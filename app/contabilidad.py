"""
Módulo de cálculos contables para el salón de manicuría.
Genera libros de ingresos/egresos, balance mensual, control de monotributo
y exportaciones Excel/CSV.
"""
import csv
import io
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import models


# ── Límites de categoría Monotributo 2024-2025 (ARS) ─────────────────────────
# Actualizar según RG AFIP vigente
LIMITES_MONOTRIBUTO = {
    "A": 2_109_000,
    "B": 3_133_100,
    "C": 4_361_100,
    "D": 5_407_800,
    "E": 6_471_100,
    "F": 8_085_800,
    "G": 9_699_300,
    "H": 13_700_500,
    "I": 17_700_000,
    "J": 21_820_000,
    "K": 25_844_900,
}


def _periodo_actual(mes: Optional[int] = None, anio: Optional[int] = None):
    hoy = date.today()
    m = mes or hoy.month
    a = anio or hoy.year
    inicio = datetime(a, m, 1)
    if m == 12:
        fin = datetime(a + 1, 1, 1) - timedelta(seconds=1)
    else:
        fin = datetime(a, m + 1, 1) - timedelta(seconds=1)
    return inicio, fin


# ── Libro de Ingresos ─────────────────────────────────────────────────────────

def get_libro_ingresos(db: Session, desde: datetime, hasta: datetime) -> dict:
    ventas = (
        db.query(models.Venta)
        .filter(models.Venta.fecha_hora >= desde, models.Venta.fecha_hora <= hasta)
        .order_by(models.Venta.fecha_hora)
        .all()
    )

    filas = []
    totales_por_metodo = {}

    for v in ventas:
        servicios_str = " + ".join(i.nombre_servicio for i in v.items if i.nombre_servicio)
        cliente_nombre = v.cliente.nombre if v.cliente else "Ocasional"
        subtotal = v.total + (v.descuento or 0)

        # Desglose de pago
        if v.forma_pago == "mixto" and v.pagos:
            pagos_str = " + ".join(f"{p.metodo} ${p.monto:,.0f}".replace(",", ".") for p in v.pagos)
        else:
            pagos_str = v.forma_pago

        filas.append({
            "id": v.id,
            "fecha": v.fecha_hora,
            "cliente": cliente_nombre,
            "servicios": servicios_str,
            "subtotal": subtotal,
            "descuento": v.descuento or 0,
            "total": v.total,
            "forma_pago": v.forma_pago,
            "pagos_detalle": pagos_str,
            "notas": v.notas or "",
        })

        # Acumular por método
        if v.forma_pago == "mixto" and v.pagos:
            for p in v.pagos:
                totales_por_metodo[p.metodo] = totales_por_metodo.get(p.metodo, 0) + p.monto
        else:
            metodo = v.forma_pago
            totales_por_metodo[metodo] = totales_por_metodo.get(metodo, 0) + v.total

    return {
        "filas": filas,
        "total": sum(v.total for v in ventas),
        "cantidad_ventas": len(ventas),
        "totales_por_metodo": totales_por_metodo,
        "descuentos_total": sum(v.descuento or 0 for v in ventas),
    }


# ── Libro de Egresos ──────────────────────────────────────────────────────────

def get_libro_egresos(db: Session, desde: datetime, hasta: datetime) -> dict:
    filas = []

    # Costos fijos del período (prorrateados por días si el período no es un mes completo)
    costos_fijos = db.query(models.CostoFijo).filter_by(activo=True).all()
    dias_periodo = max(1, (hasta - desde).days + 1)
    dias_mes = 30  # promedio para prorrateo

    for c in costos_fijos:
        monto_periodo = c.monto * dias_periodo / dias_mes
        filas.append({
            "fecha": desde,
            "tipo": "Costo Fijo",
            "descripcion": c.nombre,
            "categoria": c.categoria,
            "proveedor": "",
            "monto": round(monto_periodo, 2),
        })

    # Compras de stock del período
    compras = (
        db.query(models.CompraStock)
        .filter(models.CompraStock.fecha >= desde, models.CompraStock.fecha <= hasta)
        .order_by(models.CompraStock.fecha)
        .all()
    )
    for c in compras:
        filas.append({
            "fecha": c.fecha,
            "tipo": "Compra Insumo",
            "descripcion": f"{c.producto.nombre} x{c.cantidad} {c.producto.unidad}",
            "categoria": "insumos",
            "proveedor": c.proveedor or "",
            "monto": c.cantidad * c.precio_unitario,
        })

    filas.sort(key=lambda x: x["fecha"])
    total = sum(f["monto"] for f in filas)

    return {
        "filas": filas,
        "total": total,
        "total_costos_fijos": sum(f["monto"] for f in filas if f["tipo"] == "Costo Fijo"),
        "total_compras": sum(f["monto"] for f in filas if f["tipo"] == "Compra Insumo"),
    }


# ── Balance Mensual ───────────────────────────────────────────────────────────

def get_balance_mensual(db: Session, anio: int) -> dict:
    meses = []
    total_ingresos = 0
    total_egresos = 0

    nombres_meses = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    for m in range(1, 13):
        inicio, fin = _periodo_actual(m, anio)
        ing = get_libro_ingresos(db, inicio, fin)
        egr = get_libro_egresos(db, inicio, fin)
        resultado = ing["total"] - egr["total"]
        margen_pct = (resultado / ing["total"] * 100) if ing["total"] > 0 else 0

        meses.append({
            "mes": m,
            "nombre": nombres_meses[m],
            "ingresos": ing["total"],
            "egresos": egr["total"],
            "resultado": resultado,
            "margen_pct": round(margen_pct, 1),
            "cantidad_ventas": ing["cantidad_ventas"],
        })
        total_ingresos += ing["total"]
        total_egresos += egr["total"]

    resultado_anual = total_ingresos - total_egresos
    margen_anual = (resultado_anual / total_ingresos * 100) if total_ingresos > 0 else 0

    return {
        "anio": anio,
        "meses": meses,
        "total_ingresos": total_ingresos,
        "total_egresos": total_egresos,
        "resultado_anual": resultado_anual,
        "margen_anual": round(margen_anual, 1),
    }


# ── Control Monotributo ───────────────────────────────────────────────────────

def get_control_monotributo(db: Session) -> dict:
    """Calcula facturación de los últimos 12 meses y compara con límites."""
    hoy = date.today()
    hace_12m = datetime(
        hoy.year if hoy.month > 1 else hoy.year - 1,
        hoy.month - 1 if hoy.month > 1 else 12,
        1
    )
    hasta = datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59)

    ventas = db.query(models.Venta).filter(
        models.Venta.fecha_hora >= hace_12m,
        models.Venta.fecha_hora <= hasta,
    ).all()

    facturacion_12m = sum(v.total for v in ventas)

    # Determinar categoría actual
    categoria_actual = None
    limite_actual = None
    categoria_siguiente = None
    limite_siguiente = None

    categorias_ord = sorted(LIMITES_MONOTRIBUTO.items(), key=lambda x: x[1])
    for i, (cat, limite) in enumerate(categorias_ord):
        if facturacion_12m <= limite:
            categoria_actual = cat
            limite_actual = limite
            if i + 1 < len(categorias_ord):
                categoria_siguiente = categorias_ord[i + 1][0]
                limite_siguiente = categorias_ord[i + 1][1]
            break

    if not categoria_actual:
        categoria_actual = "EXCEDIDA"
        limite_actual = categorias_ord[-1][1]

    # Promedio mensual de los últimos 3 meses para proyección
    hace_3m = hoy - timedelta(days=90)
    ventas_3m = db.query(models.Venta).filter(
        models.Venta.fecha_hora >= datetime(hace_3m.year, hace_3m.month, hace_3m.day)
    ).all()
    promedio_mensual = sum(v.total for v in ventas_3m) / 3 if ventas_3m else 0

    # Meses hasta alcanzar el límite siguiente
    meses_hasta_limite = None
    if limite_siguiente and promedio_mensual > 0:
        margen = limite_siguiente - facturacion_12m
        meses_hasta_limite = max(0, round(margen / promedio_mensual, 1))

    pct_limite_actual = min(100, (facturacion_12m / limite_actual * 100)) if limite_actual else 0

    # Historial por mes (últimos 12)
    historial = []
    for i in range(12):
        ref = hoy.replace(day=1) - timedelta(days=i * 30)
        inicio_m = datetime(ref.year, ref.month, 1)
        if ref.month == 12:
            fin_m = datetime(ref.year + 1, 1, 1) - timedelta(seconds=1)
        else:
            fin_m = datetime(ref.year, ref.month + 1, 1) - timedelta(seconds=1)

        total_m = sum(
            v.total for v in ventas
            if inicio_m <= v.fecha_hora <= fin_m
        )
        historial.insert(0, {
            "mes": ref.strftime("%b %Y"),
            "total": total_m,
        })

    return {
        "facturacion_12m": facturacion_12m,
        "categoria_actual": categoria_actual,
        "limite_actual": limite_actual,
        "categoria_siguiente": categoria_siguiente,
        "limite_siguiente": limite_siguiente,
        "pct_limite_actual": round(pct_limite_actual, 1),
        "promedio_mensual": round(promedio_mensual),
        "meses_hasta_limite": meses_hasta_limite,
        "historial": historial,
        "limites": dict(categorias_ord),
    }


# ── Exportación Excel ─────────────────────────────────────────────────────────

def exportar_excel(db: Session, desde: datetime, hasta: datetime, nombre_negocio: str = "Salón") -> io.BytesIO:
    """
    Genera un archivo Excel (.xlsx) con 5 hojas:
    1. Libro de Ventas
    2. Por Forma de Pago
    3. Libro de Egresos
    4. Balance Mensual
    5. Control Monotributo
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()

    # Paleta de colores
    COLOR_HEADER = "2D1B69"   # Violeta oscuro

    def _estilo_header(ws, fila, columnas):
        for col, titulo in enumerate(columnas, 1):
            cell = ws.cell(row=fila, column=col, value=titulo)
            cell.font = Font(bold=True, color="FFFFFF", size=10)
            cell.fill = PatternFill("solid", fgColor=COLOR_HEADER)
            cell.alignment = Alignment(horizontal="center", vertical="center")

    def _autofit(ws):
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max_len + 4, 45)

    def _fmt_pesos(val) -> str:
        try:
            return f"${float(val):,.0f}".replace(",", ".")
        except Exception:
            return "$0"

    # ── Hoja 1: Libro de Ventas ──
    ws1 = wb.active
    ws1.title = "Libro de Ventas"
    ws1.append([
        f"LIBRO DE VENTAS — {nombre_negocio}",
        f"Período: {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}"
    ])
    ws1.append([])

    cols1 = ["N°", "Fecha", "Hora", "Cliente", "Servicios", "Subtotal", "Descuento", "Total", "Forma de Pago", "Notas"]
    _estilo_header(ws1, 3, cols1)

    ing = get_libro_ingresos(db, desde, hasta)
    for i, f in enumerate(ing["filas"], 1):
        ws1.append([
            f["id"],
            f["fecha"].strftime("%d/%m/%Y") if f["fecha"] else "",
            (f["fecha"] - timedelta(hours=3)).strftime("%H:%M") if f["fecha"] else "",
            f["cliente"],
            f["servicios"],
            f["subtotal"],
            f["descuento"],
            f["total"],
            f["pagos_detalle"],
            f["notas"],
        ])

    # Fila de totales
    ws1.append([])
    ws1.append(["", "", "", "", "TOTAL", _fmt_pesos(ing["total"] + ing["descuentos_total"]),
                _fmt_pesos(ing["descuentos_total"]), _fmt_pesos(ing["total"]), "", ""])
    _autofit(ws1)

    # ── Hoja 2: Por Forma de Pago ──
    ws2 = wb.create_sheet("Por Forma de Pago")
    ws2.append(["Resumen por Método de Pago"])
    ws2.append([])
    _estilo_header(ws2, 3, ["Método de Pago", "Total Recaudado", "% del Total"])
    total_ing = ing["total"] or 1
    for metodo, monto in sorted(ing["totales_por_metodo"].items(), key=lambda x: -x[1]):
        ws2.append([metodo.capitalize(), _fmt_pesos(monto), f"{monto/total_ing*100:.1f}%"])
    ws2.append(["TOTAL", _fmt_pesos(ing["total"]), "100%"])
    _autofit(ws2)

    # ── Hoja 3: Libro de Egresos ──
    ws3 = wb.create_sheet("Libro de Egresos")
    ws3.append([f"LIBRO DE EGRESOS — Período: {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}"])
    ws3.append([])
    _estilo_header(ws3, 3, ["Fecha", "Tipo", "Descripción", "Categoría", "Proveedor", "Monto"])
    egr = get_libro_egresos(db, desde, hasta)
    for f in egr["filas"]:
        ws3.append([
            f["fecha"].strftime("%d/%m/%Y") if f["fecha"] else "",
            f["tipo"], f["descripcion"], f["categoria"], f["proveedor"],
            _fmt_pesos(f["monto"]),
        ])
    ws3.append([])
    ws3.append(["", "", "", "", "TOTAL EGRESOS", _fmt_pesos(egr["total"])])
    _autofit(ws3)

    # ── Hoja 4: Balance Mensual ──
    ws4 = wb.create_sheet("Balance Mensual")
    anio_desde = desde.year
    ws4.append([f"BALANCE MENSUAL {anio_desde}"])
    ws4.append([])
    _estilo_header(ws4, 3, ["Mes", "Ventas", "Ingresos", "Egresos", "Resultado Neto", "Margen %"])
    balance = get_balance_mensual(db, anio_desde)
    for m in balance["meses"]:
        ws4.append([
            m["nombre"], m["cantidad_ventas"],
            _fmt_pesos(m["ingresos"]), _fmt_pesos(m["egresos"]),
            _fmt_pesos(m["resultado"]), f"{m['margen_pct']}%"
        ])
    ws4.append([])
    ws4.append(["TOTAL ANUAL", "", _fmt_pesos(balance["total_ingresos"]),
                _fmt_pesos(balance["total_egresos"]), _fmt_pesos(balance["resultado_anual"]),
                f"{balance['margen_anual']}%"])
    _autofit(ws4)

    # ── Hoja 5: Control Monotributo ──
    ws5 = wb.create_sheet("Control Monotributo")
    mono = get_control_monotributo(db)
    ws5.append(["CONTROL CATEGORÍA MONOTRIBUTO"])
    ws5.append([])
    ws5.append(["Facturación últimos 12 meses", _fmt_pesos(mono["facturacion_12m"])])
    ws5.append(["Categoría actual", mono["categoria_actual"]])
    ws5.append(["Límite categoría actual", _fmt_pesos(mono["limite_actual"])])
    ws5.append(["% del límite utilizado", f"{mono['pct_limite_actual']}%"])
    ws5.append(["Promedio mensual (últ. 3 meses)", _fmt_pesos(mono["promedio_mensual"])])
    if mono["categoria_siguiente"]:
        ws5.append(["Categoría siguiente", mono["categoria_siguiente"]])
        ws5.append(["Límite categoría siguiente", _fmt_pesos(mono["limite_siguiente"])])
        ws5.append(["Meses estimados hasta límite siguiente",
                    str(mono["meses_hasta_limite"]) if mono["meses_hasta_limite"] is not None else "N/A"])
    ws5.append([])
    ws5.append(["Histórico mensual (últimos 12 meses)"])
    _estilo_header(ws5, ws5.max_row + 1, ["Mes", "Facturación"])
    for h in mono["historial"]:
        ws5.append([h["mes"], _fmt_pesos(h["total"])])
    ws5.append([])
    ws5.append(["Límites de Categoría Vigentes"])
    _estilo_header(ws5, ws5.max_row + 1, ["Categoría", "Límite Anual"])
    for cat, lim in sorted(mono["limites"].items(), key=lambda x: x[1]):
        ws5.append([cat, _fmt_pesos(lim)])
    _autofit(ws5)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ── Exportación CSV ───────────────────────────────────────────────────────────

def exportar_csv_ventas(db: Session, desde: datetime, hasta: datetime) -> io.StringIO:
    ing = get_libro_ingresos(db, desde, hasta)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["N°", "Fecha", "Hora", "Cliente", "Servicios", "Subtotal", "Descuento", "Total", "Forma de Pago", "Notas"])
    for f in ing["filas"]:
        writer.writerow([
            f["id"],
            f["fecha"].strftime("%d/%m/%Y") if f["fecha"] else "",
            (f["fecha"] - timedelta(hours=3)).strftime("%H:%M") if f["fecha"] else "",
            f["cliente"], f["servicios"],
            f["subtotal"], f["descuento"], f["total"],
            f["pagos_detalle"], f["notas"],
        ])
    writer.writerow([])
    writer.writerow(["", "", "", "", "TOTAL", "", "", ing["total"], "", ""])
    output.seek(0)
    return output


def exportar_csv_egresos(db: Session, desde: datetime, hasta: datetime) -> io.StringIO:
    egr = get_libro_egresos(db, desde, hasta)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Fecha", "Tipo", "Descripción", "Categoría", "Proveedor", "Monto"])
    for f in egr["filas"]:
        writer.writerow([
            f["fecha"].strftime("%d/%m/%Y") if f["fecha"] else "",
            f["tipo"], f["descripcion"], f["categoria"], f["proveedor"], f["monto"],
        ])
    writer.writerow([])
    writer.writerow(["", "", "", "", "TOTAL", egr["total"]])
    output.seek(0)
    return output


def exportar_csv_balance(db: Session, anio: int) -> io.StringIO:
    balance = get_balance_mensual(db, anio)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Mes", "Cantidad Ventas", "Ingresos", "Egresos", "Resultado Neto", "Margen %"])
    for m in balance["meses"]:
        writer.writerow([m["nombre"], m["cantidad_ventas"], m["ingresos"], m["egresos"], m["resultado"], f"{m['margen_pct']}%"])
    writer.writerow([])
    writer.writerow(["TOTAL ANUAL", "", balance["total_ingresos"], balance["total_egresos"], balance["resultado_anual"], f"{balance['margen_anual']}%"])
    output.seek(0)
    return output

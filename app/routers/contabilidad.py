"""
Router del módulo de contabilidad.
"""
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
import app.contabilidad as conta

router = APIRouter(prefix="/contabilidad", tags=["contabilidad"])
templates = Jinja2Templates(directory="app/templates")


def _parse_periodo(desde: str, hasta: str, mes: str, anio: str):
    """Parsea los parámetros de período y retorna (desde_dt, hasta_dt, mes_int, anio_int)."""
    hoy = date.today()

    # Si viene mes y año usar eso
    if mes and anio:
        try:
            m, a = int(mes), int(anio)
            inicio = datetime(a, m, 1)
            if m == 12:
                fin = datetime(a + 1, 1, 1) - timedelta(seconds=1)
            else:
                fin = datetime(a, m + 1, 1) - timedelta(seconds=1)
            return inicio, fin, m, a
        except ValueError:
            pass

    # Si viene rango personalizado
    if desde and hasta:
        try:
            d_desde = date.fromisoformat(desde)
            d_hasta = date.fromisoformat(hasta)
            return (
                datetime(d_desde.year, d_desde.month, d_desde.day),
                datetime(d_hasta.year, d_hasta.month, d_hasta.day, 23, 59, 59),
                None, None
            )
        except ValueError:
            pass

    # Default: mes actual
    m, a = hoy.month, hoy.year
    inicio = datetime(a, m, 1)
    if m == 12:
        fin = datetime(a + 1, 1, 1) - timedelta(seconds=1)
    else:
        fin = datetime(a, m + 1, 1) - timedelta(seconds=1)
    return inicio, fin, m, a


@router.get("/", response_class=HTMLResponse)
def panel_contabilidad(
    request: Request,
    desde: str = "",
    hasta: str = "",
    mes: str = "",
    anio: str = "",
    db: Session = Depends(get_db),
):
    hoy = date.today()
    d_desde, d_hasta, mes_int, anio_int = _parse_periodo(desde, hasta, mes, anio)

    ing = conta.get_libro_ingresos(db, d_desde, d_hasta)
    egr = conta.get_libro_egresos(db, d_desde, d_hasta)
    mono = conta.get_control_monotributo(db)

    resultado = ing["total"] - egr["total"]
    margen_pct = (resultado / ing["total"] * 100) if ing["total"] > 0 else 0

    # Balance últimos 6 meses para gráfico
    meses_grafico = []
    for i in range(5, -1, -1):
        ref = hoy.replace(day=1) - timedelta(days=i * 28)
        m_i = ref.month
        a_i = ref.year
        inicio_m = datetime(a_i, m_i, 1)
        if m_i == 12:
            fin_m = datetime(a_i + 1, 1, 1) - timedelta(seconds=1)
        else:
            fin_m = datetime(a_i, m_i + 1, 1) - timedelta(seconds=1)
        ing_m = conta.get_libro_ingresos(db, inicio_m, fin_m)
        egr_m = conta.get_libro_egresos(db, inicio_m, fin_m)
        meses_grafico.append({
            "label": ref.strftime("%b"),
            "ingresos": ing_m["total"],
            "egresos": egr_m["total"],
        })

    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")

    return templates.TemplateResponse("contabilidad/index.html", {
        "request": request,
        "desde": d_desde,
        "hasta": d_hasta,
        "mes_int": mes_int,
        "anio_int": anio_int,
        "anio_actual": hoy.year,
        "ingresos": ing,
        "egresos": egr,
        "resultado": resultado,
        "margen_pct": round(margen_pct, 1),
        "monotributo": mono,
        "meses_grafico": meses_grafico,
        "flash_msg": flash_msg,
        "flash_type": flash_type,
    })


@router.get("/ingresos", response_class=HTMLResponse)
def libro_ingresos(
    request: Request,
    desde: str = "",
    hasta: str = "",
    mes: str = "",
    anio: str = "",
    forma_pago: str = "",
    db: Session = Depends(get_db),
):
    d_desde, d_hasta, mes_int, anio_int = _parse_periodo(desde, hasta, mes, anio)
    ing = conta.get_libro_ingresos(db, d_desde, d_hasta)

    # Filtrar por forma de pago si se especificó
    if forma_pago:
        ing["filas"] = [f for f in ing["filas"] if f["forma_pago"] == forma_pago]

    return templates.TemplateResponse("contabilidad/ingresos.html", {
        "request": request,
        "desde": d_desde,
        "hasta": d_hasta,
        "mes_int": mes_int,
        "anio_int": anio_int,
        "anio_actual": date.today().year,
        "ingresos": ing,
        "filtro_forma_pago": forma_pago,
        "formas_pago": ["efectivo", "transferencia", "tarjeta", "mixto"],
    })


@router.get("/egresos", response_class=HTMLResponse)
def libro_egresos(
    request: Request,
    desde: str = "",
    hasta: str = "",
    mes: str = "",
    anio: str = "",
    categoria: str = "",
    db: Session = Depends(get_db),
):
    d_desde, d_hasta, mes_int, anio_int = _parse_periodo(desde, hasta, mes, anio)
    egr = conta.get_libro_egresos(db, d_desde, d_hasta)

    if categoria:
        egr["filas"] = [f for f in egr["filas"] if f["categoria"] == categoria]

    return templates.TemplateResponse("contabilidad/egresos.html", {
        "request": request,
        "desde": d_desde,
        "hasta": d_hasta,
        "mes_int": mes_int,
        "anio_int": anio_int,
        "anio_actual": date.today().year,
        "egresos": egr,
        "filtro_categoria": categoria,
        "categorias": ["local", "servicios", "personal", "insumos", "otros"],
    })


@router.get("/balance", response_class=HTMLResponse)
def balance_anual(
    request: Request,
    anio: str = "",
    db: Session = Depends(get_db),
):
    hoy = date.today()
    try:
        anio_int = int(anio) if anio else hoy.year
    except ValueError:
        anio_int = hoy.year

    balance = conta.get_balance_mensual(db, anio_int)
    anios_disponibles = list(range(hoy.year, hoy.year - 5, -1))

    return templates.TemplateResponse("contabilidad/balance.html", {
        "request": request,
        "balance": balance,
        "anio_int": anio_int,
        "anios_disponibles": anios_disponibles,
    })


@router.get("/monotributo", response_class=HTMLResponse)
def control_monotributo(request: Request, db: Session = Depends(get_db)):
    mono = conta.get_control_monotributo(db)
    return templates.TemplateResponse("contabilidad/monotributo.html", {
        "request": request,
        "mono": mono,
    })


@router.get("/exportar", response_class=HTMLResponse)
def form_exportar(request: Request):
    hoy = date.today()
    return templates.TemplateResponse("contabilidad/exportar.html", {
        "request": request,
        "anio_actual": hoy.year,
        "mes_actual": hoy.month,
        "desde_default": date(hoy.year, hoy.month, 1).isoformat(),
        "hasta_default": hoy.isoformat(),
    })


@router.get("/exportar/excel")
def descargar_excel(
    desde: str = "",
    hasta: str = "",
    mes: str = "",
    anio: str = "",
    db: Session = Depends(get_db),
):
    d_desde, d_hasta, _, _ = _parse_periodo(desde, hasta, mes, anio)
    output = conta.exportar_excel(db, d_desde, d_hasta)
    nombre = f"contabilidad_{d_desde.strftime('%Y%m%d')}_{d_hasta.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/exportar/csv/ventas")
def descargar_csv_ventas(
    desde: str = "",
    hasta: str = "",
    mes: str = "",
    anio: str = "",
    db: Session = Depends(get_db),
):
    d_desde, d_hasta, _, _ = _parse_periodo(desde, hasta, mes, anio)
    output = conta.exportar_csv_ventas(db, d_desde, d_hasta)
    nombre = f"ventas_{d_desde.strftime('%Y%m%d')}_{d_hasta.strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/exportar/csv/egresos")
def descargar_csv_egresos(
    desde: str = "",
    hasta: str = "",
    mes: str = "",
    anio: str = "",
    db: Session = Depends(get_db),
):
    d_desde, d_hasta, _, _ = _parse_periodo(desde, hasta, mes, anio)
    output = conta.exportar_csv_egresos(db, d_desde, d_hasta)
    nombre = f"egresos_{d_desde.strftime('%Y%m%d')}_{d_hasta.strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/exportar/csv/balance")
def descargar_csv_balance(anio: str = "", db: Session = Depends(get_db)):
    try:
        anio_int = int(anio) if anio else date.today().year
    except ValueError:
        anio_int = date.today().year
    output = conta.exportar_csv_balance(db, anio_int)
    nombre = f"balance_{anio_int}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )

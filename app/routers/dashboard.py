from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta, timezone


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)
from collections import Counter, defaultdict
from app.database import get_db
from app import models

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


def _rango(inicio: datetime, fin: datetime, db: Session):
    return db.query(func.sum(models.Venta.total)).filter(
        models.Venta.fecha_hora >= inicio,
        models.Venta.fecha_hora < fin
    ).scalar() or 0


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    rango: str = "7d",
    desde: str = "",
    hasta: str = "",
    db: Session = Depends(get_db),
):
    hoy = date.today()
    ahora = _now()

    # Ingresos KPIs
    inicio_hoy = datetime(hoy.year, hoy.month, hoy.day)
    fin_hoy = inicio_hoy + timedelta(days=1)
    lunes = hoy - timedelta(days=hoy.weekday())
    inicio_semana = datetime(lunes.year, lunes.month, lunes.day)
    inicio_mes = datetime(hoy.year, hoy.month, 1)

    ingresos_hoy = _rango(inicio_hoy, fin_hoy, db)
    ingresos_semana = _rango(inicio_semana, ahora, db)
    ingresos_mes = _rango(inicio_mes, ahora, db)

    # Rango del gráfico
    dias_semana_nombres = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    if rango == "30d":
        n_dias = 30
        dia_inicio_chart = hoy - timedelta(days=29)
    elif rango == "mes":
        dia_inicio_chart = date(hoy.year, hoy.month, 1)
        n_dias = (hoy - dia_inicio_chart).days + 1
    elif rango == "custom":
        try:
            dia_inicio_chart = date.fromisoformat(desde) if desde else hoy - timedelta(days=6)
            dia_fin_chart = date.fromisoformat(hasta) if hasta else hoy
            if dia_fin_chart < dia_inicio_chart:
                dia_fin_chart = dia_inicio_chart
            n_dias = (dia_fin_chart - dia_inicio_chart).days + 1
        except ValueError:
            dia_inicio_chart = hoy - timedelta(days=6)
            n_dias = 7
    else:  # 7d por defecto
        rango = "7d"
        n_dias = 7
        dia_inicio_chart = hoy - timedelta(days=6)

    labels_chart = []
    data_chart = []
    for i in range(n_dias):
        dia = dia_inicio_chart + timedelta(days=i)
        label = dias_semana_nombres[dia.weekday()] if n_dias <= 7 else dia.strftime('%d/%m')
        labels_chart.append(label)
        d_inicio = datetime(dia.year, dia.month, dia.day)
        total = _rango(d_inicio, d_inicio + timedelta(days=1), db)
        data_chart.append(total)

    # Top servicios del mes
    items_mes = (
        db.query(models.VentaItem)
        .join(models.Venta)
        .filter(models.Venta.fecha_hora >= inicio_mes)
        .all()
    )
    conteo_servicios = Counter()
    ingresos_por_servicio = defaultdict(float)
    for item in items_mes:
        conteo_servicios[item.nombre_servicio] += 1
        ingresos_por_servicio[item.nombre_servicio] += item.precio_cobrado
    top_servicios = conteo_servicios.most_common(5)

    # Cliente más frecuente del mes
    ventas_mes = (
        db.query(models.Venta)
        .filter(models.Venta.fecha_hora >= inicio_mes, models.Venta.cliente_id.isnot(None))
        .all()
    )
    conteo_clientes = Counter(v.cliente_id for v in ventas_mes)
    cliente_top = None
    if conteo_clientes:
        cli_id, visitas = conteo_clientes.most_common(1)[0]
        cliente_top = {
            "cliente": db.query(models.Cliente).filter_by(id=cli_id).first(),
            "visitas": visitas,
        }

    # Análisis de márgenes por servicio
    servicios_activos = db.query(models.Servicio).filter_by(activo=True).order_by(models.Servicio.nombre).all()
    margenes = []
    for s in servicios_activos:
        costo = sum(sp.cantidad_uso * sp.producto.costo_unitario for sp in s.productos_usados)
        sin_costos = len(s.productos_usados) == 0
        margen = s.precio - costo
        margen_pct = (margen / s.precio * 100) if s.precio > 0 else 0
        if sin_costos:
            estado = "sin_datos"
        elif margen < 0:
            estado = "perdida"
        elif margen_pct < 20:
            estado = "critico"
        elif margen_pct < 40:
            estado = "bajo"
        else:
            estado = "ok"
        margenes.append({
            "servicio": s,
            "costo": costo,
            "margen": margen,
            "margen_pct": margen_pct,
            "estado": estado,
            "sin_costos": sin_costos,
        })
    margenes.sort(key=lambda x: (x["estado"] == "sin_datos", -x.get("margen_pct", 0)
                                  if x["estado"] != "perdida" else float("inf")))

    # Forma de pago más usada
    conteo_pago = Counter(v.forma_pago for v in ventas_mes)
    pago_labels = list(conteo_pago.keys())
    pago_data = list(conteo_pago.values())

    # Proyección de stock
    # Calcular consumo de los últimos 14 días para estimar días restantes
    hace_14 = _now() - timedelta(days=14)
    movimientos_recientes = (
        db.query(models.StockMovimiento)
        .filter(
            models.StockMovimiento.tipo == "venta",
            models.StockMovimiento.fecha >= hace_14
        )
        .all()
    )
    consumo_14 = defaultdict(float)
    for m in movimientos_recientes:
        consumo_14[m.producto_id] += abs(m.cantidad)

    proyeccion_stock = []
    productos_criticos = (
        db.query(models.ProductoStock)
        .filter_by(activo=True)
        .filter(models.ProductoStock.cantidad_actual <= models.ProductoStock.cantidad_minima * 3)
        .all()
    )
    for p in productos_criticos:
        consumo_diario = consumo_14.get(p.id, 0) / 14
        if consumo_diario > 0:
            dias_restantes = int(p.cantidad_actual / consumo_diario)
        else:
            dias_restantes = None
        proyeccion_stock.append({
            "producto": p,
            "dias": dias_restantes,
            "critico": p.cantidad_actual <= p.cantidad_minima,
        })
    proyeccion_stock.sort(key=lambda x: (x["dias"] is None, x["dias"] or 9999))

    # Alertas de stock bajo
    alertas_stock = db.query(models.ProductoStock).filter(
        models.ProductoStock.activo == True,
        models.ProductoStock.cantidad_actual <= models.ProductoStock.cantidad_minima
    ).count()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "ingresos_hoy": ingresos_hoy,
        "ingresos_semana": ingresos_semana,
        "ingresos_mes": ingresos_mes,
        "labels_chart": labels_chart,
        "data_chart": data_chart,
        "top_servicios": top_servicios,
        "ingresos_por_servicio": ingresos_por_servicio,
        "cliente_top": cliente_top,
        "pago_labels": pago_labels,
        "pago_data": pago_data,
        "proyeccion_stock": proyeccion_stock[:5],
        "alertas_stock": alertas_stock,
        "margenes": margenes,
        "hoy": hoy.isoformat(),
        "rango": rango,
        "chart_desde": desde or (dia_inicio_chart.isoformat() if rango == "custom" else ""),
        "chart_hasta": hasta or (hoy.isoformat() if rango == "custom" else ""),
    })

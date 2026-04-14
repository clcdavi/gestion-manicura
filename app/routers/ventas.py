from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from app.database import get_db
from app import models


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


router = APIRouter(prefix="/ventas", tags=["ventas"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def lista_ventas(request: Request, fecha: str = "", db: Session = Depends(get_db)):
    if fecha:
        try:
            dia = date.fromisoformat(fecha)
        except ValueError:
            dia = date.today()
    else:
        dia = date.today()

    inicio = datetime(dia.year, dia.month, dia.day)
    fin = inicio + timedelta(days=1)

    ventas = (
        db.query(models.Venta)
        .filter(models.Venta.fecha_hora >= inicio, models.Venta.fecha_hora < fin)
        .order_by(models.Venta.fecha_hora.desc())
        .all()
    )
    total_dia = sum(v.total for v in ventas)
    clientes = db.query(models.Cliente).filter_by(activo=True).order_by(models.Cliente.nombre).all()
    return templates.TemplateResponse("ventas/list.html", {
        "request": request,
        "ventas": ventas,
        "fecha": dia.isoformat(),
        "total_dia": total_dia,
        "hoy": date.today().isoformat(),
        "clientes": clientes,
    })


@router.get("/nueva", response_class=HTMLResponse)
def form_nueva_venta(request: Request, db: Session = Depends(get_db)):
    clientes = db.query(models.Cliente).filter_by(activo=True).order_by(models.Cliente.nombre).all()
    servicios = db.query(models.Servicio).filter_by(activo=True).order_by(models.Servicio.nombre).all()
    combos = db.query(models.Combo).filter_by(activo=True).order_by(models.Combo.nombre).all()
    return templates.TemplateResponse("ventas/nueva.html", {
        "request": request,
        "clientes": clientes,
        "servicios": servicios,
        "combos": combos,
    })


@router.post("/nueva")
async def registrar_venta(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    cliente_id = form.get("cliente_id") or None
    if cliente_id:
        cliente_id = int(cliente_id)
    forma_pago = form.get("forma_pago", "efectivo")
    notas = form.get("notas", "")

    # Descuento
    try:
        descuento_valor = float(form.get("descuento_valor") or 0)
    except (ValueError, TypeError):
        descuento_valor = 0
    descuento_tipo = form.get("descuento_tipo", "pesos")
    descuento_motivo = form.get("descuento_motivo", "")

    # Items
    nombres = form.getlist("item_nombre")
    precios = form.getlist("item_precio")
    servicios_ids = form.getlist("item_servicio_id")

    if not nombres:
        return RedirectResponse(url="/ventas/nueva", status_code=303)

    items = []
    subtotal = 0
    for i, nombre in enumerate(nombres):
        if not nombre.strip():
            continue
        try:
            precio = float(precios[i]) if i < len(precios) else 0
        except (ValueError, TypeError):
            precio = 0
        srv_id = int(servicios_ids[i]) if i < len(servicios_ids) and servicios_ids[i] else None
        subtotal += precio
        items.append(models.VentaItem(
            servicio_id=srv_id,
            nombre_servicio=nombre.strip(),
            precio_cobrado=precio,
        ))

    if not items or subtotal <= 0:
        return RedirectResponse(url="/ventas/nueva", status_code=303)

    # Calcular descuento real
    if descuento_tipo == "porcentaje":
        descuento_monto = round(subtotal * descuento_valor / 100, 2)
    else:
        descuento_monto = descuento_valor
    descuento_monto = max(0, min(descuento_monto, subtotal))
    total = subtotal - descuento_monto

    venta = models.Venta(
        cliente_id=cliente_id,
        total=total,
        forma_pago=forma_pago,
        notas=notas,
        descuento=descuento_monto,
        descuento_tipo=descuento_tipo,
        descuento_motivo=descuento_motivo,
        items=items,
    )
    db.add(venta)
    db.flush()

    # Descontar stock por cada servicio con consumos configurados
    for item in items:
        if item.servicio_id:
            servicio = db.query(models.Servicio).filter_by(id=item.servicio_id).first()
            if servicio:
                for sp in servicio.productos_usados:
                    consumo_real = min(sp.cantidad_uso, sp.producto.cantidad_actual)
                    sp.producto.cantidad_actual = max(0, sp.producto.cantidad_actual - sp.cantidad_uso)
                    db.add(models.StockMovimiento(
                        producto_id=sp.producto.id,
                        cantidad=-consumo_real,
                        tipo="venta",
                        descripcion=f"Consumo por {item.nombre_servicio}",
                        venta_id=venta.id,
                    ))

    db.commit()
    return RedirectResponse(url="/ventas", status_code=303)


@router.post("/{venta_id}/asignar-cliente")
def asignar_cliente(venta_id: int, cliente_id: int = Form(...), db: Session = Depends(get_db)):
    venta = db.query(models.Venta).filter_by(id=venta_id).first()
    if not venta:
        raise HTTPException(status_code=404)
    venta.cliente_id = cliente_id
    db.commit()
    return RedirectResponse(url="/ventas", status_code=303)


@router.get("/caja", response_class=HTMLResponse)
def caja_diaria(request: Request, fecha: str = "", db: Session = Depends(get_db)):
    if fecha:
        try:
            dia = date.fromisoformat(fecha)
        except ValueError:
            dia = date.today()
    else:
        dia = date.today()

    inicio = datetime(dia.year, dia.month, dia.day)
    fin = inicio + timedelta(days=1)

    ventas = (
        db.query(models.Venta)
        .filter(models.Venta.fecha_hora >= inicio, models.Venta.fecha_hora < fin)
        .all()
    )

    total = sum(v.total for v in ventas)
    por_forma = {}
    for v in ventas:
        por_forma[v.forma_pago] = por_forma.get(v.forma_pago, 0) + v.total

    items_todos = [it for v in ventas for it in v.items]
    ticket_promedio = total / len(ventas) if ventas else 0

    return templates.TemplateResponse("ventas/caja.html", {
        "request": request,
        "fecha": dia.isoformat(),
        "ventas": ventas,
        "total": total,
        "por_forma": por_forma,
        "cantidad_servicios": len(items_todos),
        "ticket_promedio": ticket_promedio,
        "hoy": date.today().isoformat(),
    })


@router.post("/{venta_id}/eliminar")
def eliminar_venta(venta_id: int, db: Session = Depends(get_db)):
    venta = db.query(models.Venta).filter_by(id=venta_id).first()
    if not venta:
        raise HTTPException(status_code=404)
    # Revertir stock antes de eliminar
    movimientos = db.query(models.StockMovimiento).filter_by(venta_id=venta_id, tipo="venta").all()
    for m in movimientos:
        producto = db.query(models.ProductoStock).filter_by(id=m.producto_id).first()
        if producto:
            producto.cantidad_actual += abs(m.cantidad)
        db.delete(m)
    db.delete(venta)
    db.commit()
    return RedirectResponse(url="/ventas", status_code=303)

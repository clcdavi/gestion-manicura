from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta, timezone
from app.database import get_db
from app import models
from app.utils import get_costo_insumos_servicio


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


router = APIRouter(prefix="/ventas", tags=["ventas"])
templates = Jinja2Templates(directory="app/templates")


# ── helpers ───────────────────────────────────────────────────────────────────

def _calcular_descuento(subtotal: float, valor: float, tipo: str) -> float:
    if tipo == "porcentaje":
        monto = round(subtotal * valor / 100, 2)
    else:
        monto = valor
    return max(0, min(monto, subtotal))


def _chequear_fidelizacion(db: Session, cliente_id: int) -> bool:
    """
    Revisa si el cliente alcanzó el umbral de visitas para obtener un beneficio.
    Actualiza beneficio_disponible=True en el modelo y retorna True si se activó.
    """
    cfg = db.query(models.ConfiguracionFidelizacion).filter_by(id=1).first()
    if not cfg or not cfg.activo:
        return False

    cliente = db.query(models.Cliente).filter_by(id=cliente_id).first()
    if not cliente or cliente.beneficio_disponible:
        return False

    # Contar ventas desde la última vez que se otorgó beneficio
    # (Simplificado: total de ventas módulo visitas_para_beneficio)
    total_ventas = db.query(models.Venta).filter_by(cliente_id=cliente_id).count()
    if total_ventas > 0 and total_ventas % cfg.visitas_para_beneficio == 0:
        cliente.beneficio_disponible = True
        db.flush()
        return True
    return False


def _revertir_stock_venta(db: Session, venta_id: int):
    """Revierte los movimientos de stock asociados a una venta."""
    movimientos = db.query(models.StockMovimiento).filter_by(
        venta_id=venta_id, tipo="venta"
    ).all()
    for m in movimientos:
        producto = db.query(models.ProductoStock).filter_by(id=m.producto_id).first()
        if producto:
            producto.cantidad_actual += abs(m.cantidad)
        db.delete(m)


def _aplicar_stock_items(db: Session, items: list, venta_id: int):
    """Descuenta stock y registra movimientos para los ítems de una venta."""
    for item in items:
        if item.servicio_id:
            servicio = db.query(models.Servicio).filter_by(id=item.servicio_id).first()
            if servicio:
                for sp in servicio.productos_usados:
                    consumo_real = min(sp.cantidad_uso, sp.producto.cantidad_actual)
                    sp.producto.cantidad_actual = max(
                        0, sp.producto.cantidad_actual - sp.cantidad_uso
                    )
                    db.add(models.StockMovimiento(
                        producto_id=sp.producto.id,
                        cantidad=-consumo_real,
                        tipo="venta",
                        descripcion=f"Consumo por {item.nombre_servicio}",
                        venta_id=venta_id,
                    ))


# ── Lista de ventas ───────────────────────────────────────────────────────────

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

    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")

    return templates.TemplateResponse("ventas/list.html", {
        "request": request,
        "ventas": ventas,
        "fecha": dia.isoformat(),
        "total_dia": total_dia,
        "hoy": date.today().isoformat(),
        "clientes": clientes,
        "flash_msg": flash_msg,
        "flash_type": flash_type,
    })


# ── Nueva venta ───────────────────────────────────────────────────────────────

@router.get("/nueva", response_class=HTMLResponse)
def form_nueva_venta(request: Request, db: Session = Depends(get_db)):
    clientes = db.query(models.Cliente).filter_by(activo=True).order_by(models.Cliente.nombre).all()
    servicios = db.query(models.Servicio).filter_by(activo=True).order_by(models.Servicio.nombre).all()
    combos = db.query(models.Combo).filter_by(activo=True).order_by(models.Combo.nombre).all()

    # Pre-cargar cliente desde query param (desde turnos)
    pre_cliente_id = request.query_params.get("cliente_id")
    pre_cliente = None
    if pre_cliente_id and pre_cliente_id.isdigit():
        pre_cliente = db.query(models.Cliente).filter_by(id=int(pre_cliente_id), activo=True).first()

    # Verificar si tiene beneficio disponible
    beneficio_msg = None
    if pre_cliente and pre_cliente.beneficio_disponible:
        cfg = db.query(models.ConfiguracionFidelizacion).filter_by(id=1).first()
        if cfg and cfg.activo:
            if cfg.tipo_beneficio == "descuento_pct":
                beneficio_msg = f"🎁 {pre_cliente.nombre} tiene un descuento de {cfg.valor_beneficio:.0f}% por fidelidad disponible."
            else:
                beneficio_msg = f"🎁 {pre_cliente.nombre} tiene un beneficio de fidelidad disponible."

    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")

    return templates.TemplateResponse("ventas/nueva.html", {
        "request": request,
        "clientes": clientes,
        "servicios": servicios,
        "combos": combos,
        "pre_cliente": pre_cliente,
        "beneficio_msg": beneficio_msg,
        "flash_msg": flash_msg,
        "flash_type": flash_type,
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
        request.session["flash"] = "Agregá al menos un servicio."
        request.session["flash_type"] = "error"
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

        # Snapshot del costo de materiales al momento
        costo_snap = None
        if srv_id:
            costo_snap = get_costo_insumos_servicio(db, srv_id)

        subtotal += precio
        items.append(models.VentaItem(
            servicio_id=srv_id,
            nombre_servicio=nombre.strip(),
            precio_cobrado=precio,
            costo_materiales_al_momento=costo_snap,
        ))

    if not items or subtotal <= 0:
        request.session["flash"] = "Total inválido."
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/ventas/nueva", status_code=303)

    descuento_monto = _calcular_descuento(subtotal, descuento_valor, descuento_tipo)
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

    # Pago mixto — parsear montos individuales
    if forma_pago == "mixto":
        metodos = form.getlist("pago_metodo")
        montos = form.getlist("pago_monto")
        for metodo, monto_str in zip(metodos, montos):
            try:
                monto = float(monto_str or 0)
            except (ValueError, TypeError):
                monto = 0
            if monto > 0 and metodo:
                db.add(models.VentaPago(venta_id=venta.id, metodo=metodo, monto=monto))

    # Stock
    _aplicar_stock_items(db, items, venta.id)

    # Fidelización — verificar si se alcanzó el umbral
    fidelizacion_activada = False
    if cliente_id:
        fidelizacion_activada = _chequear_fidelizacion(db, cliente_id)

        # Consumir beneficio si se usó (viene del form como flag)
        usar_beneficio = form.get("usar_beneficio") == "1"
        if usar_beneficio:
            cliente = db.query(models.Cliente).filter_by(id=cliente_id).first()
            if cliente:
                cliente.beneficio_disponible = False

    db.commit()

    if fidelizacion_activada:
        cliente_obj = db.query(models.Cliente).filter_by(id=cliente_id).first()
        nombre_c = cliente_obj.nombre if cliente_obj else "La cliente"
        request.session["flash"] = f"✅ Venta registrada. 🎁 ¡{nombre_c} alcanzó su beneficio de fidelidad!"
    else:
        request.session["flash"] = "✅ Venta registrada correctamente."
    request.session["flash_type"] = "success"
    return RedirectResponse(url="/ventas", status_code=303)


# ── Editar venta ──────────────────────────────────────────────────────────────

@router.get("/{venta_id}/editar", response_class=HTMLResponse)
def form_editar_venta(venta_id: int, request: Request, db: Session = Depends(get_db)):
    venta = db.query(models.Venta).filter_by(id=venta_id).first()
    if not venta:
        raise HTTPException(status_code=404)
    clientes = db.query(models.Cliente).filter_by(activo=True).order_by(models.Cliente.nombre).all()
    servicios = db.query(models.Servicio).filter_by(activo=True).order_by(models.Servicio.nombre).all()
    combos = db.query(models.Combo).filter_by(activo=True).order_by(models.Combo.nombre).all()

    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")

    return templates.TemplateResponse("ventas/editar.html", {
        "request": request,
        "venta": venta,
        "clientes": clientes,
        "servicios": servicios,
        "combos": combos,
        "flash_msg": flash_msg,
        "flash_type": flash_type,
    })


@router.post("/{venta_id}/editar")
async def actualizar_venta(venta_id: int, request: Request, db: Session = Depends(get_db)):
    venta = db.query(models.Venta).filter_by(id=venta_id).first()
    if not venta:
        raise HTTPException(status_code=404)

    form = await request.form()

    cliente_id = form.get("cliente_id") or None
    if cliente_id:
        cliente_id = int(cliente_id)
    forma_pago = form.get("forma_pago", "efectivo")
    notas = form.get("notas", "")

    try:
        descuento_valor = float(form.get("descuento_valor") or 0)
    except (ValueError, TypeError):
        descuento_valor = 0
    descuento_tipo = form.get("descuento_tipo", "pesos")
    descuento_motivo = form.get("descuento_motivo", "")

    nombres = form.getlist("item_nombre")
    precios = form.getlist("item_precio")
    servicios_ids = form.getlist("item_servicio_id")

    if not nombres:
        request.session["flash"] = "La venta debe tener al menos un servicio."
        request.session["flash_type"] = "error"
        return RedirectResponse(url=f"/ventas/{venta_id}/editar", status_code=303)

    # Revertir stock previo
    _revertir_stock_venta(db, venta_id)

    # Eliminar pagos mixtos previos
    for pago in venta.pagos:
        db.delete(pago)

    # Eliminar items previos
    for item in venta.items:
        db.delete(item)
    db.flush()

    # Construir nuevos items
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
        costo_snap = get_costo_insumos_servicio(db, srv_id) if srv_id else None
        subtotal += precio
        items.append(models.VentaItem(
            venta_id=venta_id,
            servicio_id=srv_id,
            nombre_servicio=nombre.strip(),
            precio_cobrado=precio,
            costo_materiales_al_momento=costo_snap,
        ))
        db.add(items[-1])

    if not items or subtotal <= 0:
        request.session["flash"] = "Total inválido."
        request.session["flash_type"] = "error"
        return RedirectResponse(url=f"/ventas/{venta_id}/editar", status_code=303)

    descuento_monto = _calcular_descuento(subtotal, descuento_valor, descuento_tipo)
    total = subtotal - descuento_monto

    venta.cliente_id = cliente_id
    venta.total = total
    venta.forma_pago = forma_pago
    venta.notas = notas
    venta.descuento = descuento_monto
    venta.descuento_tipo = descuento_tipo
    venta.descuento_motivo = descuento_motivo
    db.flush()

    # Nuevos pagos mixtos
    if forma_pago == "mixto":
        metodos = form.getlist("pago_metodo")
        montos_str = form.getlist("pago_monto")
        for metodo, monto_str in zip(metodos, montos_str):
            try:
                monto = float(monto_str or 0)
            except (ValueError, TypeError):
                monto = 0
            if monto > 0 and metodo:
                db.add(models.VentaPago(venta_id=venta_id, metodo=metodo, monto=monto))

    # Reaplicar stock
    _aplicar_stock_items(db, items, venta_id)

    db.commit()
    request.session["flash"] = "✅ Venta actualizada correctamente."
    request.session["flash_type"] = "success"
    return RedirectResponse(url="/ventas", status_code=303)


# ── Asignar cliente ───────────────────────────────────────────────────────────

@router.post("/{venta_id}/asignar-cliente")
def asignar_cliente(venta_id: int, cliente_id: int = Form(...), db: Session = Depends(get_db)):
    venta = db.query(models.Venta).filter_by(id=venta_id).first()
    if not venta:
        raise HTTPException(status_code=404)
    venta.cliente_id = cliente_id
    db.commit()
    return RedirectResponse(url="/ventas", status_code=303)


# ── Caja diaria ───────────────────────────────────────────────────────────────

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

    # Totalizar por método de pago (incluyendo mixtos)
    por_forma = {}
    for v in ventas:
        if v.forma_pago == "mixto" and v.pagos:
            for p in v.pagos:
                por_forma[p.metodo] = por_forma.get(p.metodo, 0) + p.monto
        else:
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


# ── Eliminar venta ────────────────────────────────────────────────────────────

@router.post("/{venta_id}/eliminar")
def eliminar_venta(request: Request, venta_id: int, db: Session = Depends(get_db)):
    venta = db.query(models.Venta).filter_by(id=venta_id).first()
    if not venta:
        raise HTTPException(status_code=404)
    _revertir_stock_venta(db, venta_id)
    db.delete(venta)
    db.commit()
    request.session["flash"] = "Venta eliminada."
    request.session["flash_type"] = "info"
    return RedirectResponse(url="/ventas", status_code=303)

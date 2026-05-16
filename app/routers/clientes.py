from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta
from app.database import get_db
from app import models
from app.utils import verify_admin_token

router = APIRouter(prefix="/clientes", tags=["clientes"])
templates = Jinja2Templates(directory="app/templates")


def _clientes_con_cumpleanos_hoy(db: Session) -> list:
    hoy = date.today()
    todos = db.query(models.Cliente).filter(
        models.Cliente.activo == True,
        models.Cliente.fecha_nacimiento != None,
    ).all()
    return [c for c in todos if
            c.fecha_nacimiento.month == hoy.month and
            c.fecha_nacimiento.day == hoy.day]


def _clientes_inactivos(db: Session, dias: int = 60) -> list:
    """Clientes que no vinieron en los últimos `dias` días."""
    umbral = datetime.now() - timedelta(days=dias)
    # Subquery: última venta por cliente
    sq = (
        db.query(
            models.Venta.cliente_id,
            func.max(models.Venta.fecha_hora).label("ultima")
        )
        .group_by(models.Venta.cliente_id)
        .subquery()
    )
    inactivos = (
        db.query(models.Cliente)
        .join(sq, models.Cliente.id == sq.c.cliente_id)
        .filter(
            models.Cliente.activo == True,
            sq.c.ultima < umbral,
        )
        .order_by(sq.c.ultima)
        .all()
    )
    # Agregar última_visita como atributo
    for c in inactivos:
        ultima = db.query(func.max(models.Venta.fecha_hora)).filter_by(
            cliente_id=c.id
        ).scalar()
        c._ultima_visita = ultima
        c._dias_sin_visitar = (datetime.now() - ultima).days if ultima else 999
    return inactivos


@router.get("/", response_class=HTMLResponse)
def lista_clientes(
    request: Request,
    q: str = "",
    vista: str = "activos",   # activos | inactivos | cumpleanos
    db: Session = Depends(get_db),
):
    cumple_hoy = _clientes_con_cumpleanos_hoy(db)

    if vista == "inactivos":
        clientes = _clientes_inactivos(db, dias=60)
    elif vista == "cumpleanos":
        clientes = cumple_hoy
    else:
        query = db.query(models.Cliente).filter(models.Cliente.activo == True)
        if q:
            query = query.filter(models.Cliente.nombre.ilike(f"%{q}%"))
        clientes = query.order_by(models.Cliente.nombre).all()

    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")

    return templates.TemplateResponse("clientes/list.html", {
        "request": request,
        "clientes": clientes,
        "q": q,
        "vista": vista,
        "cumple_hoy_count": len(cumple_hoy),
        "flash_msg": flash_msg,
        "flash_type": flash_type,
    })


@router.get("/nuevo", response_class=HTMLResponse)
def form_nuevo(request: Request):
    return templates.TemplateResponse("clientes/form.html", {
        "request": request, "cliente": None, "titulo": "Nuevo cliente"
    })


@router.post("/nuevo")
async def crear_cliente(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    nombre = form.get("nombre", "").strip()
    if not nombre:
        request.session["flash"] = "El nombre es obligatorio."
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/clientes/nuevo", status_code=303)

    fecha_nacimiento = form.get("fecha_nacimiento", "")
    try:
        fn = date.fromisoformat(fecha_nacimiento) if fecha_nacimiento else None
    except ValueError:
        fn = None

    c = models.Cliente(
        nombre=nombre,
        telefono=form.get("telefono", ""),
        fecha_nacimiento=fn,
        notas=form.get("notas", ""),
        color_favorito=form.get("color_favorito", ""),
        tipo_una=form.get("tipo_una", ""),
        alergias=form.get("alergias", ""),
        preferencias=form.get("preferencias", ""),
    )
    db.add(c)
    db.commit()
    request.session["flash"] = f"✅ Cliente {nombre} creado."
    request.session["flash_type"] = "success"
    return RedirectResponse(url=f"/clientes/{c.id}", status_code=303)


@router.get("/{cliente_id}", response_class=HTMLResponse)
def detalle_cliente(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter_by(id=cliente_id, activo=True).first()
    if not cliente:
        raise HTTPException(status_code=404)
    ventas = (
        db.query(models.Venta)
        .filter_by(cliente_id=cliente_id)
        .order_by(models.Venta.fecha_hora.desc())
        .all()
    )
    total_gastado = sum(v.total for v in ventas)

    # Próximos turnos
    ahora = datetime.utcnow()
    turnos_proximos = (
        db.query(models.Turno)
        .filter(
            models.Turno.cliente_id == cliente_id,
            models.Turno.fecha_hora_inicio >= ahora,
            models.Turno.estado.in_(["pendiente", "confirmado"]),
        )
        .order_by(models.Turno.fecha_hora_inicio)
        .limit(3)
        .all()
    )

    # Fidelización
    cfg_fidelizacion = db.query(models.ConfiguracionFidelizacion).filter_by(id=1).first()
    visitas_para_beneficio = cfg_fidelizacion.visitas_para_beneficio if cfg_fidelizacion else 10
    progreso_fidelidad = len(ventas) % visitas_para_beneficio if visitas_para_beneficio > 0 else 0
    pct_fidelidad = round(progreso_fidelidad / visitas_para_beneficio * 100) if visitas_para_beneficio > 0 else 0

    # Estadísticas de servicios favoritos
    from collections import Counter
    items_nombres = [i.nombre_servicio for v in ventas for i in v.items]
    servicios_favoritos = Counter(items_nombres).most_common(5)

    # Días desde última visita
    ultima_visita = ventas[0].fecha_hora if ventas else None
    dias_sin_visitar = (datetime.utcnow() - ultima_visita).days if ultima_visita else None

    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")

    return templates.TemplateResponse("clientes/detail.html", {
        "request": request,
        "cliente": cliente,
        "ventas": ventas,
        "total_gastado": total_gastado,
        "turnos_proximos": turnos_proximos,
        "progreso_fidelidad": progreso_fidelidad,
        "visitas_para_beneficio": visitas_para_beneficio,
        "pct_fidelidad": pct_fidelidad,
        "servicios_favoritos": servicios_favoritos,
        "dias_sin_visitar": dias_sin_visitar,
        "ultima_visita": ultima_visita,
        "flash_msg": flash_msg,
        "flash_type": flash_type,
    })


@router.get("/{cliente_id}/editar", response_class=HTMLResponse)
def form_editar(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter_by(id=cliente_id, activo=True).first()
    if not cliente:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("clientes/form.html", {
        "request": request, "cliente": cliente, "titulo": "Editar cliente"
    })


@router.post("/{cliente_id}/editar")
async def actualizar_cliente(
    cliente_id: int, request: Request, db: Session = Depends(get_db)
):
    cliente = db.query(models.Cliente).filter_by(id=cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404)

    form = await request.form()
    cliente.nombre = form.get("nombre", cliente.nombre).strip()
    cliente.telefono = form.get("telefono", "")

    fecha_nacimiento = form.get("fecha_nacimiento", "")
    try:
        cliente.fecha_nacimiento = date.fromisoformat(fecha_nacimiento) if fecha_nacimiento else None
    except ValueError:
        pass

    cliente.notas = form.get("notas", "")
    cliente.color_favorito = form.get("color_favorito", "")
    cliente.tipo_una = form.get("tipo_una", "")
    cliente.alergias = form.get("alergias", "")
    cliente.preferencias = form.get("preferencias", "")

    db.commit()
    request.session["flash"] = "✅ Cliente actualizado."
    request.session["flash_type"] = "success"
    return RedirectResponse(url=f"/clientes/{cliente_id}", status_code=303)


@router.post("/{cliente_id}/reset-beneficio")
def reset_beneficio(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    """Marca el beneficio como usado."""
    cliente = db.query(models.Cliente).filter_by(id=cliente_id).first()
    if cliente:
        cliente.beneficio_disponible = False
        db.commit()
    request.session["flash"] = "Beneficio marcado como utilizado."
    request.session["flash_type"] = "info"
    return RedirectResponse(url=f"/clientes/{cliente_id}", status_code=303)


@router.post("/{cliente_id}/eliminar")
def eliminar_cliente(
    cliente_id: int,
    request: Request,
    admin_token: str = Form(""),
    db: Session = Depends(get_db),
):
    if not verify_admin_token(db, admin_token):
        return RedirectResponse(url=f"/clientes/{cliente_id}/editar", status_code=303)
    cliente = db.query(models.Cliente).filter_by(id=cliente_id).first()
    if cliente:
        cliente.activo = False
        db.commit()
    return RedirectResponse(url="/clientes", status_code=303)

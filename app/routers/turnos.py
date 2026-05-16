"""
Router de agenda de turnos con sincronización a Google Calendar.
"""
import json
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
import app.google_calendar as gcal

router = APIRouter(prefix="/turnos", tags=["turnos"])
templates = Jinja2Templates(directory="app/templates")

ESTADOS = ["pendiente", "confirmado", "realizado", "cancelado"]

ESTADO_COLOR = {
    "pendiente":  "#F59E0B",
    "confirmado": "#10B981",
    "realizado":  "#64748B",
    "cancelado":  "#EF4444",
}

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ar_now() -> datetime:
    """Datetime local argentina (UTC-3)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)


def _parse_dt(dt_str: str) -> Optional[datetime]:
    """Parsea un string datetime-local de HTML (YYYY-MM-DDTHH:MM) a datetime naive."""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _ar_to_utc(dt: datetime) -> datetime:
    """Convierte datetime Argentina (UTC-3) a UTC."""
    return dt + timedelta(hours=3)


def _utc_to_ar(dt: datetime) -> datetime:
    """Convierte datetime UTC a Argentina (UTC-3)."""
    return dt - timedelta(hours=3)


def _get_semana(semana_str: str = "") -> tuple[date, date]:
    """Retorna (lunes, domingo) de la semana dada o la semana actual."""
    if semana_str:
        try:
            ref = date.fromisoformat(semana_str)
        except ValueError:
            ref = date.today()
    else:
        ref = date.today()
    lunes = ref - timedelta(days=ref.weekday())
    domingo = lunes + timedelta(days=6)
    return lunes, domingo


# ── Lista / Calendario ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def calendario_turnos(request: Request, semana: str = "", db: Session = Depends(get_db)):
    lunes, domingo = _get_semana(semana)
    lunes_dt = datetime(lunes.year, lunes.month, lunes.day)
    domingo_dt = datetime(domingo.year, domingo.month, domingo.day, 23, 59, 59)

    # Turnos de la semana (en UTC, convertir para mostrar)
    lunes_utc = _ar_to_utc(lunes_dt)
    domingo_utc = _ar_to_utc(domingo_dt)

    turnos = (
        db.query(models.Turno)
        .filter(
            models.Turno.fecha_hora_inicio >= lunes_utc,
            models.Turno.fecha_hora_inicio <= domingo_utc,
        )
        .order_by(models.Turno.fecha_hora_inicio)
        .all()
    )

    # Estructurar turnos para la grilla (hora_inicio_ar, hora_fin_ar)
    turnos_data = []
    for t in turnos:
        inicio_ar = _utc_to_ar(t.fecha_hora_inicio)
        fin_ar = _utc_to_ar(t.fecha_hora_fin)
        # Calcular posición en grilla: desde las 08:00, cada fila = 15 min
        minutos_desde_8 = (inicio_ar.hour - 8) * 60 + inicio_ar.minute
        duracion_min = int((fin_ar - inicio_ar).total_seconds() / 60)
        dia_semana = inicio_ar.weekday()  # 0=lunes

        turnos_data.append({
            "turno": t,
            "inicio_ar": inicio_ar,
            "fin_ar": fin_ar,
            "dia_semana": dia_semana,
            "minutos_desde_8": max(0, minutos_desde_8),
            "duracion_min": max(15, duracion_min),
            "color": ESTADO_COLOR.get(t.estado, "#94A3B8"),
            "cliente_nombre": t.cliente.nombre if t.cliente else "Sin cliente",
        })

    # Días de la semana con sus fechas
    dias = []
    for i in range(7):
        d = lunes + timedelta(days=i)
        dias.append({
            "fecha": d,
            "nombre": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"][i],
            "es_hoy": d == date.today(),
        })

    # Horas de la grilla (08:00 a 21:00)
    horas = [f"{h:02d}:00" for h in range(8, 22)]

    semana_anterior = (lunes - timedelta(days=7)).isoformat()
    semana_siguiente = (lunes + timedelta(days=7)).isoformat()

    gcal_connected = gcal.is_connected(db)

    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")

    return templates.TemplateResponse("turnos/calendario.html", {
        "request": request,
        "dias": dias,
        "horas": horas,
        "turnos_data": turnos_data,
        "lunes": lunes,
        "domingo": domingo,
        "semana_anterior": semana_anterior,
        "semana_siguiente": semana_siguiente,
        "semana_actual": date.today().isoformat(),
        "gcal_connected": gcal_connected,
        "flash_msg": flash_msg,
        "flash_type": flash_type,
    })


@router.get("/lista", response_class=HTMLResponse)
def lista_turnos(
    request: Request,
    desde: str = "",
    hasta: str = "",
    estado: str = "",
    cliente_id: str = "",
    db: Session = Depends(get_db),
):
    hoy = date.today()
    try:
        d_desde = date.fromisoformat(desde) if desde else hoy
    except ValueError:
        d_desde = hoy
    try:
        d_hasta = date.fromisoformat(hasta) if hasta else hoy
    except ValueError:
        d_hasta = hoy

    inicio_utc = _ar_to_utc(datetime(d_desde.year, d_desde.month, d_desde.day))
    fin_utc = _ar_to_utc(datetime(d_hasta.year, d_hasta.month, d_hasta.day, 23, 59, 59))

    query = db.query(models.Turno).filter(
        models.Turno.fecha_hora_inicio >= inicio_utc,
        models.Turno.fecha_hora_inicio <= fin_utc,
    )
    if estado:
        query = query.filter(models.Turno.estado == estado)
    if cliente_id and cliente_id.isdigit():
        query = query.filter(models.Turno.cliente_id == int(cliente_id))

    turnos = query.order_by(models.Turno.fecha_hora_inicio).all()

    # Enriquecer con hora AR
    for t in turnos:
        t._inicio_ar = _utc_to_ar(t.fecha_hora_inicio)
        t._fin_ar = _utc_to_ar(t.fecha_hora_fin)

    clientes = db.query(models.Cliente).filter_by(activo=True).order_by(models.Cliente.nombre).all()

    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")

    return templates.TemplateResponse("turnos/lista.html", {
        "request": request,
        "turnos": turnos,
        "clientes": clientes,
        "estados": ESTADOS,
        "filtro_desde": d_desde.isoformat(),
        "filtro_hasta": d_hasta.isoformat(),
        "filtro_estado": estado,
        "filtro_cliente_id": cliente_id,
        "flash_msg": flash_msg,
        "flash_type": flash_type,
    })


# ── Nuevo Turno ───────────────────────────────────────────────────────────────

@router.get("/nuevo", response_class=HTMLResponse)
def form_nuevo_turno(
    request: Request,
    fecha: str = "",
    hora: str = "",
    db: Session = Depends(get_db),
):
    clientes = db.query(models.Cliente).filter_by(activo=True).order_by(models.Cliente.nombre).all()
    servicios = db.query(models.Servicio).filter_by(activo=True).order_by(models.Servicio.nombre).all()

    # Pre-cargar fecha/hora si vienen del calendario
    datetime_default = ""
    if fecha and hora:
        datetime_default = f"{fecha}T{hora}"
    elif fecha:
        datetime_default = f"{fecha}T09:00"

    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")

    return templates.TemplateResponse("turnos/form.html", {
        "request": request,
        "turno": None,
        "titulo": "Nuevo Turno",
        "clientes": clientes,
        "servicios": servicios,
        "datetime_default": datetime_default,
        "estados": ESTADOS,
        "flash_msg": flash_msg,
        "flash_type": flash_type,
    })


@router.post("/nuevo")
async def crear_turno(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    cliente_id = form.get("cliente_id") or None
    if cliente_id:
        cliente_id = int(cliente_id)

    inicio_str = form.get("fecha_hora_inicio", "")
    fin_str = form.get("fecha_hora_fin", "")
    estado = form.get("estado", "pendiente")
    notas = form.get("notas", "")
    servicios_ids_list = form.getlist("servicios_ids")

    inicio_ar = _parse_dt(inicio_str)
    fin_ar = _parse_dt(fin_str)

    if not inicio_ar or not fin_ar or fin_ar <= inicio_ar:
        request.session["flash"] = "Fecha y hora inválidas. El fin debe ser posterior al inicio."
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/turnos/nuevo", status_code=303)

    # Convertir a UTC para guardar
    inicio_utc = _ar_to_utc(inicio_ar)
    fin_utc = _ar_to_utc(fin_ar)

    # Nombres de servicios para snapshot
    nombres_servicios = []
    for sid in servicios_ids_list:
        s = db.query(models.Servicio).filter_by(id=int(sid)).first()
        if s:
            nombres_servicios.append(s.nombre)

    turno = models.Turno(
        cliente_id=cliente_id,
        fecha_hora_inicio=inicio_utc,
        fecha_hora_fin=fin_utc,
        servicios_ids=json.dumps([int(s) for s in servicios_ids_list]),
        servicios_nombres=", ".join(nombres_servicios),
        estado=estado,
        notas=notas,
    )
    db.add(turno)
    db.flush()

    # Sync Google Calendar
    if gcal.is_connected(db):
        event_id = gcal.create_event(db, turno)
        if event_id:
            turno.gcal_event_id = event_id

    db.commit()

    # Calcular semana del turno para redirigir al calendario en esa semana
    lunes = inicio_ar.date() - timedelta(days=inicio_ar.weekday())
    request.session["flash"] = "✅ Turno creado correctamente."
    request.session["flash_type"] = "success"
    return RedirectResponse(url=f"/turnos?semana={lunes.isoformat()}", status_code=303)


# ── Editar Turno ──────────────────────────────────────────────────────────────

@router.get("/{turno_id}/editar", response_class=HTMLResponse)
def form_editar_turno(turno_id: int, request: Request, db: Session = Depends(get_db)):
    turno = db.query(models.Turno).filter_by(id=turno_id).first()
    if not turno:
        raise HTTPException(status_code=404)

    clientes = db.query(models.Cliente).filter_by(activo=True).order_by(models.Cliente.nombre).all()
    servicios = db.query(models.Servicio).filter_by(activo=True).order_by(models.Servicio.nombre).all()

    # Convertir a AR para el form
    inicio_ar = _utc_to_ar(turno.fecha_hora_inicio)
    fin_ar = _utc_to_ar(turno.fecha_hora_fin)
    turno._inicio_ar_str = inicio_ar.strftime("%Y-%m-%dT%H:%M")
    turno._fin_ar_str = fin_ar.strftime("%Y-%m-%dT%H:%M")

    try:
        turno._servicios_ids_list = json.loads(turno.servicios_ids or "[]")
    except Exception:
        turno._servicios_ids_list = []

    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")

    return templates.TemplateResponse("turnos/form.html", {
        "request": request,
        "turno": turno,
        "titulo": "Editar Turno",
        "clientes": clientes,
        "servicios": servicios,
        "estados": ESTADOS,
        "flash_msg": flash_msg,
        "flash_type": flash_type,
    })


@router.post("/{turno_id}/editar")
async def actualizar_turno(turno_id: int, request: Request, db: Session = Depends(get_db)):
    turno = db.query(models.Turno).filter_by(id=turno_id).first()
    if not turno:
        raise HTTPException(status_code=404)

    form = await request.form()
    cliente_id = form.get("cliente_id") or None
    if cliente_id:
        cliente_id = int(cliente_id)

    inicio_ar = _parse_dt(form.get("fecha_hora_inicio", ""))
    fin_ar = _parse_dt(form.get("fecha_hora_fin", ""))

    if not inicio_ar or not fin_ar or fin_ar <= inicio_ar:
        request.session["flash"] = "Fecha y hora inválidas."
        request.session["flash_type"] = "error"
        return RedirectResponse(url=f"/turnos/{turno_id}/editar", status_code=303)

    servicios_ids_list = form.getlist("servicios_ids")
    nombres_servicios = []
    for sid in servicios_ids_list:
        s = db.query(models.Servicio).filter_by(id=int(sid)).first()
        if s:
            nombres_servicios.append(s.nombre)

    turno.cliente_id = cliente_id
    turno.fecha_hora_inicio = _ar_to_utc(inicio_ar)
    turno.fecha_hora_fin = _ar_to_utc(fin_ar)
    turno.servicios_ids = json.dumps([int(s) for s in servicios_ids_list])
    turno.servicios_nombres = ", ".join(nombres_servicios)
    turno.estado = form.get("estado", turno.estado)
    turno.notas = form.get("notas", "")

    db.commit()

    # Sync GCal
    if gcal.is_connected(db):
        gcal.update_event(db, turno)

    lunes = inicio_ar.date() - timedelta(days=inicio_ar.weekday())
    request.session["flash"] = "✅ Turno actualizado."
    request.session["flash_type"] = "success"
    return RedirectResponse(url=f"/turnos?semana={lunes.isoformat()}", status_code=303)


# ── Acciones de estado ────────────────────────────────────────────────────────

@router.post("/{turno_id}/confirmar")
def confirmar_turno(turno_id: int, request: Request, db: Session = Depends(get_db)):
    turno = db.query(models.Turno).filter_by(id=turno_id).first()
    if not turno:
        raise HTTPException(status_code=404)
    turno.estado = "confirmado"
    db.commit()
    if gcal.is_connected(db):
        gcal.update_event(db, turno)
    request.session["flash"] = "✅ Turno confirmado."
    request.session["flash_type"] = "success"
    return RedirectResponse(url="/turnos/lista", status_code=303)


@router.post("/{turno_id}/cancelar")
def cancelar_turno(turno_id: int, request: Request, db: Session = Depends(get_db)):
    turno = db.query(models.Turno).filter_by(id=turno_id).first()
    if not turno:
        raise HTTPException(status_code=404)
    turno.estado = "cancelado"
    db.commit()
    if gcal.is_connected(db):
        gcal.update_event(db, turno)
    request.session["flash"] = "Turno cancelado."
    request.session["flash_type"] = "info"
    return RedirectResponse(url="/turnos/lista", status_code=303)


@router.post("/{turno_id}/realizar")
def realizar_turno(turno_id: int, request: Request, db: Session = Depends(get_db)):
    """Marca el turno como realizado y redirige a nueva venta pre-cargada."""
    turno = db.query(models.Turno).filter_by(id=turno_id).first()
    if not turno:
        raise HTTPException(status_code=404)
    turno.estado = "realizado"
    db.commit()
    if gcal.is_connected(db):
        gcal.update_event(db, turno)

    # Redirigir a nueva venta pre-cargando cliente y servicios del turno
    params = []
    if turno.cliente_id:
        params.append(f"cliente_id={turno.cliente_id}")
    try:
        sids = json.loads(turno.servicios_ids or "[]")
        for sid in sids:
            params.append(f"servicio_id={sid}")
    except Exception:
        pass
    params.append(f"turno_id={turno_id}")
    qs = "&".join(params)
    return RedirectResponse(url=f"/ventas/nueva?{qs}", status_code=303)


@router.post("/{turno_id}/eliminar")
def eliminar_turno(turno_id: int, request: Request, db: Session = Depends(get_db)):
    turno = db.query(models.Turno).filter_by(id=turno_id).first()
    if not turno:
        raise HTTPException(status_code=404)
    if turno.gcal_event_id and gcal.is_connected(db):
        gcal.delete_event(db, turno.gcal_event_id)
    db.delete(turno)
    db.commit()
    request.session["flash"] = "Turno eliminado."
    request.session["flash_type"] = "info"
    return RedirectResponse(url="/turnos/lista", status_code=303)

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.utils import (
    get_costo_fijo_por_hora, get_rentabilidad_servicio, get_punto_equilibrio,
    verify_admin_token,
)

router = APIRouter(tags=["costos"])
templates = Jinja2Templates(directory="app/templates")

CATEGORIAS_COSTO = ["local", "servicios", "personal", "otros"]


# ── Página principal HTML ─────────────────────────────────────────────────────

@router.get("/costos", response_class=HTMLResponse)
def pagina_costos(request: Request, db: Session = Depends(get_db)):
    costos = db.query(models.CostoFijo).filter_by(activo=True).order_by(models.CostoFijo.categoria, models.CostoFijo.nombre).all()
    config = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    total_mensual = sum(c.monto for c in costos)
    costo_hora = get_costo_fijo_por_hora(db)
    has_pin = bool(config and config.admin_pin_hash)
    return templates.TemplateResponse("costos/index.html", {
        "request": request,
        "costos": costos,
        "config": config,
        "total_mensual": total_mensual,
        "costo_hora": costo_hora,
        "categorias": CATEGORIAS_COSTO,
        "has_pin": has_pin,
    })


@router.post("/costos/set-pin")
def guardar_pin(
    pin_nuevo: str = Form(...),
    pin_confirmar: str = Form(...),
    admin_token: str = Form(""),
    db: Session = Depends(get_db),
):
    cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    if cfg and cfg.admin_pin_hash:
        # Ya tiene PIN → requiere token de admin para cambiarlo
        if not verify_admin_token(db, admin_token):
            return RedirectResponse(url="/costos", status_code=303)
    if pin_nuevo != pin_confirmar or len(pin_nuevo) < 4:
        return RedirectResponse(url="/costos", status_code=303)
    if not cfg:
        cfg = models.ConfiguracionNegocio(id=1)
        db.add(cfg)
    cfg.admin_pin_hash = hashlib.sha256(pin_nuevo.encode()).hexdigest()
    # Invalidar sesión activa al cambiar PIN
    cfg.admin_token = None
    cfg.admin_token_expiry = None
    db.commit()
    return RedirectResponse(url="/costos", status_code=303)


@router.post("/costos/nuevo")
def crear_costo(
    nombre: str = Form(...),
    monto: float = Form(...),
    categoria: str = Form("general"),
    admin_token: str = Form(""),
    db: Session = Depends(get_db),
):
    if not verify_admin_token(db, admin_token):
        return RedirectResponse(url="/costos", status_code=303)
    db.add(models.CostoFijo(nombre=nombre.strip(), monto=monto, categoria=categoria))
    db.commit()
    return RedirectResponse(url="/costos", status_code=303)


@router.post("/costos/{costo_id}/editar")
def editar_costo(
    costo_id: int,
    nombre: str = Form(...),
    monto: float = Form(...),
    categoria: str = Form("general"),
    admin_token: str = Form(""),
    db: Session = Depends(get_db),
):
    if not verify_admin_token(db, admin_token):
        return RedirectResponse(url="/costos", status_code=303)
    c = db.query(models.CostoFijo).filter_by(id=costo_id).first()
    if not c:
        raise HTTPException(status_code=404)
    c.nombre = nombre.strip()
    c.monto = monto
    c.categoria = categoria
    db.commit()
    return RedirectResponse(url="/costos", status_code=303)


@router.post("/costos/{costo_id}/eliminar")
def eliminar_costo(
    costo_id: int,
    admin_token: str = Form(""),
    db: Session = Depends(get_db),
):
    if not verify_admin_token(db, admin_token):
        return RedirectResponse(url="/costos", status_code=303)
    c = db.query(models.CostoFijo).filter_by(id=costo_id).first()
    if c:
        c.activo = False
        db.commit()
    return RedirectResponse(url="/costos", status_code=303)


@router.post("/costos/configuracion")
def guardar_configuracion(
    dias_trabajo_mes: int = Form(22),
    horas_dia: float = Form(7.0),
    pct_ocupacion: float = Form(75),
    admin_token: str = Form(""),
    db: Session = Depends(get_db),
):
    if not verify_admin_token(db, admin_token):
        return RedirectResponse(url="/costos", status_code=303)
    cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    if not cfg:
        cfg = models.ConfiguracionNegocio(id=1)
        db.add(cfg)
    cfg.dias_trabajo_mes = max(1, min(dias_trabajo_mes, 31))
    cfg.horas_dia = max(0.5, min(horas_dia, 24))
    cfg.pct_ocupacion = max(0.01, min(pct_ocupacion / 100, 1.0))
    db.commit()
    return RedirectResponse(url="/costos", status_code=303)


# ── API Admin ─────────────────────────────────────────────────────────────────

@router.get("/api/admin/status")
def admin_status(db: Session = Depends(get_db)):
    cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    return {"has_pin": bool(cfg and cfg.admin_pin_hash)}


@router.post("/api/admin/login")
async def admin_login(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    pin = str(data.get("pin", ""))
    cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    if not cfg or not cfg.admin_pin_hash:
        return JSONResponse({"error": "no_pin"}, status_code=400)
    if hashlib.sha256(pin.encode()).hexdigest() != cfg.admin_pin_hash:
        return JSONResponse({"error": "invalid"}, status_code=401)
    token = secrets.token_hex(32)
    cfg.admin_token = token
    cfg.admin_token_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)
    db.commit()
    return {"token": token, "expires_in": 1800}


@router.post("/api/admin/logout")
def admin_logout(db: Session = Depends(get_db)):
    cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    if cfg:
        cfg.admin_token = None
        cfg.admin_token_expiry = None
        db.commit()
    return {"ok": True}


# ── API JSON ──────────────────────────────────────────────────────────────────

@router.get("/api/costos-fijos")
def api_lista_costos(db: Session = Depends(get_db)):
    costos = db.query(models.CostoFijo).filter_by(activo=True).all()
    return [{"id": c.id, "nombre": c.nombre, "monto": c.monto, "categoria": c.categoria} for c in costos]


@router.post("/api/costos-fijos")
async def api_crear_costo(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    c = models.CostoFijo(nombre=data["nombre"], monto=data["monto"], categoria=data.get("categoria", "general"))
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "nombre": c.nombre, "monto": c.monto, "categoria": c.categoria}


@router.put("/api/costos-fijos/{costo_id}")
async def api_editar_costo(costo_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.query(models.CostoFijo).filter_by(id=costo_id).first()
    if not c:
        raise HTTPException(status_code=404)
    data = await request.json()
    c.nombre = data.get("nombre", c.nombre)
    c.monto = data.get("monto", c.monto)
    c.categoria = data.get("categoria", c.categoria)
    db.commit()
    return {"id": c.id, "nombre": c.nombre, "monto": c.monto, "categoria": c.categoria}


@router.delete("/api/costos-fijos/{costo_id}")
def api_eliminar_costo(costo_id: int, db: Session = Depends(get_db)):
    c = db.query(models.CostoFijo).filter_by(id=costo_id).first()
    if not c:
        raise HTTPException(status_code=404)
    c.activo = False
    db.commit()
    return {"ok": True}


@router.get("/api/configuracion-negocio")
def api_get_config(db: Session = Depends(get_db)):
    cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    if not cfg:
        return {"dias_trabajo_mes": 22, "horas_dia": 7.0, "pct_ocupacion": 0.75}
    return {"dias_trabajo_mes": cfg.dias_trabajo_mes, "horas_dia": cfg.horas_dia, "pct_ocupacion": cfg.pct_ocupacion}


@router.put("/api/configuracion-negocio")
async def api_put_config(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    if not cfg:
        cfg = models.ConfiguracionNegocio(id=1)
        db.add(cfg)
    cfg.dias_trabajo_mes = data.get("dias_trabajo_mes", cfg.dias_trabajo_mes)
    cfg.horas_dia = data.get("horas_dia", cfg.horas_dia)
    cfg.pct_ocupacion = data.get("pct_ocupacion", cfg.pct_ocupacion)
    db.commit()
    return {"ok": True}


@router.get("/api/rentabilidad/resumen")
def api_rentabilidad_resumen(db: Session = Depends(get_db)):
    servicios = db.query(models.Servicio).filter_by(activo=True).all()
    return [get_rentabilidad_servicio(s, db) | {"nombre": s.nombre, "precio": s.precio, "id": s.id}
            for s in servicios]


@router.get("/api/rentabilidad/servicio/{servicio_id}")
def api_rentabilidad_servicio(servicio_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Servicio).filter_by(id=servicio_id, activo=True).first()
    if not s:
        raise HTTPException(status_code=404)
    return get_rentabilidad_servicio(s, db) | {"nombre": s.nombre, "precio": s.precio, "id": s.id}


@router.get("/api/rentabilidad/punto-equilibrio")
def api_punto_equilibrio(db: Session = Depends(get_db)):
    return get_punto_equilibrio(db)

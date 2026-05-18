import os
import shutil
from datetime import date
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text
from app.database import engine
from app import models
from app.routers import (
    clientes, servicios, ventas, stock, dashboard, costos,
    turnos, auth, contabilidad
)
from app.scheduler import crear_scheduler, rotar_pin

# ── Crear tablas ──────────────────────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)

# ── Migraciones inline (columnas nuevas en tablas existentes) ─────────────────
with engine.connect() as _conn:
    for _tabla, _col, _tipo, _default in [
        # Ventas
        ("ventas",           "descuento",                  "REAL",     "0"),
        ("ventas",           "descuento_tipo",              "TEXT",     "'pesos'"),
        ("ventas",           "descuento_motivo",            "TEXT",     "''"),
        # Stock
        ("productos_stock",  "rendimiento_usos",            "REAL",     "1.0"),
        ("productos_stock",  "unidad_rendimiento",          "TEXT",     "'aplicaciones'"),
        # Admin
        ("configuracion_negocio", "admin_pin_hash",         "TEXT",     "NULL"),
        ("configuracion_negocio", "admin_pin_plain",        "TEXT",     "NULL"),
        ("configuracion_negocio", "admin_token",             "TEXT",     "NULL"),
        ("configuracion_negocio", "admin_token_expiry",      "DATETIME", "NULL"),
        # Ficha técnica cliente
        ("clientes",         "color_favorito",              "TEXT",     "''"),
        ("clientes",         "tipo_una",                    "TEXT",     "''"),
        ("clientes",         "alergias",                    "TEXT",     "''"),
        ("clientes",         "preferencias",                "TEXT",     "''"),
        ("clientes",         "beneficio_disponible",        "INTEGER",  "0"),
        # VentaItem snapshot
        ("venta_items",      "costo_materiales_al_momento", "REAL",     "NULL"),
    ]:
        try:
            _conn.execute(text(
                f"ALTER TABLE {_tabla} ADD COLUMN {_col} {_tipo} DEFAULT {_default}"
            ))
            _conn.commit()
        except Exception:
            pass

# ── Datos por defecto ─────────────────────────────────────────────────────────
from app.database import SessionLocal as _Session
from app import models as _models

_db = _Session()
if not _db.query(_models.CategoriaStock).first():
    for _cat in ["General", "Esmaltes", "Solventes", "Gel/Acrílico", "Herramientas", "Insumos"]:
        _db.add(_models.CategoriaStock(nombre=_cat))
    _db.commit()

if not _db.query(_models.ConfiguracionNegocio).first():
    _db.add(_models.ConfiguracionNegocio(id=1))
    _db.commit()

if not _db.query(_models.ConfiguracionFidelizacion).first():
    _db.add(_models.ConfiguracionFidelizacion(id=1))
    _db.commit()

_db.close()

# ── Backup automático diario ──────────────────────────────────────────────────
_DB_PATH = "salon.db"
_hoy_str = date.today().strftime("%Y%m%d")
_backup_hoy = f"salon.db.backup_{_hoy_str}"

if os.path.exists(_DB_PATH) and not os.path.exists(_backup_hoy):
    shutil.copy2(_DB_PATH, _backup_hoy)
    # Mantener solo los últimos 7 backups
    _backups = sorted(
        [f for f in os.listdir(".") if f.startswith("salon.db.backup_")],
        reverse=True,
    )
    for _old in _backups[7:]:
        try:
            os.remove(_old)
        except OSError:
            pass

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Gestión Salón de Manicuría", docs_url=None, redoc_url=None)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "salon-manicura-secret-key-2026"),
    max_age=3600 * 8,   # 8 horas
)

# ── Scheduler: rotación del PIN ───────────────────────────────────────────────
_scheduler = crear_scheduler()

@app.on_event("startup")
async def startup_event():
    _scheduler.start()
    # Si no hay PIN generado todavía, generar uno al arrancar
    from app.database import SessionLocal as _SL
    _db = _SL()
    try:
        _cfg = _db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
        if _cfg and not _cfg.admin_pin_plain:
            rotar_pin()
    finally:
        _db.close()

@app.on_event("shutdown")
async def shutdown_event():
    _scheduler.shutdown(wait=False)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


# ── Filtros Jinja2 ────────────────────────────────────────────────────────────
def fmt_pesos(value):
    """Formatea número como pesos argentinos: $12.500"""
    try:
        return f"${float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


def ar_hora(value):
    """Convierte datetime UTC a hora argentina (UTC-3)."""
    from datetime import timedelta
    try:
        return (value + timedelta(hours=-3)).strftime('%H:%M')
    except Exception:
        return ""


def ar_fecha_hora(value):
    """Convierte datetime UTC a fecha+hora argentina (UTC-3)."""
    from datetime import timedelta
    try:
        return (value + timedelta(hours=-3)).strftime('%d/%m/%Y %H:%M')
    except Exception:
        return ""


def ar_fecha(value):
    """Formatea una fecha como dd/mm/YYYY."""
    try:
        if hasattr(value, 'strftime'):
            return value.strftime('%d/%m/%Y')
        return str(value)
    except Exception:
        return ""


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(dashboard.router)
app.include_router(clientes.router)
app.include_router(servicios.router)
app.include_router(ventas.router)
app.include_router(stock.router)
app.include_router(costos.router)
app.include_router(turnos.router)
app.include_router(auth.router)
app.include_router(contabilidad.router)

# ── Inyectar filtros en todos los routers ─────────────────────────────────────
_ALL_TEMPLATES = [
    clientes.templates, servicios.templates, ventas.templates,
    stock.templates, dashboard.templates, costos.templates,
    turnos.templates, auth.templates, contabilidad.templates,
]
for _t in _ALL_TEMPLATES:
    _t.env.filters["pesos"] = fmt_pesos
    _t.env.filters["ar_hora"] = ar_hora
    _t.env.filters["ar_fecha_hora"] = ar_fecha_hora
    _t.env.filters["ar_fecha"] = ar_fecha

# Inyectar también en el templates de main (usado por buscar.html)
templates.env.filters["pesos"] = fmt_pesos
templates.env.filters["ar_hora"] = ar_hora
templates.env.filters["ar_fecha_hora"] = ar_fecha_hora
templates.env.filters["ar_fecha"] = ar_fecha


# ── Admin backup download ─────────────────────────────────────────────────────
from fastapi.responses import FileResponse
from fastapi import Depends
from app.routers.auth import get_current_admin_user

@app.get("/admin/backup")
def descargar_backup(
    current_admin: models.User = Depends(get_current_admin_user)
):
    """Descarga directa de la base de datos (solo admins autenticados con Google)."""
    if os.path.exists(_DB_PATH):
        nombre = f"salon_backup_{date.today().strftime('%Y%m%d')}.db"
        return FileResponse(_DB_PATH, media_type="application/octet-stream", filename=nombre)
    return {"error": "Base de datos no encontrada"}


# ── Búsqueda global ───────────────────────────────────────────────────────────
from fastapi.responses import HTMLResponse
from app.database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends

@app.get("/buscar", response_class=HTMLResponse)
def buscar_global(request: Request, q: str = "", db: Session = Depends(get_db)):
    if not q or len(q.strip()) < 2:
        return templates.TemplateResponse("buscar.html", {
            "request": request, "q": q, "resultados": None
        })
    patron = f"%{q.strip()}%"
    clientes_r = db.query(models.Cliente).filter(
        models.Cliente.activo == True,
        models.Cliente.nombre.ilike(patron)
    ).limit(10).all()
    servicios_r = db.query(models.Servicio).filter(
        models.Servicio.activo == True,
        models.Servicio.nombre.ilike(patron)
    ).limit(10).all()
    productos_r = db.query(models.ProductoStock).filter(
        models.ProductoStock.activo == True,
        models.ProductoStock.nombre.ilike(patron)
    ).limit(10).all()
    # Buscar venta por ID numérico
    ventas_r = []
    if q.strip().isdigit():
        v = db.query(models.Venta).filter_by(id=int(q.strip())).first()
        if v:
            ventas_r = [v]

    return templates.TemplateResponse("buscar.html", {
        "request": request,
        "q": q,
        "resultados": {
            "clientes": clientes_r,
            "servicios": servicios_r,
            "productos": productos_r,
            "ventas": ventas_r,
        }
    })


# ── Configuración de Fidelización ─────────────────────────────────────────────

@app.get("/configuracion/fidelizacion", response_class=HTMLResponse)
def config_fidelizacion(request: Request, db: Session = Depends(get_db)):
    cfg = db.query(models.ConfiguracionFidelizacion).filter_by(id=1).first()
    if not cfg:
        cfg = models.ConfiguracionFidelizacion(id=1)
        db.add(cfg)
        db.commit()
    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "success")
    return templates.TemplateResponse("configuracion/fidelizacion.html", {
        "request": request, "cfg": cfg,
        "flash_msg": flash_msg, "flash_type": flash_type,
    })


@app.post("/configuracion/fidelizacion")
async def guardar_config_fidelizacion(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    cfg = db.query(models.ConfiguracionFidelizacion).filter_by(id=1).first()
    if not cfg:
        cfg = models.ConfiguracionFidelizacion(id=1)
        db.add(cfg)

    cfg.activo = form.get("activo") == "1"
    try:
        cfg.visitas_para_beneficio = max(1, int(form.get("visitas_para_beneficio", 10)))
    except (ValueError, TypeError):
        cfg.visitas_para_beneficio = 10

    cfg.tipo_beneficio = form.get("tipo_beneficio", "descuento_pct")
    try:
        cfg.valor_beneficio = max(0, float(form.get("valor_beneficio", 10)))
    except (ValueError, TypeError):
        cfg.valor_beneficio = 10.0

    db.commit()
    request.session["flash"] = "✅ Configuración de fidelización actualizada."
    request.session["flash_type"] = "success"
    return RedirectResponse(url="/configuracion/fidelizacion", status_code=303)

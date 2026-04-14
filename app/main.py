from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from app.database import engine
from app import models
from app.routers import clientes, servicios, ventas, stock, dashboard, costos

# Crear tablas si no existen
models.Base.metadata.create_all(bind=engine)

# Sembrar datos por defecto si las tablas están vacías
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
_db.close()

# Migraciones inline para columnas nuevas en tablas existentes
with engine.connect() as _conn:
    for _tabla, _col, _tipo, _default in [
        ("ventas",           "descuento",          "REAL",  "0"),
        ("ventas",           "descuento_tipo",      "TEXT",  "'pesos'"),
        ("ventas",           "descuento_motivo",    "TEXT",  "''"),
        ("productos_stock",  "rendimiento_usos",    "REAL",  "1.0"),
        ("productos_stock",  "unidad_rendimiento",  "TEXT",  "'aplicaciones'"),
    ]:
        try:
            _conn.execute(text(f"ALTER TABLE {_tabla} ADD COLUMN {_col} {_tipo} DEFAULT {_default}"))
            _conn.commit()
        except Exception:
            pass

app = FastAPI(title="Gestión Salón de Manicuría", docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# Registrar filtros de Jinja2
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

templates.env.filters["pesos"] = fmt_pesos
templates.env.filters["ar_hora"] = ar_hora
templates.env.filters["ar_fecha_hora"] = ar_fecha_hora

# Routers
app.include_router(dashboard.router)
app.include_router(clientes.router)
app.include_router(servicios.router)
app.include_router(ventas.router)
app.include_router(stock.router)
app.include_router(costos.router)

# Inyectar el filtro en todos los routers que usan sus propios templates
for r in [clientes.templates, servicios.templates, ventas.templates, stock.templates, dashboard.templates, costos.templates]:
    r.env.filters["pesos"] = fmt_pesos
    r.env.filters["ar_hora"] = ar_hora
    r.env.filters["ar_fecha_hora"] = ar_fecha_hora

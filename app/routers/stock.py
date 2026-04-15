from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.utils import verify_admin_token

router = APIRouter(prefix="/stock", tags=["stock"])
templates = Jinja2Templates(directory="app/templates")


def _get_categorias(db: Session):
    return db.query(models.CategoriaStock).order_by(models.CategoriaStock.nombre).all()


@router.get("/", response_class=HTMLResponse)
def lista_stock(request: Request, db: Session = Depends(get_db)):
    productos = (
        db.query(models.ProductoStock)
        .filter_by(activo=True)
        .order_by(models.ProductoStock.categoria, models.ProductoStock.nombre)
        .all()
    )
    alertas = [p for p in productos if p.cantidad_actual <= p.cantidad_minima]
    cats_usadas = list(dict.fromkeys(p.categoria for p in productos))
    todas_cats = _get_categorias(db)
    return templates.TemplateResponse("stock/list.html", {
        "request": request, "productos": productos, "alertas": alertas,
        "categorias": cats_usadas, "todas_categorias": todas_cats,
    })


@router.get("/nuevo", response_class=HTMLResponse)
def form_nuevo_producto(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("stock/form.html", {
        "request": request, "producto": None, "titulo": "Nuevo producto",
        "categorias": _get_categorias(db),
    })


@router.post("/nuevo")
def crear_producto(
    nombre: str = Form(...),
    categoria: str = Form("General"),
    cantidad_actual: float = Form(0),
    cantidad_minima: float = Form(1),
    costo_unitario: float = Form(0),
    unidad: str = Form("unidad"),
    rendimiento_usos: float = Form(1.0),
    unidad_rendimiento: str = Form("aplicaciones"),
    admin_token: str = Form(""),
    db: Session = Depends(get_db)
):
    if not verify_admin_token(db, admin_token):
        return RedirectResponse(url="/stock", status_code=303)
    p = models.ProductoStock(
        nombre=nombre, categoria=categoria,
        cantidad_actual=cantidad_actual, cantidad_minima=cantidad_minima,
        costo_unitario=costo_unitario, unidad=unidad,
        rendimiento_usos=max(rendimiento_usos, 1),
        unidad_rendimiento=unidad_rendimiento.strip() or "aplicaciones",
    )
    db.add(p)
    db.commit()
    return RedirectResponse(url="/stock", status_code=303)


# ── Categorías ────────────────────────────────────────────────────────────────

@router.post("/categorias/nueva")
def crear_categoria(nombre: str = Form(...), db: Session = Depends(get_db)):
    nombre = nombre.strip()
    if nombre and not db.query(models.CategoriaStock).filter_by(nombre=nombre).first():
        db.add(models.CategoriaStock(nombre=nombre))
        db.commit()
    return RedirectResponse(url="/stock", status_code=303)


@router.post("/categorias/{cat_id}/editar")
def editar_categoria(cat_id: int, nombre: str = Form(...), db: Session = Depends(get_db)):
    cat = db.query(models.CategoriaStock).filter_by(id=cat_id).first()
    if not cat:
        raise HTTPException(status_code=404)
    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse(url="/stock", status_code=303)
    # Renombrar también en productos que la usan
    db.query(models.ProductoStock).filter_by(categoria=cat.nombre).update({"categoria": nombre})
    cat.nombre = nombre
    db.commit()
    return RedirectResponse(url="/stock", status_code=303)


@router.post("/categorias/{cat_id}/eliminar")
def eliminar_categoria(cat_id: int, db: Session = Depends(get_db)):
    cat = db.query(models.CategoriaStock).filter_by(id=cat_id).first()
    if not cat:
        raise HTTPException(status_code=404)
    # Mover productos huérfanos a "General"
    db.query(models.ProductoStock).filter_by(categoria=cat.nombre).update({"categoria": "General"})
    db.delete(cat)
    db.commit()
    return RedirectResponse(url="/stock", status_code=303)


# ── Productos ─────────────────────────────────────────────────────────────────

@router.get("/{producto_id}", response_class=HTMLResponse)
def detalle_producto(producto_id: int, request: Request, db: Session = Depends(get_db)):
    producto = db.query(models.ProductoStock).filter_by(id=producto_id, activo=True).first()
    if not producto:
        raise HTTPException(status_code=404)
    movimientos = (
        db.query(models.StockMovimiento)
        .filter_by(producto_id=producto_id)
        .order_by(models.StockMovimiento.fecha.desc())
        .limit(30)
        .all()
    )
    return templates.TemplateResponse("stock/detail.html", {
        "request": request, "producto": producto, "movimientos": movimientos
    })


@router.get("/{producto_id}/editar", response_class=HTMLResponse)
def form_editar_producto(producto_id: int, request: Request, db: Session = Depends(get_db)):
    producto = db.query(models.ProductoStock).filter_by(id=producto_id, activo=True).first()
    if not producto:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("stock/form.html", {
        "request": request, "producto": producto, "titulo": "Editar producto",
        "categorias": _get_categorias(db),
    })


@router.post("/{producto_id}/editar")
def actualizar_producto(
    producto_id: int,
    nombre: str = Form(...),
    categoria: str = Form("General"),
    cantidad_actual: float = Form(0),
    cantidad_minima: float = Form(1),
    costo_unitario: float = Form(0),
    unidad: str = Form("unidad"),
    rendimiento_usos: float = Form(1.0),
    unidad_rendimiento: str = Form("aplicaciones"),
    admin_token: str = Form(""),
    db: Session = Depends(get_db)
):
    if not verify_admin_token(db, admin_token):
        return RedirectResponse(url="/stock", status_code=303)
    p = db.query(models.ProductoStock).filter_by(id=producto_id).first()
    if not p:
        raise HTTPException(status_code=404)
    p.nombre = nombre
    p.categoria = categoria
    p.cantidad_minima = cantidad_minima
    p.costo_unitario = costo_unitario
    p.unidad = unidad
    p.rendimiento_usos = max(rendimiento_usos, 1)
    p.unidad_rendimiento = unidad_rendimiento.strip() or "aplicaciones"
    diferencia = cantidad_actual - p.cantidad_actual
    if diferencia != 0:
        p.cantidad_actual = cantidad_actual
        db.add(models.StockMovimiento(
            producto_id=producto_id,
            cantidad=diferencia,
            tipo="ajuste",
            descripcion="Ajuste por edición de producto",
        ))
    db.commit()
    return RedirectResponse(url="/stock", status_code=303)


@router.post("/{producto_id}/ajuste")
def ajustar_stock(
    producto_id: int,
    cantidad: float = Form(...),
    descripcion: str = Form("Ajuste manual"),
    admin_token: str = Form(""),
    db: Session = Depends(get_db)
):
    if not verify_admin_token(db, admin_token):
        return RedirectResponse(url=f"/stock/{producto_id}", status_code=303)
    p = db.query(models.ProductoStock).filter_by(id=producto_id).first()
    if not p:
        raise HTTPException(status_code=404)
    p.cantidad_actual = max(0, p.cantidad_actual + cantidad)
    db.add(models.StockMovimiento(
        producto_id=producto_id,
        cantidad=cantidad,
        tipo="ajuste",
        descripcion=descripcion,
    ))
    db.commit()
    return RedirectResponse(url=f"/stock/{producto_id}", status_code=303)


@router.post("/{producto_id}/eliminar")
def eliminar_producto(
    producto_id: int,
    admin_token: str = Form(""),
    db: Session = Depends(get_db),
):
    if not verify_admin_token(db, admin_token):
        return RedirectResponse(url="/stock", status_code=303)
    p = db.query(models.ProductoStock).filter_by(id=producto_id).first()
    if p:
        p.activo = False
        db.commit()
    return RedirectResponse(url="/stock", status_code=303)

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database import get_db
from app import models

router = APIRouter(prefix="/servicios", tags=["servicios"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def lista_servicios(request: Request, db: Session = Depends(get_db)):
    servicios = db.query(models.Servicio).filter_by(activo=True).order_by(models.Servicio.nombre).all()
    combos = db.query(models.Combo).filter_by(activo=True).order_by(models.Combo.nombre).all()
    return templates.TemplateResponse("servicios/list.html", {
        "request": request, "servicios": servicios, "combos": combos
    })


@router.get("/nuevo", response_class=HTMLResponse)
def form_nuevo_servicio(request: Request, db: Session = Depends(get_db)):
    productos = db.query(models.ProductoStock).filter_by(activo=True).all()
    return templates.TemplateResponse("servicios/form.html", {
        "request": request, "servicio": None, "titulo": "Nuevo servicio",
        "productos": productos, "consumos": {}
    })


@router.post("/nuevo")
async def crear_servicio(
    request: Request,
    nombre: str = Form(...),
    precio: float = Form(...),
    duracion_min: int = Form(60),
    descripcion: str = Form(""),
    db: Session = Depends(get_db)
):
    s = models.Servicio(nombre=nombre, precio=precio, duracion_min=duracion_min, descripcion=descripcion)
    db.add(s)
    db.flush()

    form = await request.form()
    for key, val in form.items():
        if key.startswith("prod_") and val:
            try:
                prod_id = int(key.split("_")[1])
                qty = float(val)
            except (ValueError, IndexError):
                continue
            if qty > 0:
                db.add(models.ServicioProducto(servicio_id=s.id, producto_id=prod_id, cantidad_uso=qty))

    db.commit()
    return RedirectResponse(url="/servicios", status_code=303)


@router.get("/{servicio_id}/editar", response_class=HTMLResponse)
def form_editar_servicio(servicio_id: int, request: Request, db: Session = Depends(get_db)):
    servicio = db.query(models.Servicio).filter_by(id=servicio_id, activo=True).first()
    if not servicio:
        raise HTTPException(status_code=404)
    productos = db.query(models.ProductoStock).filter_by(activo=True).all()
    consumos = {sp.producto_id: sp.cantidad_uso for sp in servicio.productos_usados}
    return templates.TemplateResponse("servicios/form.html", {
        "request": request, "servicio": servicio, "titulo": "Editar servicio",
        "productos": productos, "consumos": consumos
    })


@router.post("/{servicio_id}/editar")
async def actualizar_servicio(
    servicio_id: int,
    request: Request,
    nombre: str = Form(...),
    precio: float = Form(...),
    duracion_min: int = Form(60),
    descripcion: str = Form(""),
    db: Session = Depends(get_db)
):
    s = db.query(models.Servicio).filter_by(id=servicio_id).first()
    if not s:
        raise HTTPException(status_code=404)
    s.nombre = nombre
    s.precio = precio
    s.duracion_min = duracion_min
    s.descripcion = descripcion

    # Reemplazar consumos
    db.query(models.ServicioProducto).filter_by(servicio_id=servicio_id).delete()
    form = await request.form()
    for key, val in form.items():
        if key.startswith("prod_") and val:
            try:
                prod_id = int(key.split("_")[1])
                qty = float(val)
            except (ValueError, IndexError):
                continue
            if qty > 0:
                db.add(models.ServicioProducto(servicio_id=s.id, producto_id=prod_id, cantidad_uso=qty))

    db.commit()
    return RedirectResponse(url="/servicios", status_code=303)


@router.post("/{servicio_id}/eliminar")
def eliminar_servicio(servicio_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Servicio).filter_by(id=servicio_id).first()
    if s:
        s.activo = False
        db.commit()
    return RedirectResponse(url="/servicios", status_code=303)


# ─── Combos ───────────────────────────────────────────────────────────────────

@router.get("/combos/nuevo", response_class=HTMLResponse)
def form_nuevo_combo(request: Request, db: Session = Depends(get_db)):
    servicios = db.query(models.Servicio).filter_by(activo=True).all()
    return templates.TemplateResponse("servicios/combo_form.html", {
        "request": request, "combo": None, "titulo": "Nuevo combo",
        "servicios": servicios, "combo_ids": []
    })


@router.post("/combos/nuevo")
async def crear_combo(
    request: Request,
    nombre: str = Form(...),
    precio: float = Form(...),
    descripcion: str = Form(""),
    db: Session = Depends(get_db)
):
    combo = models.Combo(nombre=nombre, precio=precio, descripcion=descripcion)
    db.add(combo)
    db.flush()

    form = await request.form()
    ids = form.getlist("servicio_ids")
    for sid in ids:
        db.add(models.ComboItem(combo_id=combo.id, servicio_id=int(sid)))

    db.commit()
    return RedirectResponse(url="/servicios", status_code=303)


@router.get("/combos/{combo_id}/editar", response_class=HTMLResponse)
def form_editar_combo(combo_id: int, request: Request, db: Session = Depends(get_db)):
    combo = db.query(models.Combo).filter_by(id=combo_id, activo=True).first()
    if not combo:
        raise HTTPException(status_code=404)
    servicios = db.query(models.Servicio).filter_by(activo=True).all()
    combo_ids = [item.servicio_id for item in combo.items]
    return templates.TemplateResponse("servicios/combo_form.html", {
        "request": request, "combo": combo, "titulo": "Editar combo",
        "servicios": servicios, "combo_ids": combo_ids
    })


@router.post("/combos/{combo_id}/editar")
async def actualizar_combo(
    combo_id: int,
    request: Request,
    nombre: str = Form(...),
    precio: float = Form(...),
    descripcion: str = Form(""),
    db: Session = Depends(get_db)
):
    combo = db.query(models.Combo).filter_by(id=combo_id).first()
    if not combo:
        raise HTTPException(status_code=404)
    combo.nombre = nombre
    combo.precio = precio
    combo.descripcion = descripcion

    db.query(models.ComboItem).filter_by(combo_id=combo_id).delete()
    form = await request.form()
    for sid in form.getlist("servicio_ids"):
        db.add(models.ComboItem(combo_id=combo.id, servicio_id=int(sid)))

    db.commit()
    return RedirectResponse(url="/servicios", status_code=303)


@router.post("/combos/{combo_id}/eliminar")
def eliminar_combo(combo_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Combo).filter_by(id=combo_id).first()
    if c:
        c.activo = False
        db.commit()
    return RedirectResponse(url="/servicios", status_code=303)

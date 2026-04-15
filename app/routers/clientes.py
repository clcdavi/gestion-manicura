from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date
from app.database import get_db
from app import models
from app.utils import verify_admin_token

router = APIRouter(prefix="/clientes", tags=["clientes"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def lista_clientes(request: Request, q: str = "", db: Session = Depends(get_db)):
    query = db.query(models.Cliente).filter(models.Cliente.activo == True)
    if q:
        query = query.filter(models.Cliente.nombre.ilike(f"%{q}%"))
    clientes = query.order_by(models.Cliente.nombre).all()
    return templates.TemplateResponse("clientes/list.html", {
        "request": request, "clientes": clientes, "q": q
    })


@router.get("/nuevo", response_class=HTMLResponse)
def form_nuevo(request: Request):
    return templates.TemplateResponse("clientes/form.html", {
        "request": request, "cliente": None, "titulo": "Nuevo cliente"
    })


@router.post("/nuevo")
def crear_cliente(
    request: Request,
    nombre: str = Form(...),
    telefono: str = Form(""),
    fecha_nacimiento: str = Form(""),
    notas: str = Form(""),
    db: Session = Depends(get_db)
):
    try:
        fn = date.fromisoformat(fecha_nacimiento) if fecha_nacimiento else None
    except ValueError:
        fn = None
    c = models.Cliente(nombre=nombre, telefono=telefono, fecha_nacimiento=fn, notas=notas)
    db.add(c)
    db.commit()
    return RedirectResponse(url="/clientes", status_code=303)


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
    return templates.TemplateResponse("clientes/detail.html", {
        "request": request,
        "cliente": cliente,
        "ventas": ventas,
        "total_gastado": total_gastado,
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
def actualizar_cliente(
    cliente_id: int,
    nombre: str = Form(...),
    telefono: str = Form(""),
    fecha_nacimiento: str = Form(""),
    notas: str = Form(""),
    db: Session = Depends(get_db)
):
    cliente = db.query(models.Cliente).filter_by(id=cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404)
    cliente.nombre = nombre
    cliente.telefono = telefono
    try:
        cliente.fecha_nacimiento = date.fromisoformat(fecha_nacimiento) if fecha_nacimiento else None
    except ValueError:
        cliente.fecha_nacimiento = None
    cliente.notas = notas
    db.commit()
    return RedirectResponse(url=f"/clientes/{cliente_id}", status_code=303)


@router.post("/{cliente_id}/eliminar")
def eliminar_cliente(
    cliente_id: int,
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

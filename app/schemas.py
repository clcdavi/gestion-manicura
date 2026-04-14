from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


# ─── Cliente ──────────────────────────────────────────────────────────────────

class ClienteBase(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    notas: Optional[str] = ""


class ClienteCreate(ClienteBase):
    pass


class ClienteOut(ClienteBase):
    id: int
    activo: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Servicio ─────────────────────────────────────────────────────────────────

class ServicioBase(BaseModel):
    nombre: str
    precio: float
    duracion_min: int = 60
    descripcion: Optional[str] = ""


class ServicioCreate(ServicioBase):
    pass


class ServicioOut(ServicioBase):
    id: int
    activo: bool

    class Config:
        from_attributes = True


# ─── Combo ────────────────────────────────────────────────────────────────────

class ComboBase(BaseModel):
    nombre: str
    precio: float
    descripcion: Optional[str] = ""


class ComboCreate(ComboBase):
    servicio_ids: List[int] = []


class ComboOut(ComboBase):
    id: int
    activo: bool

    class Config:
        from_attributes = True


# ─── Producto Stock ───────────────────────────────────────────────────────────

class ProductoBase(BaseModel):
    nombre: str
    categoria: str = "General"
    cantidad_actual: float = 0
    cantidad_minima: float = 1
    costo_unitario: float = 0
    unidad: str = "unidad"


class ProductoCreate(ProductoBase):
    pass


class ProductoOut(ProductoBase):
    id: int
    activo: bool

    class Config:
        from_attributes = True


# ─── Venta ────────────────────────────────────────────────────────────────────

class VentaItemIn(BaseModel):
    servicio_id: Optional[int] = None
    nombre_servicio: str
    precio_cobrado: float


class VentaCreate(BaseModel):
    cliente_id: Optional[int] = None
    forma_pago: str = "efectivo"
    notas: Optional[str] = ""
    items: List[VentaItemIn]


class VentaItemOut(BaseModel):
    id: int
    nombre_servicio: str
    precio_cobrado: float

    class Config:
        from_attributes = True


class VentaOut(BaseModel):
    id: int
    cliente_id: Optional[int]
    fecha_hora: datetime
    total: float
    forma_pago: str
    notas: str
    items: List[VentaItemOut]

    class Config:
        from_attributes = True


# ─── Stock Movimiento ─────────────────────────────────────────────────────────

class AjusteStockIn(BaseModel):
    cantidad: float
    descripcion: str = "Ajuste manual"

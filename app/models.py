from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    telefono = Column(String(20))
    fecha_nacimiento = Column(Date, nullable=True)
    notas = Column(Text, default="")
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)

    ventas = relationship("Venta", back_populates="cliente")


class Servicio(Base):
    __tablename__ = "servicios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    precio = Column(Float, nullable=False)
    duracion_min = Column(Integer, default=60)
    descripcion = Column(Text, default="")
    activo = Column(Boolean, default=True)

    combo_items = relationship("ComboItem", back_populates="servicio")
    venta_items = relationship("VentaItem", back_populates="servicio")
    productos_usados = relationship("ServicioProducto", back_populates="servicio")


class Combo(Base):
    __tablename__ = "combos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    precio = Column(Float, nullable=False)
    descripcion = Column(Text, default="")
    activo = Column(Boolean, default=True)

    items = relationship("ComboItem", back_populates="combo")


class ComboItem(Base):
    __tablename__ = "combo_items"

    id = Column(Integer, primary_key=True)
    combo_id = Column(Integer, ForeignKey("combos.id"), nullable=False)
    servicio_id = Column(Integer, ForeignKey("servicios.id"), nullable=False)

    combo = relationship("Combo", back_populates="items")
    servicio = relationship("Servicio", back_populates="combo_items")


class CategoriaStock(Base):
    __tablename__ = "categorias_stock"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(50), nullable=False, unique=True)


class ProductoStock(Base):
    __tablename__ = "productos_stock"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    categoria = Column(String(50), default="General")
    cantidad_actual = Column(Float, default=0)
    cantidad_minima = Column(Float, default=1)
    costo_unitario = Column(Float, default=0)
    unidad = Column(String(20), default="unidad")
    rendimiento_usos = Column(Float, default=1.0)
    unidad_rendimiento = Column(String(20), default="aplicaciones")
    activo = Column(Boolean, default=True)

    movimientos = relationship("StockMovimiento", back_populates="producto")
    servicios_asociados = relationship("ServicioProducto", back_populates="producto")


class ServicioProducto(Base):
    """Qué productos consume cada servicio y en qué cantidad."""
    __tablename__ = "servicio_productos"

    id = Column(Integer, primary_key=True)
    servicio_id = Column(Integer, ForeignKey("servicios.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos_stock.id"), nullable=False)
    cantidad_uso = Column(Float, default=1)

    servicio = relationship("Servicio", back_populates="productos_usados")
    producto = relationship("ProductoStock", back_populates="servicios_asociados")


class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    fecha_hora = Column(DateTime, default=_now)
    total = Column(Float, nullable=False)
    forma_pago = Column(String(20), default="efectivo")  # efectivo / transferencia / tarjeta / mixto
    notas = Column(Text, default="")

    descuento = Column(Float, default=0)
    descuento_tipo = Column(String(10), default="pesos")  # "pesos" | "porcentaje"
    descuento_motivo = Column(String(200), default="")

    cliente = relationship("Cliente", back_populates="ventas")
    items = relationship("VentaItem", back_populates="venta", cascade="all, delete-orphan")


class VentaItem(Base):
    __tablename__ = "venta_items"

    id = Column(Integer, primary_key=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    servicio_id = Column(Integer, ForeignKey("servicios.id"), nullable=True)
    nombre_servicio = Column(String(100))  # snapshot del nombre al momento de la venta
    precio_cobrado = Column(Float, nullable=False)

    venta = relationship("Venta", back_populates="items")
    servicio = relationship("Servicio", back_populates="venta_items")


class StockMovimiento(Base):
    __tablename__ = "stock_movimientos"

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos_stock.id"), nullable=False)
    cantidad = Column(Float, nullable=False)  # negativo = salida, positivo = entrada
    tipo = Column(String(30), default="ajuste")  # venta / ajuste / compra
    descripcion = Column(String(200), default="")
    fecha = Column(DateTime, default=_now)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=True)

    producto = relationship("ProductoStock", back_populates="movimientos")


class CostoFijo(Base):
    __tablename__ = "costos_fijos"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    monto = Column(Float, nullable=False)
    categoria = Column(String(20), default="general")  # local/servicios/personal/otros
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)


class ConfiguracionNegocio(Base):
    __tablename__ = "configuracion_negocio"

    id = Column(Integer, primary_key=True)
    dias_trabajo_mes = Column(Integer, default=22)
    horas_dia = Column(Float, default=7.0)
    pct_ocupacion = Column(Float, default=0.75)
    admin_pin_hash = Column(String(64), nullable=True)
    admin_token = Column(String(64), nullable=True)
    admin_token_expiry = Column(DateTime, nullable=True)

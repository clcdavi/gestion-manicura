"""
Script de seed: crea la base de datos e inserta datos de ejemplo.
Uso: python seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, date, timedelta
import random
from app.database import engine, SessionLocal
from app import models

# Crear todas las tablas
models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

# ─── Clientes ──────────────────────────────────────────────────────────────────
clientes_data = [
    {"nombre": "Valentina Gómez",    "telefono": "11-4523-8891", "fecha_nacimiento": date(1992, 3, 15), "notas": "Alérgica al formaldehído. Prefiere colores nude."},
    {"nombre": "Luciana Martínez",   "telefono": "11-3892-4471", "fecha_nacimiento": date(1988, 7, 22), "notas": "Le gusta el nail art con piedras. Cliente frecuente."},
    {"nombre": "Sofía Herrera",      "telefono": "11-5541-2233", "fecha_nacimiento": date(1995, 11, 8), "notas": "Uñas cortas, siempre esmaltado oscuro."},
    {"nombre": "Camila Torres",      "telefono": "11-2278-9954", "fecha_nacimiento": date(2000, 1, 30), "notas": ""},
    {"nombre": "Mariana Rodríguez",  "telefono": "11-6612-0087", "fecha_nacimiento": date(1985, 6, 4),  "notas": "Viene siempre con su hija. Piel sensible, usar base protectora."},
]
clientes = []
for d in clientes_data:
    c = models.Cliente(**d)
    db.add(c)
    clientes.append(c)
db.flush()

# ─── Servicios ────────────────────────────────────────────────────────────────
servicios_data = [
    {"nombre": "Manicura simple",           "precio": 3500,  "duracion_min": 45,  "descripcion": "Limado, cutícula y esmaltado común."},
    {"nombre": "Esmaltado semipermanente",  "precio": 8000,  "duracion_min": 60,  "descripcion": "Gel UV, dura 3-4 semanas."},
    {"nombre": "Nail art básico",           "precio": 12000, "duracion_min": 90,  "descripcion": "Diseños simples con esmalte o acrílico."},
    {"nombre": "Kapping completo",          "precio": 22000, "duracion_min": 120, "descripcion": "Uñas acrílicas con tips, forma y esmaltado."},
    {"nombre": "Relleno de kapping",        "precio": 14000, "duracion_min": 90,  "descripcion": "Relleno de la zona de crecimiento."},
    {"nombre": "Pedicura completa",         "precio": 6000,  "duracion_min": 60,  "descripcion": "Exfoliación, cutícula, limado y esmaltado."},
    {"nombre": "Diseño especial",           "precio": 25000, "duracion_min": 150, "descripcion": "Nail art complejo, encapsulado, piedras, etc."},
    {"nombre": "Retiro de acríl. + manicura", "precio": 7500, "duracion_min": 75, "descripcion": "Retiro seguro de kapping + manicura simple."},
]
servicios = []
for d in servicios_data:
    s = models.Servicio(**d)
    db.add(s)
    servicios.append(s)
db.flush()

# ─── Combos ───────────────────────────────────────────────────────────────────
combos_data = [
    {"nombre": "Mani + Pedi Express", "precio": 8500,  "descripcion": "Manicura simple + Pedicura completa.", "idx": [0, 5]},
    {"nombre": "Kapping + Arte",      "precio": 30000, "descripcion": "Kapping completo + Nail art básico.",   "idx": [3, 2]},
    {"nombre": "Semi + Pedicura",     "precio": 12500, "descripcion": "Esmaltado semi en manos + Pedicura.",   "idx": [1, 5]},
]
for d in combos_data:
    combo = models.Combo(nombre=d["nombre"], precio=d["precio"], descripcion=d["descripcion"])
    db.add(combo)
    db.flush()
    for i in d["idx"]:
        db.add(models.ComboItem(combo_id=combo.id, servicio_id=servicios[i].id))

# ─── Productos de Stock ───────────────────────────────────────────────────────
productos_data = [
    {"nombre": "Esmalte semipermanente (set 12u)", "categoria": "Esmaltes",   "cantidad_actual": 8,  "cantidad_minima": 3,  "costo_unitario": 4500,  "unidad": "set"},
    {"nombre": "Esmalte común (set 24u)",          "categoria": "Esmaltes",   "cantidad_actual": 4,  "cantidad_minima": 2,  "costo_unitario": 2800,  "unidad": "set"},
    {"nombre": "Acetona 1L",                       "categoria": "Solventes",  "cantidad_actual": 2,  "cantidad_minima": 2,  "costo_unitario": 1200,  "unidad": "litro"},
    {"nombre": "Gel UV constructor 30ml",          "categoria": "Gel/Acrílico","cantidad_actual": 5, "cantidad_minima": 2,  "costo_unitario": 3500,  "unidad": "pomo"},
    {"nombre": "Tips naturales x100",              "categoria": "Gel/Acrílico","cantidad_actual": 3, "cantidad_minima": 2,  "costo_unitario": 1800,  "unidad": "caja"},
    {"nombre": "Polvo acrílico 30g",               "categoria": "Gel/Acrílico","cantidad_actual": 1, "cantidad_minima": 2,  "costo_unitario": 2200,  "unidad": "pote"},
    {"nombre": "Papel absorbente (rollo)",         "categoria": "Insumos",    "cantidad_actual": 6,  "cantidad_minima": 3,  "costo_unitario": 400,   "unidad": "rollo"},
    {"nombre": "Guantes de látex (caja 100u)",     "categoria": "Insumos",    "cantidad_actual": 2,  "cantidad_minima": 1,  "costo_unitario": 1500,  "unidad": "caja"},
    {"nombre": "Lima de cartón x20",               "categoria": "Herramientas","cantidad_actual": 15, "cantidad_minima": 5, "costo_unitario": 600,   "unidad": "pack"},
    {"nombre": "Base coat / Top coat 15ml",        "categoria": "Esmaltes",   "cantidad_actual": 4,  "cantidad_minima": 2,  "costo_unitario": 1800,  "unidad": "frasco"},
]
productos = []
for d in productos_data:
    p = models.ProductoStock(**d)
    db.add(p)
    productos.append(p)
db.flush()

# Asociar consumos: esmaltado semi consume 1 semi + 1 base; kapping consume gel + tips + acrílico
consumos = [
    (1, 0, 0.1),  # Esmaltado semi → semipermanente
    (1, 9, 0.1),  # Esmaltado semi → base/top
    (3, 3, 0.5),  # Kapping → gel UV
    (3, 4, 0.1),  # Kapping → tips
    (3, 5, 0.2),  # Kapping → polvo acrílico
    (4, 3, 0.3),  # Relleno → gel UV
    (0, 1, 0.1),  # Manicura simple → esmalte común
]
for s_idx, p_idx, qty in consumos:
    db.add(models.ServicioProducto(
        servicio_id=servicios[s_idx].id,
        producto_id=productos[p_idx].id,
        cantidad_uso=qty
    ))

# ─── Ventas (últimos 30 días) ─────────────────────────────────────────────────
random.seed(42)
formas_pago = ["efectivo", "efectivo", "efectivo", "transferencia", "transferencia", "tarjeta"]
hoy = datetime.now()

ventas_config = [
    # (días_atrás, cliente_idx, [servicios_idx], forma_pago)
    (1,  0, [1],    "efectivo"),
    (2,  1, [3],    "transferencia"),
    (3,  2, [0, 5], "efectivo"),
    (5,  3, [1],    "tarjeta"),
    (6,  4, [5],    "transferencia"),
    (8,  0, [2],    "efectivo"),
    (10, 1, [4],    "transferencia"),
    (12, 2, [1],    "efectivo"),
    (14, 3, [6],    "transferencia"),
    (15, 4, [0],    "efectivo"),
    (17, 0, [3, 2], "tarjeta"),
    (20, 1, [1],    "efectivo"),
    (22, 2, [5],    "transferencia"),
    (25, 3, [4],    "efectivo"),
    (28, 4, [7],    "efectivo"),
]

for dias_atras, cli_idx, srv_indices, fp in ventas_config:
    fecha = hoy - timedelta(days=dias_atras)
    items_data = []
    total = 0
    movimientos_pendientes = []  # Se asigna venta_id después del flush

    for si in srv_indices:
        srv = servicios[si]
        items_data.append(models.VentaItem(
            servicio_id=srv.id,
            nombre_servicio=srv.nombre,
            precio_cobrado=srv.precio
        ))
        total += srv.precio

        for sp in servicios[si].productos_usados:
            sp.producto.cantidad_actual = max(0, sp.producto.cantidad_actual - sp.cantidad_uso)
            movimientos_pendientes.append(models.StockMovimiento(
                producto_id=sp.producto.id,
                cantidad=-sp.cantidad_uso,
                tipo="venta",
                descripcion=f"Consumo por {srv.nombre}",
                fecha=fecha,
            ))

    venta = models.Venta(
        cliente_id=clientes[cli_idx].id,
        fecha_hora=fecha,
        total=total,
        forma_pago=fp,
        notas="",
        items=items_data,
    )
    db.add(venta)
    db.flush()  # Obtener venta.id antes de asignarlo a movimientos

    for m in movimientos_pendientes:
        m.venta_id = venta.id
        db.add(m)

db.commit()
db.close()

print("✓ Base de datos creada con éxito: salon.db")
print(f"  • {len(clientes_data)} clientes")
print(f"  • {len(servicios_data)} servicios + 3 combos")
print(f"  • {len(productos_data)} productos de stock")
print(f"  • {len(ventas_config)} ventas de los últimos 30 días")
print()
print("Para iniciar el servidor:")
print("  uvicorn app.main:app --reload")
print("  → http://localhost:8000")

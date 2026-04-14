# Bella Studio — Sistema de Gestión

Sistema de gestión integral para salón de manicuría. Backend Python (FastAPI) + frontend HTML/CSS/JS, base de datos SQLite. Corre completamente local con un solo comando.

## Requisitos

- Python 3.10 o superior
- pip

## Instalación y ejecución

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Crear la base de datos con datos de ejemplo (opcional)
python seed.py

# 3. Iniciar el servidor
uvicorn app.main:app --reload

# 4. Abrir en el navegador
# → http://localhost:8000
```

## Módulos

| Módulo | URL | Descripción |
|--------|-----|-------------|
| Dashboard | `/` | Métricas, gráficos por rango de fechas, rentabilidad por servicio |
| Nueva Venta | `/ventas/nueva` | Registro rápido con descuentos y asignación de cliente |
| Ventas del día | `/ventas` | Listado con filtro por fecha, asignar cliente post-venta |
| Caja diaria | `/ventas/caja` | Resumen imprimible del día |
| Clientes | `/clientes` | CRUD completo + historial de servicios por cliente |
| Servicios | `/servicios` | Catálogo de servicios, combos, y consumo de insumos |
| Stock | `/stock` | Inventario con categorías, alertas de mínimo y proyección |

## Funcionalidades principales

**Ventas**
- Registro rápido desde catálogo de servicios y combos
- Descuentos por monto fijo o porcentaje con comentario
- Asignación de cliente opcional (antes o después de la venta)
- Eliminación con doble confirmación (escribir "ELIMINAR")
- Descuento automático de stock de insumos al registrar una venta

**Dashboard**
- KPIs de ingresos: día, semana y mes
- Gráfico de barras con selector de rango (7 días / 30 días / mes / personalizado)
- Top 5 servicios del mes con ingresos
- Cliente más frecuente del mes
- Distribución de formas de pago
- Proyección de días restantes de stock crítico
- **Análisis de rentabilidad**: margen de ganancia por servicio, alertas de pérdida y recomendaciones de precio

**Stock**
- Categorías dinámicas (crear, editar, eliminar desde la UI)
- Historial de movimientos por producto
- Alertas visuales de stock bajo mínimo
- Ajustes manuales con registro de motivo

**Clientes**
- Búsqueda por nombre
- Historial completo de servicios y total gastado
- Cumpleaños y notas personalizadas

## Estructura del proyecto

```
app/
├── main.py          # FastAPI app, filtros Jinja2, migraciones inline
├── database.py      # Conexión SQLite / SQLAlchemy
├── models.py        # Modelos ORM
├── schemas.py       # Schemas Pydantic
├── routers/         # Lógica por módulo (ventas, clientes, servicios, stock, dashboard)
├── templates/       # HTML con Jinja2
└── static/          # CSS y JS

seed.py              # Poblar DB con datos de ejemplo
salon.db             # Base de datos local (hacer backup copiando el archivo)
```

## Notas

- **Nombre del salón**: buscar "Bella Studio" en los templates y reemplazar
- **Horario**: la app usa UTC internamente y muestra hora Argentina (UTC-3) en la interfaz
- **Backups**: copiar `salon.db` es suficiente para hacer un backup completo
- **Rentabilidad**: para que el análisis de márgenes funcione, configurar los insumos que consume cada servicio en Servicios → Editar

## Migrar a PostgreSQL (futuro)

Cambiar en `app/database.py`:
```python
DATABASE_URL = "postgresql://usuario:password@localhost/salon_db"
```
Y remover `connect_args` del engine.

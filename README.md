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
| Dashboard | `/` | KPIs, gráficos por rango, rentabilidad y punto de equilibrio |
| Nueva Venta | `/ventas/nueva` | Registro rápido con descuentos y asignación de cliente |
| Ventas del día | `/ventas` | Listado con filtro por fecha, asignar cliente post-venta |
| Caja diaria | `/ventas/caja` | Resumen imprimible del día |
| Clientes | `/clientes` | CRUD completo + historial de servicios por cliente |
| Servicios | `/servicios` | Catálogo de servicios, combos y consumo de insumos |
| Stock | `/stock` | Inventario con categorías, alertas de mínimo y proyección |
| Configuración | `/costos` | Costos fijos del negocio y parámetros de trabajo |

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
- **Análisis de rentabilidad real**: costo de insumos + costo de tiempo por servicio, margen, estado (saludable / advertencia / crítico) y recomendaciones de precio
- **Punto de equilibrio**: servicios mínimos mensuales para cubrir costos fijos

**Rentabilidad**
- Costo de insumos calculado con rendimiento real (ej: 1 frasco = 40 aplicaciones)
- Costo de tiempo basado en costos fijos / horas productivas × duración del servicio
- Estados: saludable (≥30%), advertencia (15–29%), crítico (<15%), sin datos
- API JSON disponible en `/api/rentabilidad/resumen` y `/api/rentabilidad/punto-equilibrio`

**Configuración del negocio** (`/costos`)
- Alta, edición y baja de costos fijos mensuales (alquiler, servicios, personal, otros)
- Parámetros: días trabajados por mes, horas por día y % de ocupación estimada
- Cálculo automático de costo fijo por hora productiva
- **PIN de administrador**: protege todas las acciones críticas (ver abajo)

**Stock**
- Categorías dinámicas (crear, editar, eliminar desde la UI)
- Rendimiento por producto: cuántos usos rinde cada unidad
- Historial de movimientos por producto
- Alertas visuales de stock bajo mínimo
- Ajustes manuales con registro de motivo

**Clientes**
- Búsqueda por nombre
- Historial completo de servicios y total gastado
- Cumpleaños y notas personalizadas

**Seguridad — PIN de administrador**
- PIN de 4+ dígitos definido en Configuración, guardado hasheado (SHA-256)
- Modal de PIN aparece al intentar cualquier acción crítica: editar precios, modificar stock, eliminar clientes/servicios/productos
- Sesión activa por 30 minutos; indicador visible en el sidebar
- Sin PIN configurado, todas las acciones funcionan sin fricción (modo inicial)
- Operaciones del día a día (registrar ventas, ver listados) no requieren PIN

## Estructura del proyecto

```
app/
├── main.py          # FastAPI app, filtros Jinja2, migraciones inline
├── database.py      # Conexión SQLite / SQLAlchemy
├── models.py        # Modelos ORM
├── utils.py         # Lógica de rentabilidad y punto de equilibrio
├── routers/
│   ├── dashboard.py
│   ├── ventas.py
│   ├── clientes.py
│   ├── servicios.py
│   ├── stock.py
│   └── costos.py    # Configuración del negocio + API rentabilidad
├── templates/       # HTML con Jinja2
└── static/          # CSS y JS

seed.py              # Poblar DB con datos de ejemplo
salon.db             # Base de datos local (hacer backup copiando el archivo)
```

## API JSON

| Endpoint | Descripción |
|----------|-------------|
| `GET /api/rentabilidad/resumen` | Lista de servicios con margen, estado y costos |
| `GET /api/rentabilidad/punto-equilibrio` | Servicios mínimos para cubrir costos fijos |
| `GET /api/rentabilidad/servicio/{id}` | Rentabilidad de un servicio específico |
| `GET /api/costos-fijos` | Lista de costos fijos activos |
| `GET /api/configuracion-negocio` | Parámetros de trabajo actuales |
| `GET /api/admin/status` | Si hay PIN configurado (`{"has_pin": bool}`) |
| `POST /api/admin/login` | Verificar PIN y obtener token de sesión (30 min) |
| `POST /api/admin/logout` | Invalidar token activo |

## Notas

- **Nombre del salón**: buscar "Bella Studio" en los templates para personalizar
- **Horario**: la app usa UTC internamente y muestra hora Argentina (UTC-3) en la interfaz
- **Backups**: copiar `salon.db` es suficiente para hacer un backup completo
- **Rentabilidad**: configurar los insumos de cada servicio (Servicios → Editar) y los costos fijos del negocio (Configuración) para que el análisis de márgenes sea preciso
- **Rendimiento de insumos**: en Stock → Editar producto, indicar cuántos usos rinde cada unidad para calcular el costo real por servicio
- **PIN de admin**: configurarlo en Configuración → "PIN de administrador". Sin PIN, la app funciona igual que antes

## Migrar a PostgreSQL (futuro)

Cambiar en `app/database.py`:
```python
DATABASE_URL = "postgresql://usuario:password@localhost/salon_db"
```
Y remover `connect_args` del engine.

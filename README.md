# Bella Studio — Sistema de Gestión

Sistema de gestión integral para salón de manicuría. Backend Python (FastAPI) + frontend HTML/CSS/JS, base de datos PostgreSQL. Desplegado en infraestructura de nube (Oracle Cloud) mediante Docker.

## 🚀 Despliegue y Ejecución

La aplicación está diseñada para correr en contenedores Docker, asegurando la consistencia entre entornos de desarrollo y producción.

### Ejecución con Docker Compose
Para levantar la aplicación y la base de datos PostgreSQL:

```bash
# 1. Clonar el repositorio
git clone https://github.com/clcdavi/gestion-manicura.git
cd gestion-manicura

# 2. Levantar los servicios
sudo docker-compose up -d --build
```

La aplicación estará disponible en el puerto `8000`.

### Variables de Entorno
El sistema utiliza las siguientes variables para su configuración:
- `DATABASE_URL`: Cadena de conexión a PostgreSQL (ej: `postgresql://user:pass@host:5432/db`).
- `SESSION_SECRET`: Clave secreta para la gestión de sesiones y seguridad.

---

## 📦 Módulos del Sistema

| Módulo | URL | Descripción |
|--------|-----|-------------|
| Dashboard | `/` | KPIs, análisis de rentabilidad real y punto de equilibrio |
| Nueva Venta | `/ventas/nueva` | Registro rápido con descuentos y asignación de cliente |
| Ventas del día | `/ventas` | Listado con filtro por fecha y gestión de clientes post-venta |
| Caja diaria | `/ventas/caja` | Resumen imprimible de ingresos del día |
| Clientes | `/clientes` | Gestión de clientes + fichas técnicas y historial |
| Servicios | `/servicios` | Catálogo de servicios, combos y vinculación de insumos |
| Stock | `/stock` | Inventario con alertas de mínimo y rendimiento de productos |
| Configuración | `/costos` | Costos fijos del negocio, parámetros de trabajo y PIN de admin |

## ✨ Funcionalidades Clave

### Rentabilidad Inteligente
El sistema no solo registra ventas, sino que calcula la salud financiera de cada servicio:
- **Costos Dinámicos:** Calcula el costo de insumos basándose en el rendimiento real (ej: 1 frasco = 40 usos).
- **Costo de Tiempo:** Calcula cuánto cuesta cada minuto de trabajo basado en los costos fijos y horas productivas.
- **Semáforo de Márgenes:** Clasifica servicios en Saludables (🟢), Advertencia (🟡) o Críticos (🔴).
- **Punto de Equilibrio:** Determina la cantidad mínima de servicios necesarios para cubrir los gastos fijos.

### Seguridad y Control
- **PIN de Administrador:** Protege acciones críticas (cambio de precios, borrado de datos, ajustes de stock) mediante un sistema de hash SHA-256.
- **Sincronización Google:** Integración con Google Calendar y OAuth2 para gestión de turnos y acceso.

### Gestión de Stock
- Descuento automático de insumos al concretar una venta.
- Proyección de stock crítico basada en el consumo real.

---

## 🏗️ Estructura del Proyecto

```
app/
├── main.py          # FastAPI app, filtros Jinja2 y configuración
├── database.py      # Gestión de conexión (PostgreSQL / SQLite)
├── models.py        # Modelos ORM de SQLAlchemy
├── utils.py         # Lógica de cálculos de rentabilidad
├── routers/          # Controladores de cada módulo
├── templates/       # HTML con Jinja2
└── static/          # CSS y JS
```

## 📖 Documentación de Uso
Para instrucciones detalladas paso a paso sobre cómo configurar y operar la plataforma, consulta el archivo **[MANUAL.md](./MANUAL.md)**.

---

## 🛠️ Notas Técnicas
- **Timezone:** Internamente usa UTC y muestra hora Argentina (UTC-3) en la interfaz.
- **Base de Datos:** Migrado de SQLite a PostgreSQL para persistencia en nube.
- **Backup:** Al usar PostgreSQL, se recomienda realizar backups mediante `pg_dump` o snapshots de la instancia de Oracle Cloud.

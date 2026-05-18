# Bella Studio — Sistema de Gestión v2.0

Sistema de gestión integral para salón de manicuría. Backend Python (FastAPI) + frontend HTML/CSS/JS, base de datos SQLite/PostgreSQL. Incluye autenticación con Google OAuth2, RBAC, rotación automática de PIN, contabilidad, fidelización y sincronización con Google Calendar.

---

## 🚀 Despliegue Rápido

### Requisitos previos
- Docker y Docker Compose instalados
- Proyecto en Google Cloud Console con OAuth2 configurado

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/clcdavi/gestion-manicura.git
cd gestion-manicura

# 2. Crear el docker-compose.yml con tus credenciales (NO está en el repo por seguridad)
# Ver sección "Variables de Entorno" más abajo

# 3. Levantar los servicios
sudo docker-compose up -d --build
```

La aplicación estará disponible en `http://localhost:8000`

---

## ⚙️ Variables de Entorno

Creá un archivo `docker-compose.yml` local (no se sube a git) con las siguientes variables:

```yaml
environment:
  # Base de datos
  - DATABASE_URL=postgresql://usuario:contraseña@db:5432/salon_db

  # Sesión segura (generá una clave aleatoria larga)
  - SESSION_SECRET=clave_muy_larga_y_aleatoria

  # Google OAuth2 — Login de usuarios
  - GOOGLE_CLIENT_ID=tu_client_id.apps.googleusercontent.com
  - GOOGLE_CLIENT_SECRET=GOCSPX-tu_secret

  # URIs de callback (deben coincidir con las configuradas en Google Console)
  - GOOGLE_LOGIN_REDIRECT_URI=http://localhost:8000/auth/google/callback
  - GOOGLE_CALENDAR_REDIRECT_URI=http://localhost:8000/auth/google/callback-calendar

  # Emails de administradores RBAC (separados por coma)
  - ADMIN_EMAILS=tumail@gmail.com
```

### Configuración en Google Cloud Console

1. Ir a [APIs y servicios → Credenciales](https://console.cloud.google.com/apis/credentials)
2. Abrir el cliente OAuth 2.0 existente (o crear uno nuevo de tipo "Aplicación web")
3. En **"URIs de redireccionamiento autorizados"** agregar:
   - `http://localhost:8000/auth/google/callback`
   - `http://localhost:8000/auth/google/callback-calendar`
4. Copiar el **Client ID** y generar un nuevo **Client Secret**

---

## 📦 Módulos del Sistema

| Módulo | URL | Descripción |
|--------|-----|-------------|
| Dashboard | `/` | KPIs, turnos del día, alertas de cumpleaños y fidelización |
| Nueva Venta | `/ventas/nueva` | Registro con pagos mixtos, descuentos y fidelización automática |
| Ventas del día | `/ventas` | Listado con filtro por fecha y edición de ventas |
| Caja diaria | `/ventas/caja` | Resumen imprimible de ingresos por método de pago |
| Agenda / Turnos | `/turnos` | Calendario de turnos con sync a Google Calendar |
| Clientes | `/clientes` | Fichas técnicas, historial, inactivos y cumpleaños |
| Servicios | `/servicios` | Catálogo, combos y vinculación de insumos |
| Stock | `/stock` | Inventario con alertas y rendimiento por uso |
| Compras de insumos | `/stock/compras` | Historial de compras con reversión automática |
| Contabilidad | `/contabilidad` | Ingresos, egresos, balance y exportación Excel |
| Configuración | `/costos` | Costos fijos, parámetros de trabajo y PIN rotativo |
| Fidelización | `/configuracion/fidelizacion` | Programa de beneficios por visitas |
| Login | `/auth/login` | Autenticación con Google OAuth2 |

---

## ✨ Funcionalidades Clave

### 🔐 Seguridad y Autenticación
- **Login con Google OAuth2:** Flujo seguro con Authlib. Los emails en `ADMIN_EMAILS` reciben rol de administrador automáticamente.
- **RBAC:** Rutas `/admin/*` protegidas con `get_current_admin_user`. Acceso denegado con HTTP 403 si no hay sesión válida.
- **PIN de Administrador Rotativo:** Generado automáticamente cada día a las 00:00 (hora Argentina). Hash SHA-256 en BD. Solo el admin autenticado con Google puede consultarlo en `/auth/admin/pin-actual`.
- **Rotación automática:** APScheduler con timezone `America/Argentina/Buenos_Aires`. Al arrancar la app, si no hay PIN generado, se crea uno inmediatamente.

### 💰 Rentabilidad Inteligente
- **Costos Dinámicos:** Costo de insumos basado en rendimiento real (ej: 1 frasco = 40 usos).
- **Costo de Tiempo:** Calcula cuánto cuesta cada hora de trabajo según costos fijos y ocupación.
- **Semáforo de Márgenes:** 🟢 Saludable ≥30% | 🟡 Advertencia 15-29% | 🔴 Crítico <15%
- **Punto de Equilibrio:** Retorna `0` cuando no hay costos fijos cargados (sin división por cero).

### 📊 Contabilidad y Fiscal
- Motor de cálculos: ingresos, egresos, balance mensual
- Categorización y proyección de Monotributo
- Exportación a Excel con 5 hojas detalladas

### 👥 Fidelización
- Configuración de visitas necesarias para activar beneficio
- Descuento automático o servicio gratis
- Badge visual en ficha de cliente y dashboard

### 📅 Google Calendar
- Sincronización bidireccional de turnos
- Flujo OAuth2 independiente del login de usuarios
- Estado del turno: pendiente / confirmado / realizado / cancelado

---

## 🏗️ Estructura del Proyecto

```
app/
├── main.py           # FastAPI app, startup del scheduler, migraciones inline
├── database.py       # Conexión SQLAlchemy (PostgreSQL / SQLite)
├── models.py         # Modelos ORM: User, Venta, Cliente, Turno, etc.
├── scheduler.py      # Rotación automática del PIN con APScheduler
├── utils.py          # Cálculos de rentabilidad y punto de equilibrio
├── google_calendar.py# Integración Google Calendar API
├── routers/
│   ├── auth.py       # OAuth2 Google, RBAC, /admin/pin-actual
│   ├── dashboard.py  # KPIs, turnos hoy, alertas
│   ├── ventas.py     # Ventas, pagos mixtos, fidelización
│   ├── clientes.py   # Fichas técnicas, vistas filtradas
│   ├── stock.py      # Inventario y compras de insumos
│   ├── costos.py     # Costos fijos, PIN, API de rentabilidad
│   ├── contabilidad.py # Reportes contables y export Excel
│   ├── servicios.py  # Catálogo y combos
│   └── turnos.py     # Agenda y sync Google Calendar
├── templates/        # HTML Jinja2
│   └── auth/
│       └── login.html # Página de login con Google
└── static/           # CSS (dark mode, temas) y JS
```

---

## 🛠️ Notas Técnicas

- **Timezone:** UTC internamente, UTC-3 (Argentina) en la interfaz y en el scheduler.
- **Migraciones:** Inline en `main.py` con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
- **Backup automático:** Copia diaria de `salon.db` al arrancar (últimas 7 versiones).
- **Dark Mode:** Anti-flash en `<head>`, persiste en `localStorage`.
- **Seguridad:** `docker-compose.yml` excluido de git (`.gitignore`). Nunca commitear secrets.

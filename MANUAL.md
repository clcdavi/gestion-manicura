# 💅 Manual de Usuario — Bella Studio v2.0

Bienvenida al sistema de gestión de Bella Studio. Esta guía te ayudará a configurar y operar la plataforma desde cero.

---

## 🔐 Primer Paso: Iniciar Sesión

La plataforma ahora usa **Google OAuth2** para autenticarse de forma segura.

1. Abrí el navegador y andá a la dirección del sistema (ej: `http://localhost:8000`)
2. Vas a ver la pantalla de login con el botón **"Iniciar sesión con Google"**
3. Hacé clic → elegí tu cuenta de Gmail → listo, estás dentro
4. Si tu email es el configurado como administrador, vas a ver el badge **ADMIN** en el menú lateral y acceso al **Panel Admin**

> 💡 **¿Dónde ves tu nombre?** En la parte inferior del menú lateral izquierdo, aparece tu nombre y un link para cerrar sesión.

---

## 🚀 Configuración Inicial del Negocio

Para que los cálculos sean correctos, seguí este orden la primera vez:

### 1. Configuración de Parámetros de Trabajo
Andá a **Configuración** (`/costos`) → sección "Configuración del Negocio":
- **Días de trabajo al mes:** Cuántos días trabajás (ej: 22)
- **Horas por día:** Tu jornada laboral (ej: 7)
- **% de Ocupación:** Qué porcentaje del tiempo tenés clientes (ej: 75%)

Estos datos son la base para calcular el **Costo por Hora** de tu tiempo.

### 2. Costos Fijos del Negocio
En la misma pantalla **Configuración** (`/costos`):
- Agregá todos tus gastos mensuales: Alquiler, Luz, Internet, Gas, etc.
- Categorizalos: Local / Servicios / Personal / Otros
- El sistema los usará para calcular el **Punto de Equilibrio**

> ⚠️ Las acciones de modificación requieren el **PIN de Administrador** (ver sección de Seguridad).

### 3. Inventario de Insumos
Andá a **Stock** (`/stock`):
- Cargá cada producto con:
  - **Nombre y categoría** (ej: "Esmalte Rojo", categoría "Esmaltes")
  - **Costo unitario** (lo que pagaste por el frasco/paquete)
  - **Rendimiento:** ¡Muy importante! Cuántos usos rinde esa unidad (ej: 1 esmalte = 40 aplicaciones)
  - **Stock actual y mínimo** para que el sistema te avise cuando estés por quedarte sin insumos

### 4. Catálogo de Servicios
Andá a **Servicios** (`/servicios`):
- Creá cada servicio con nombre, precio y duración en minutos
- **Vinculá insumos:** Dentro de cada servicio, agregá qué productos consume
  - *Ejemplo:* "Semipermanente" consume 1 base + 1 color + 1 top coat
  - El sistema calculará el costo exacto de materiales por servicio

### 5. Cargá tus Clientes
Andá a **Clientes** (`/clientes`) → "+ Nuevo Cliente":
- Nombre, teléfono, fecha de nacimiento (para alertas de cumpleaños)
- **Ficha técnica:** tipo de uña preferido, color favorito, alergias ⚠️

---

## 💰 Operaciones Diarias

### Registrar una Venta
Andá a **Nueva Venta** (`/ventas/nueva`):
1. Seleccioná el servicio o combo realizado
2. Elegí el cliente (o dejalo vacío y asignalo después)
3. **Forma de pago:** Efectivo / Transferencia / Tarjeta / **Mixto** (ej: $2000 efectivo + $1000 transferencia)
4. Aplicá descuento si corresponde (por monto fijo o porcentaje)
5. **Guardar** → el sistema descuenta automáticamente los insumos del stock y registra la venta

### Registrar una Compra de Insumos
Andá a **Stock → Compras de insumos** (`/stock/compras`):
- Registrá cada reposición con: proveedor, N° de factura, precio pagado
- Podés actualizar el precio de costo del producto automáticamente
- Si eliminás una compra, el stock se revierte solo

### Agendar un Turno
Andá a **Agenda / Turnos** (`/turnos`):
- Creá el turno eligiendo cliente, servicios, fecha y hora
- Si tenés Google Calendar conectado, el turno se sincroniza automáticamente
- Estados: Pendiente → Confirmado → Realizado / Cancelado

---

## 📈 Dashboard y Análisis

El **Dashboard** (`/`) es tu centro de comando diario:

### Lo que ves al entrar
- 📅 **Turnos de hoy:** Lista compacta de quién viene y a qué hora
- 🎂 **Cumpleaños:** Clientes que cumplen años hoy con link directo a WhatsApp
- 😴 **Clientes inactivos:** Las que no vienen hace más de 60 días
- 💜 **Beneficios pendientes:** Clientes que ya ganaron su beneficio de fidelización

### Semáforo de Rentabilidad por Servicio
- 🟢 **Saludable (≥30%):** Margen excelente, seguí así
- 🟡 **Advertencia (15-29%):** Margen bajo, considerá ajustar el precio
- 🔴 **Crítico (<15%):** Casi sin ganancia. Revisá el precio urgente

### Punto de Equilibrio
Cuántos servicios mínimos debés hacer al mes para no perder dinero. Si tenés `0` es porque todavía no cargaste costos fijos.

---

## 👥 Gestión de Clientes

Andá a **Clientes** (`/clientes`):

### Vistas disponibles
- **Activos:** Todas las clientas
- **💤 Inactivas:** Las que no vinieron hace más de 60 días (ideal para recontactar)
- **🎂 Cumpleaños hoy:** Para enviar un saludo personalizado

### Ficha de cada cliente
Hacé clic en el nombre de una clienta para ver:
- Historial completo de servicios y gastos
- Próximos turnos agendados
- Progreso de fidelización (cuántas visitas le faltan para el beneficio)
- Link directo a WhatsApp
- Ficha técnica: preferencias, alergias ⚠️ (se marca en rojo)

---

## 📊 Contabilidad

Andá a **Contabilidad** (`/contabilidad`):

- **Ingresos:** Resumen de ventas por período con desglose por método de pago
- **Egresos (Costos Fijos):** Lo que gastás por mes
- **Balance:** Diferencia entre ingresos y egresos
- **Monotributo:** Categorización automática basada en facturación anual proyectada y alertas de límite de categoría
- **Export Excel:** Descargá un archivo con 5 hojas detalladas para presentar al contador

---

## 💜 Programa de Fidelización

Configuralo en **Configuración → Fidelización** (`/configuracion/fidelizacion`):
- **Activar/desactivar** el programa
- **Visitas necesarias** para ganar el beneficio (ej: 10 visitas)
- **Tipo de beneficio:** Descuento porcentual o servicio gratis
- Cuando una clienta alcanza el número de visitas, se activa automáticamente `beneficio_disponible = True` y aparece en el dashboard

---

## 🛡️ Seguridad y Panel Admin

### PIN de Administrador
El PIN protege acciones críticas como:
- Crear / editar / eliminar costos fijos
- Cambiar la configuración del negocio

**El PIN es automático:** Se genera un número de 4 dígitos nuevo **todos los días a las 00:00** (hora Argentina). No lo configurás vos, lo genera el sistema.

### ¿Cómo sabés cuál es el PIN del día?
Solo el administrador autenticado con Google puede consultarlo:
1. Iniciá sesión con tu cuenta de Google (la configurada como admin)
2. En el menú lateral aparece **🔑 Panel Admin**
3. Hacé clic → te muestra el PIN del día en texto plano

### Sesión de PIN
Una vez ingresado el PIN, queda activo por **30 minutos** para no tener que escribirlo en cada operación. Podés cerrarlo manualmente con el botón "Cerrar" en el menú lateral.

---

## 📅 Sincronización con Google Calendar

Andá a **Agenda / Turnos** (`/turnos`) → "Conectar Google Calendar":
- Se inicia un flujo OAuth2 separado (usa `credentials.json`)
- Una vez conectado, cada turno creado/editado/eliminado se refleja en tu Google Calendar
- El email del calendario conectado aparece en la pantalla de turnos

---

## 🆘 Solución de Problemas Frecuentes

| Problema | Causa probable | Solución |
|---|---|---|
| No puedo iniciar sesión con Google | `GOOGLE_CLIENT_ID` o `SECRET` incorrectos | Revisá las variables de entorno |
| Error en el callback de Google | URI no autorizada en Google Console | Agregá la URI correcta en las credenciales |
| No veo "Panel Admin" | Tu email no está en `ADMIN_EMAILS` | Verificá el docker-compose |
| El PIN no funciona | Se rotó a medianoche | Consultá el nuevo PIN en el Panel Admin |
| Stock en negativo | Compra no registrada o rendimiento incorrecto | Revisá historial de compras y rendimiento del producto |
| Punto de equilibrio muestra 0 | No hay costos fijos cargados | Agregá tus gastos en Configuración |
| Google Calendar no sincroniza | Token expirado | Reconectá el calendario desde la pantalla de Turnos |

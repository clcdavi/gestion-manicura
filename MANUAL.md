# 💅 Manual de Usuario — Bella Studio

Bienvenido al sistema de gestión de Bella Studio. Esta guía te ayudará a configurar y utilizar la plataforma desde cero para optimizar la administración de tu salón.

## 🚀 Primeros Pasos (Configuración Inicial)

Para que la plataforma funcione correctamente y los cálculos de dinero sean reales, sigue este orden de configuración:

### 1. Configuración del Negocio y Seguridad
Ve a **Configuración** (`/costos`):
- **PIN de Administrador:** Define un PIN de 4+ dígitos. Esto protegerá los precios y el stock para que no sean modificados por error.
- **Parámetros de Trabajo:** Indica cuántos días trabajas al mes, cuántas horas por día y tu porcentaje de ocupación estimada. Estos datos son la base para calcular el "Costo por Hora" de tu tiempo.
- **Costos Fijos:** Agrega todos tus gastos mensuales (Alquiler, Luz, Internet, Sueldos, etc.). El sistema usará esto para calcular el **Punto de Equilibrio** (cuántos servicios debes hacer para no perder dinero).

### 2. Gestión de Inventario (Stock)
Ve a **Stock** (`/stock`):
- **Categorías:** Crea categorías (ej: "Esmaltes", "Geles", "Herramientas").
- **Productos:** Carga tus insumos. 
  - **Costo Unitario:** Cuánto pagaste por el frasco/paquete.
  - **Rendimiento:** ¡Muy importante! Indica cuántos usos rinde esa unidad (ej: un esmalte rinde 40 aplicaciones). El sistema calculará el costo exacto de cada gota de producto por servicio.

### 3. Catálogo de Servicios
Ve a **Servicios** (`/servicios`):
- **Crear Servicio:** Define el nombre, precio y duración.
- **Vincular Insumos:** Dentro de cada servicio, añade qué productos de stock consume y en qué cantidad. 
  - *Ejemplo:* Un "Semipermanente" consume 1 aplicación de base, 1 de color y 1 de top coat.

---

## 💰 Operaciones Diarias

### Registro de Ventas
Ve a **Nueva Venta** (`/ventas/nueva`):
1. Selecciona el servicio o combo realizado.
2. Elige el cliente (o deja vacío y asígnalo después en el listado de ventas).
3. Aplica descuentos si es necesario (por monto fijo o porcentaje).
4. **Guardar:** Al guardar, el sistema automáticamente descuenta los insumos del stock y suma la ganancia al dashboard.

### Gestión de Clientes
Ve a **Clientes** (`/clientes`):
- Usa la **Ficha Técnica** para anotar preferencias (color favorito, tipo de uña, alergias). Esto permite dar una atención personalizada.
- Consulta el historial de cada cliente para ver qué servicios prefiere y cuánto ha gastado en total.

---

## 📈 Análisis y Rentabilidad (El Cerebro del Negocio)

El **Dashboard** (`/`) es donde tomas decisiones basadas en datos:

### Análisis de Rentabilidad
En el Dashboard verás cada servicio con un color:
- 🟢 **Saludable (≥30%):** El servicio deja una buena ganancia.
- 🟡 **Advertencia (15-29%):** El margen es bajo. Considera subir el precio o reducir costos de insumos.
- 🔴 **Crítico (<15%):** Estás casi al costo o perdiendo dinero. **Revisa el precio inmediatamente.**

**¿Cómo se calcula esto?**
`Ganancia = Precio - (Costo de Insumos + Costo de tu tiempo por hora)`

### Punto de Equilibrio
El sistema te dirá cuántos servicios mínimos debes realizar al mes para cubrir todos tus costos fijos. Si haces menos de esa cantidad, el negocio está operando en pérdida.

---

## 🛡️ Seguridad y Administración
- **Acciones Críticas:** Siempre que intentes cambiar un precio, eliminar un cliente o ajustar el stock, el sistema te pedirá el **PIN de Administrador**.
- **Sesión de PIN:** Una vez ingresado, el PIN queda activo por 30 minutos para que no tengas que escribirlo en cada operación.

## 🆘 Solución de Problemas Comunes
- **El login de Google no funciona:** Verifica que la URL de redireccionamiento en la consola de Google coincida con la IP actual del servidor.
- **El stock está en negativo:** Revisa si olvidaste cargar una compra de insumos o si el rendimiento del producto configurado es incorrecto.

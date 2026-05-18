"""Script de auditoría de rutas — ejecutar manualmente, borrar después."""
import urllib.request, urllib.error

BASE = "http://localhost:8000"

routes = [
    # Dashboard
    ("Dashboard principal",           "/"),
    # Ventas
    ("Nueva Venta",                   "/ventas/nueva"),
    ("Ventas del día / lista",        "/ventas"),
    ("Caja diaria",                   "/ventas/caja"),
    # Clientes
    ("Clientes – lista activos",      "/clientes"),
    ("Clientes – inactivos",          "/clientes?filtro=inactivos"),
    ("Clientes – cumpleaños",         "/clientes?filtro=cumpleanos"),
    ("Cliente – nuevo form",          "/clientes/nuevo"),
    # Servicios
    ("Servicios – lista",             "/servicios"),
    ("Servicio – nuevo form",         "/servicios/nuevo"),
    ("Combo – nuevo form",            "/servicios/combos/nuevo"),
    # Stock
    ("Stock – lista",                 "/stock"),
    ("Stock – nuevo producto",        "/stock/nuevo"),
    ("Compras – lista",               "/stock/compras"),
    ("Compra – nueva",                "/stock/compras/nueva"),
    # Contabilidad
    ("Contabilidad – panel",          "/contabilidad"),
    ("Contabilidad – ingresos",       "/contabilidad/ingresos"),
    ("Contabilidad – egresos",        "/contabilidad/egresos"),
    ("Contabilidad – balance anual",  "/contabilidad/balance"),
    ("Contabilidad – monotributo",    "/contabilidad/monotributo"),
    ("Contabilidad – exportar form",  "/contabilidad/exportar"),
    # Turnos / Agenda
    ("Agenda – calendario semanal",   "/turnos"),
    ("Agenda – lista",                "/turnos/lista"),
    ("Agenda – nuevo turno",          "/turnos/nuevo"),
    # Configuración
    ("Config – costos fijos",         "/costos"),
    ("Config – fidelización",         "/configuracion/fidelizacion"),
    # Búsqueda global
    ("Búsqueda global",               "/buscar?q=test"),
    # Auth / Admin
    ("Auth – estado Google",          "/auth/google/status"),
    ("Admin – backup DB",             "/admin/backup"),
]

ok = fail = 0
fails = []

for name, path in routes:
    try:
        req = urllib.request.Request(BASE + path)
        r = urllib.request.urlopen(req, timeout=5)
        code = r.getcode()
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        code = f"ERR({e})"

    if isinstance(code, int) and code < 400:
        icon = "✅"
        ok += 1
    else:
        icon = "❌"
        fail += 1
        fails.append((name, path, code))

    print(f"{icon}  {str(code):<4} {name}")

print(f"\n{'='*50}")
print(f"Resultado: {ok} OK  |  {fail} FALLIDOS")
if fails:
    print("\nFallas detalladas:")
    for n, p, c in fails:
        print(f"  ❌ {c}  {n}  → {p}")

"""
Router de autenticación OAuth2 con Google y RBAC.
"""
import os

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

# --- Configuración OAuth2 ---
CONF_ID = os.getenv("GOOGLE_CLIENT_ID")
CONF_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# URI de callback para LOGIN de usuarios (distinto al de Google Calendar)
LOGIN_REDIRECT_URI = os.getenv(
    "GOOGLE_LOGIN_REDIRECT_URI",
    "http://localhost:8000/auth/google/callback"
)
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]

# Lazy-init OAuth para evitar error si las vars de entorno no están al arrancar
_oauth = None

def get_oauth():
    global _oauth
    if _oauth is None:
        from authlib.integrations.starlette_client import OAuth
        _oauth = OAuth()
        _oauth.register(
            name='google',
            client_id=CONF_ID,
            client_secret=CONF_SECRET,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
    return _oauth


# --- Dependencias de Acceso ---

def get_current_user(request: Request):
    """Obtiene el usuario de la sesión (None si no está autenticado)."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return user_id


def get_current_admin_user(request: Request, db: Session = Depends(get_db)):
    """Protege rutas críticas: verifica que el usuario sea admin autenticado con Google."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: debés iniciar sesión con Google primero."
        )
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: no tenés permisos de administrador."
        )
    return user


# --- Rutas de Login/Logout ---

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Muestra la página de login con botón 'Iniciar sesión con Google'."""
    # Si ya está logueado, redirigir al inicio
    if request.session.get("user_id"):
        return RedirectResponse(url="/")
    flash_msg = request.session.pop("flash", None)
    flash_type = request.session.pop("flash_type", "info")
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "flash_msg": flash_msg,
        "flash_type": flash_type,
        "google_configured": bool(CONF_ID and CONF_SECRET),
    })


@router.get("/google/start")
async def login_google(request: Request):
    """Inicia el flujo OAuth2 con Google para login de usuarios."""
    if not CONF_ID or not CONF_SECRET:
        request.session["flash"] = "⚠️ Google OAuth2 no está configurado (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET)."
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/auth/login")

    oauth = get_oauth()
    return await oauth.google.authorize_redirect(request, LOGIN_REDIRECT_URI)


@router.get("/google/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    """Procesa el callback de Google, crea/actualiza el usuario y asigna rol."""
    try:
        oauth = get_oauth()
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')

        if not user_info:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {token['access_token']}"}
                )
                user_info = resp.json()

        email = user_info.get("email", "").strip().lower()
        nombre = user_info.get("name", "Usuario")

        if not email:
            raise ValueError("Google no proporcionó un email.")

        # RBAC: ¿es administrador?
        is_admin = email in ADMIN_EMAILS

        # Guardar o actualizar usuario en BD
        user = db.query(models.User).filter_by(email=email).first()
        if not user:
            user = models.User(email=email, nombre=nombre, is_admin=is_admin)
            db.add(user)
        else:
            user.nombre = nombre
            user.is_admin = is_admin  # Actualizar por si cambió ADMIN_EMAILS

        db.commit()
        db.refresh(user)

        # Guardar sesión
        request.session["user_id"] = user.id
        request.session["user_name"] = user.nombre
        request.session["user_is_admin"] = user.is_admin
        request.session["flash"] = f"👋 ¡Bienvenida, {user.nombre}!"
        request.session["flash_type"] = "success"

        return RedirectResponse(url="/")

    except Exception as e:
        request.session["flash"] = f"Error al iniciar sesión: {str(e)}"
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/logout")
def logout(request: Request):
    """Cierra la sesión del usuario."""
    nombre = request.session.get("user_name", "")
    request.session.clear()
    request.session["flash"] = f"Sesión cerrada. ¡Hasta pronto{', ' + nombre if nombre else ''}!"
    request.session["flash_type"] = "info"
    return RedirectResponse(url="/auth/login")


# --- Rutas Admin protegidas con RBAC ---

@router.get("/admin/pin-actual")
def ver_pin_actual(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin_user),
):
    """
    Devuelve el PIN actual en texto plano.
    Solo accesible para administradores autenticados con Google.
    """
    cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    if not cfg or not cfg.admin_pin_plain:
        return JSONResponse({
            "pin": None,
            "mensaje": "No hay PIN generado aún. El scheduler lo creará a las 00:00 o reiniciá la app.",
        })
    return JSONResponse({
        "pin": cfg.admin_pin_plain,
        "admin": current_admin.nombre,
        "mensaje": "El PIN se rota automáticamente cada día a las 00:00 (hora Argentina).",
    })


@router.post("/admin/rotar-pin-ahora")
def rotar_pin_manual(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin_user),
):
    """
    Rotación manual inmediata del PIN (solo admins).
    Útil para testing o si el scheduler falló.
    """
    from app.scheduler import rotar_pin
    nuevo_pin = rotar_pin()
    return JSONResponse({
        "ok": True,
        "pin": nuevo_pin,
        "admin": current_admin.nombre,
        "mensaje": "PIN rotado exitosamente.",
    })


# --- Mantener compatibilidad con Google Calendar ---

@router.get("/google/connect")
def iniciar_calendario(request: Request):
    """Flujo específico para conectar Google Calendar (usa credentials.json)."""
    from app.google_calendar import CREDENTIALS_FILE, SCOPES, has_credentials_file
    if not has_credentials_file():
        request.session["flash"] = "No se encontró credentials.json."
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/turnos", status_code=302)

    CALENDAR_REDIRECT_URI = os.getenv(
        "GOOGLE_CALENDAR_REDIRECT_URI",
        "http://localhost:8000/auth/google/callback-calendar"
    )
    try:
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=CALENDAR_REDIRECT_URI
        )
        auth_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        request.session["oauth_state"] = state
        return RedirectResponse(url=auth_url)
    except Exception as e:
        request.session["flash"] = f"Error: {str(e)}"
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/turnos", status_code=302)


@router.get("/google/callback-calendar")
def calendar_callback(request: Request, db: Session = Depends(get_db)):
    """Recibe el código OAuth2 exclusivo para Google Calendar."""
    from app.google_calendar import CREDENTIALS_FILE, SCOPES, has_credentials_file
    code = request.query_params.get("code")
    if not code:
        return RedirectResponse(url="/turnos")

    CALENDAR_REDIRECT_URI = os.getenv(
        "GOOGLE_CALENDAR_REDIRECT_URI",
        "http://localhost:8000/auth/google/callback-calendar"
    )
    try:
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=CALENDAR_REDIRECT_URI
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        user_info_service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        user_info = user_info_service.userinfo().get().execute()
        email = user_info.get("email", "")

        tok = db.query(models.GoogleCalendarToken).filter_by(id=1).first()
        if not tok:
            tok = models.GoogleCalendarToken(id=1)
            db.add(tok)

        tok.access_token = creds.token
        tok.refresh_token = creds.refresh_token
        tok.token_expiry = creds.expiry.replace(tzinfo=None) if creds.expiry else None
        tok.connected_email = email
        db.commit()
        request.session["flash"] = "📅 Calendario conectado."
        request.session["flash_type"] = "success"
    except Exception as e:
        request.session["flash"] = f"Error al conectar calendario: {str(e)}"
        request.session["flash_type"] = "error"

    return RedirectResponse(url="/turnos", status_code=302)

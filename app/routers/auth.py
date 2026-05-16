"""
Router de autenticación OAuth2 con Google Calendar.
"""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.google_calendar import CREDENTIALS_FILE, SCOPES, has_credentials_file

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

REDIRECT_URI = "http://localhost:8000/auth/google/callback"


def _load_client_config():
    if not has_credentials_file():
        return None
    try:
        with open(CREDENTIALS_FILE) as f:
            cfg = json.load(f)
        return cfg.get("web") or cfg.get("installed")
    except Exception:
        return None


@router.get("/google")
def iniciar_oauth(request: Request):
    """Inicia el flow OAuth2 con Google."""
    client = _load_client_config()
    if not client:
        request.session["flash"] = "No se encontró credentials.json. Descargá el archivo desde Google Cloud Console."
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/turnos", status_code=302)

    try:
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        request.session["oauth_state"] = state
        return RedirectResponse(url=auth_url)
    except Exception as e:
        request.session["flash"] = f"Error al iniciar OAuth2: {str(e)}"
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/turnos", status_code=302)


@router.get("/google/callback")
def oauth_callback(request: Request, db: Session = Depends(get_db)):
    """Recibe el código de Google, obtiene tokens y los guarda en la DB."""
    code = request.query_params.get("code")
    if not code:
        request.session["flash"] = "Error en la autorización de Google."
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/turnos", status_code=302)

    try:
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build

        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )
        flow.fetch_token(code=code)
        creds = flow.credentials

        # Obtener email del usuario conectado
        user_info_service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        user_info = user_info_service.userinfo().get().execute()
        email = user_info.get("email", "")

        # Guardar tokens en DB
        tok = db.query(models.GoogleCalendarToken).filter_by(id=1).first()
        if not tok:
            tok = models.GoogleCalendarToken(id=1)
            db.add(tok)

        tok.access_token = creds.token
        tok.refresh_token = creds.refresh_token
        tok.token_expiry = creds.expiry.replace(tzinfo=None) if creds.expiry else None
        tok.calendar_id = "primary"
        tok.connected_email = email
        db.commit()

        request.session["flash"] = f"✅ Google Calendar conectado correctamente ({email})"
        request.session["flash_type"] = "success"
    except Exception as e:
        request.session["flash"] = f"Error al conectar Google Calendar: {str(e)}"
        request.session["flash_type"] = "error"

    return RedirectResponse(url="/turnos", status_code=302)


@router.post("/google/disconnect")
def desconectar(request: Request, db: Session = Depends(get_db)):
    """Borra los tokens guardados (desconecta el calendario)."""
    tok = db.query(models.GoogleCalendarToken).filter_by(id=1).first()
    if tok:
        tok.access_token = None
        tok.refresh_token = None
        tok.token_expiry = None
        tok.connected_email = None
        db.commit()
    request.session["flash"] = "Google Calendar desconectado."
    request.session["flash_type"] = "info"
    return RedirectResponse(url="/turnos", status_code=302)


@router.get("/google/status")
def estado_conexion(db: Session = Depends(get_db)):
    """JSON con el estado de la conexión."""
    from app.google_calendar import is_connected
    tok = db.query(models.GoogleCalendarToken).filter_by(id=1).first()
    return {
        "connected": is_connected(db),
        "has_credentials_file": has_credentials_file(),
        "email": tok.connected_email if tok else None,
        "calendar_id": tok.calendar_id if tok else None,
    }

"""
Servicio de integración con Google Calendar.
Gestiona OAuth2, creación/actualización/eliminación de eventos y sincronización.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from app import models
from app.database import SessionLocal


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_FILE = "credentials.json"


def _to_utc(dt: datetime) -> datetime:
    """Asegura que el datetime sea naive UTC."""
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def is_connected(db) -> bool:
    """Retorna True si hay tokens válidos guardados."""
    tok = db.query(models.GoogleCalendarToken).filter_by(id=1).first()
    return bool(tok and tok.access_token and tok.refresh_token)


def has_credentials_file() -> bool:
    return os.path.exists(CREDENTIALS_FILE)


def get_credentials(db):
    """
    Obtiene credenciales Google válidas desde la DB.
    Hace refresh automático si el access_token expiró.
    Retorna None si no hay tokens o el refresh falla.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GRequest
        import google.auth.exceptions
    except ImportError:
        return None

    tok = db.query(models.GoogleCalendarToken).filter_by(id=1).first()
    if not tok or not tok.refresh_token:
        return None

    if not has_credentials_file():
        return None

    try:
        with open(CREDENTIALS_FILE) as f:
            client_config = json.load(f)
        web = client_config.get("web") or client_config.get("installed", {})
        client_id = web.get("client_id", "")
        client_secret = web.get("client_secret", "")
        token_uri = web.get("token_uri", "https://oauth2.googleapis.com/token")
    except Exception:
        return None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expiry = tok.token_expiry or (now - timedelta(hours=1))

    creds = Credentials(
        token=tok.access_token,
        refresh_token=tok.refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )

    # Refrescar si expiró o está por expirar en los próximos 5 minutos
    if expiry <= now + timedelta(minutes=5):
        try:
            creds.refresh(GRequest())
            tok.access_token = creds.token
            tok.token_expiry = creds.expiry.replace(tzinfo=None) if creds.expiry else None
            db.commit()
        except Exception:
            return None

    return creds


def _build_service(db):
    """Construye el servicio de Google Calendar API."""
    try:
        from googleapiclient.discovery import build
        import google.auth.exceptions
    except ImportError:
        return None

    creds = get_credentials(db)
    if not creds:
        return None
    try:
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        return None


def _turno_to_event(turno: models.Turno, cliente_nombre: str = "") -> dict:
    """Convierte un Turno del sistema a un evento de Google Calendar."""
    # GCal necesita RFC3339 con timezone; como trabajamos en UTC-3
    def to_rfc3339(dt: datetime) -> str:
        # Los datetimes en DB son UTC → convertir a UTC-3 para mostrar bien en GCal
        dt_ar = dt + timedelta(hours=-3)
        return dt_ar.strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"

    titulo = f"💅 {cliente_nombre}" if cliente_nombre else "💅 Turno"
    if turno.servicios_nombres:
        titulo += f" — {turno.servicios_nombres}"

    event = {
        "summary": titulo,
        "description": turno.notas or "",
        "start": {
            "dateTime": to_rfc3339(turno.fecha_hora_inicio),
            "timeZone": "America/Argentina/Buenos_Aires",
        },
        "end": {
            "dateTime": to_rfc3339(turno.fecha_hora_fin),
            "timeZone": "America/Argentina/Buenos_Aires",
        },
        "colorId": {
            "pendiente": "5",    # amarillo
            "confirmado": "2",   # verde
            "realizado": "8",    # grafito
            "cancelado": "4",    # rojo
        }.get(turno.estado, "5"),
        "extendedProperties": {
            "private": {
                "salon_turno_id": str(turno.id),
            }
        },
    }
    return event


def create_event(db, turno: models.Turno) -> Optional[str]:
    """Crea un evento en Google Calendar. Retorna el gcal_event_id o None."""
    service = _build_service(db)
    if not service:
        return None

    tok = db.query(models.GoogleCalendarToken).filter_by(id=1).first()
    cal_id = (tok.calendar_id or "primary") if tok else "primary"

    cliente_nombre = turno.cliente.nombre if turno.cliente else ""
    event_body = _turno_to_event(turno, cliente_nombre)

    try:
        result = service.events().insert(calendarId=cal_id, body=event_body).execute()
        return result.get("id")
    except Exception:
        return None


def update_event(db, turno: models.Turno) -> bool:
    """Actualiza un evento existente en Google Calendar."""
    if not turno.gcal_event_id:
        return False
    service = _build_service(db)
    if not service:
        return False

    tok = db.query(models.GoogleCalendarToken).filter_by(id=1).first()
    cal_id = (tok.calendar_id or "primary") if tok else "primary"

    cliente_nombre = turno.cliente.nombre if turno.cliente else ""
    event_body = _turno_to_event(turno, cliente_nombre)

    try:
        service.events().update(
            calendarId=cal_id, eventId=turno.gcal_event_id, body=event_body
        ).execute()
        return True
    except Exception:
        return False


def delete_event(db, gcal_event_id: str) -> bool:
    """Elimina (o cancela) un evento de Google Calendar."""
    service = _build_service(db)
    if not service:
        return False

    tok = db.query(models.GoogleCalendarToken).filter_by(id=1).first()
    cal_id = (tok.calendar_id or "primary") if tok else "primary"

    try:
        service.events().delete(calendarId=cal_id, eventId=gcal_event_id).execute()
        return True
    except Exception:
        return False

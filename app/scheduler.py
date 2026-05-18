"""
Scheduler de tareas automáticas del salón.
- Rotación diaria del PIN de administrador a las 00:00 (UTC-3 / Argentina).
"""
import hashlib
import secrets
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from app.database import SessionLocal
from app import models

logger = logging.getLogger(__name__)

AR_TZ = timezone("America/Argentina/Buenos_Aires")


def rotar_pin() -> str:
    """
    Genera un PIN aleatorio de 4 dígitos, lo hashea con SHA-256
    y lo guarda en ConfiguracionNegocio (id=1).
    Invalida el admin_token activo para forzar re-autenticación.
    Devuelve el PIN en texto plano (para logging o debugging en dev).
    """
    db = SessionLocal()
    try:
        # Generar PIN de 4 dígitos con cero-padding (0000-9999)
        pin_int = secrets.randbelow(10000)
        pin_plain = f"{pin_int:04d}"
        pin_hash = hashlib.sha256(pin_plain.encode()).hexdigest()

        cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
        if not cfg:
            cfg = models.ConfiguracionNegocio(id=1)
            db.add(cfg)

        cfg.admin_pin_hash = pin_hash
        cfg.admin_pin_plain = pin_plain
        # Invalidar sesión admin activa al rotar el PIN
        cfg.admin_token = None
        cfg.admin_token_expiry = None

        db.commit()
        logger.info(f"[Scheduler] PIN rotado exitosamente.")
        return pin_plain
    except Exception as e:
        logger.error(f"[Scheduler] Error al rotar PIN: {e}")
        db.rollback()
        return ""
    finally:
        db.close()


def crear_scheduler() -> AsyncIOScheduler:
    """
    Crea y retorna el scheduler configurado.
    - Rota el PIN todos los días a las 00:00 hora Argentina (UTC-3).
    """
    scheduler = AsyncIOScheduler(timezone=AR_TZ)

    scheduler.add_job(
        rotar_pin,
        trigger=CronTrigger(hour=0, minute=0, timezone=AR_TZ),
        id="rotar_pin_diario",
        name="Rotación diaria del PIN de administrador",
        replace_existing=True,
        misfire_grace_time=300,  # tolera hasta 5 min de retraso
    )

    return scheduler

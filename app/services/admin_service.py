import random
import string
import hashlib
from sqlalchemy.orm import Session
from app import models

def generate_random_pin() -> str:
    """Genera un PIN de 4 dígitos aleatorios."""
    return ''.join(random.choices(string.digits, k=4))

def hash_pin(pin: str) -> str:
    """Crea un hash SHA-256 del PIN."""
    return hashlib.sha256(pin.encode()).hexdigest()

def rotate_admin_pin(db: Session):
    """Genera un nuevo PIN, lo hashea y lo guarda en la configuración global."""
    new_pin = generate_random_pin()
    hashed_pin = hash_pin(new_pin)

    cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    if not cfg:
        cfg = models.ConfiguracionNegocio(id=1)
        db.add(cfg)

    cfg.admin_pin_hash = hashed_pin
    cfg.admin_pin_plain = new_pin # Guardado para consulta del admin
    db.commit()
    return new_pin

def verify_pin(db: Session, pin: str) -> bool:
    """Verifica si el PIN proporcionado coincide con el hash guardado."""
    cfg = db.query(models.ConfiguracionNegocio).filter_by(id=1).first()
    if not cfg or not cfg.admin_pin_hash:
        return True # Sin PIN configurado, acceso libre

    return hash_pin(pin) == cfg.admin_pin_hash

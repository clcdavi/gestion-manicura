from sqlalchemy.orm import Session
from app import models


def get_config(db: Session) -> models.ConfiguracionNegocio:
    return db.query(models.ConfiguracionNegocio).filter_by(id=1).first()


def get_costo_fijo_por_hora(db: Session) -> float:
    cfg = get_config(db)
    if not cfg:
        return 0.0
    total_fijos = sum(
        c.monto for c in db.query(models.CostoFijo).filter_by(activo=True).all()
    )
    if total_fijos == 0:
        return 0.0
    horas_productivas_mes = cfg.dias_trabajo_mes * cfg.horas_dia * cfg.pct_ocupacion
    if horas_productivas_mes <= 0:
        return 0.0
    return total_fijos / horas_productivas_mes


def get_costo_insumos_servicio(servicio: models.Servicio) -> float:
    """Costo real de materiales usando rendimiento_usos."""
    return sum(
        sp.cantidad_uso * (sp.producto.costo_unitario / max(sp.producto.rendimiento_usos, 1))
        for sp in servicio.productos_usados
    )


def get_rentabilidad_servicio(servicio: models.Servicio, db: Session) -> dict:
    costo_fijo_hora = get_costo_fijo_por_hora(db)
    costo_materiales = get_costo_insumos_servicio(servicio)
    duracion_h = (servicio.duracion_min or 0) / 60
    costo_tiempo = costo_fijo_hora * duracion_h
    costo_total = costo_materiales + costo_tiempo

    tiene_insumos = len(servicio.productos_usados) > 0
    tiene_duracion = bool(servicio.duracion_min and servicio.duracion_min > 0)
    tiene_costos_fijos = costo_fijo_hora > 0

    margen = servicio.precio - costo_total
    margen_pct = (margen / servicio.precio * 100) if servicio.precio > 0 else 0.0

    sin_datos = not tiene_insumos and not tiene_costos_fijos
    if sin_datos:
        estado = "sin_datos"
    elif margen_pct >= 30:
        estado = "saludable"
    elif margen_pct >= 15:
        estado = "advertencia"
    else:
        estado = "critico"

    return {
        "servicio": servicio,
        "costo_materiales": costo_materiales,
        "costo_tiempo": costo_tiempo,
        "costo_total": costo_total,
        "margen": margen,
        "margen_pct": margen_pct,
        "estado": estado,
        "tiene_insumos": tiene_insumos,
        "tiene_duracion": tiene_duracion,
        "sin_datos": sin_datos,
    }


def get_punto_equilibrio(db: Session) -> dict:
    servicios = db.query(models.Servicio).filter_by(activo=True).all()
    if not servicios:
        return {"servicios_minimos": None, "margen_contribucion_promedio": 0, "servicios_por_dia": None}

    total_fijos = sum(
        c.monto for c in db.query(models.CostoFijo).filter_by(activo=True).all()
    )
    cfg = get_config(db)
    dias = cfg.dias_trabajo_mes if cfg else 22

    costos_var = [get_costo_insumos_servicio(s) for s in servicios]
    precios = [s.precio for s in servicios]
    precio_prom = sum(precios) / len(precios)
    costo_var_prom = sum(costos_var) / len(costos_var)
    contribucion = precio_prom - costo_var_prom

    if contribucion <= 0 or total_fijos == 0:
        return {"servicios_minimos": None, "margen_contribucion_promedio": contribucion, "servicios_por_dia": None}

    servicios_minimos = total_fijos / contribucion
    return {
        "servicios_minimos": round(servicios_minimos),
        "margen_contribucion_promedio": round(contribucion),
        "servicios_por_dia": round(servicios_minimos / dias, 1) if dias > 0 else None,
    }

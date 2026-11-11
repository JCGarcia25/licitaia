"""Cazador en lote + generación de alertas (usado por tareas, API y semilla)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Alert, CompanyProfile, Opportunity, UserOpportunity
from app.services.embeddings import embed
from app.services.matcher import score_opportunity

def email_html(title: str, lines: list[str], cta_url: str | None = None) -> str:
    rows = "".join(f"<p style='margin:8px 0;color:#cbd5e1'>{line}</p>" for line in lines)
    cta = f"<p style='margin:26px 0 8px'><a href='{cta_url}' style='display:inline-block;background:#2dd4bf;color:#062238;text-decoration:none;font-weight:700;padding:13px 22px;border-radius:8px'>Ir a MySECOP</a></p>" if cta_url else ""
    return f"""<div style='background:#07182b;padding:32px;font-family:Arial,sans-serif;color:#f8fafc'>
      <div style='max-width:620px;margin:auto;background:#102942;border:1px solid #234766;border-radius:16px;padding:28px'>
      <div style='font-size:22px;font-weight:700;color:#2dd4bf;margin-bottom:24px'>MS&nbsp; MySECOP</div>
      <h1 style='font-size:22px;margin:0 0 16px'>{title}</h1>{rows}{cta}
      <p style='margin-top:24px;color:#94a3b8;font-size:12px'>La fuente oficial de referencia es siempre el expediente en SECOP.</p>
      </div></div>"""


def profile_dict(profile: CompanyProfile) -> dict:
    if not profile:
        return {}
    return {
        "sector": profile.sector,
        "actividades": profile.actividades,
        "productos_servicios": profile.productos_servicios,
        "keywords": profile.keywords or [],
        "unspsc_codes": profile.unspsc_codes or [],
        "departamentos": profile.departamentos or [],
        "municipios": profile.municipios or [],
        "presupuesto_min": profile.presupuesto_min,
        "presupuesto_max": profile.presupuesto_max,
        "modalidades": profile.modalidades or [],
        "experiencia": profile.experiencia,
        "capacidades": profile.capacidades,
        "certificaciones": profile.certificaciones or [],
        "acepta_consorcios": profile.acepta_consorcios,
    }


def profile_is_configured(profile: CompanyProfile | None) -> bool:
    """Indica si el usuario tiene datos suficientes para identificar su actividad."""
    return bool(profile and any([
        (profile.sector or "").strip(),
        (profile.actividades or "").strip(),
        (profile.productos_servicios or "").strip(),
        profile.keywords,
        profile.unspsc_codes,
        profile.departamentos,
        profile.municipios,
        profile.modalidades,
    ]))


def has_profile_match(user_opportunity: UserOpportunity) -> bool:
    """Requiere al menos una coincidencia verificable con el perfil empresarial.

    El puntaje por sí solo no basta: un proceso puede superar el umbral por
    factores generales. Las razones persistidas por el agente son la evidencia
    de que hubo coincidencia semántica, léxica, UNSPSC, geográfica, económica
    o de modalidad con el perfil.
    """
    for reason in user_opportunity.reasons or []:
        factor = str((reason or {}).get("factor", "")).strip().lower()
        if factor and factor not in {"sin coincidencias fuertes", "riesgo"}:
            return True
    return False


def rescore_user(db: Session, user_id: int, limit: int = 1500) -> int:
    """Re-evalúa todas las oportunidades abiertas para un usuario (Agente 1)."""
    profile = db.query(CompanyProfile).filter(CompanyProfile.user_id == user_id).first()
    if not profile:
        return 0
    p_dict = profile_dict(profile)
    p_vector = embed(" ".join(str(x) for x in [p_dict["sector"], p_dict["actividades"], p_dict["productos_servicios"], " ".join(p_dict["keywords"])]))
    opps = db.query(Opportunity).limit(limit).all()  # incluye cancelados: se puntúan con penalización
    existing = {uo.opportunity_id: uo for uo in db.query(UserOpportunity).filter(UserOpportunity.user_id == user_id).all()}
    scored = 0
    for opp in opps:
        vector = opp.embedding.vector if opp.embedding else None
        result = score_opportunity(p_dict, {
            "objeto": opp.objeto, "descripcion": opp.descripcion, "modalidad": opp.modalidad,
            "tipo_contrato": opp.tipo_contrato, "unspsc_code": opp.unspsc_code,
            "departamento": opp.departamento, "valor": opp.valor, "estado": opp.estado,
            "cancelled": opp.cancelled, "_vector": vector,
        }, profile_vector=p_vector, learning_weights=(profile.learning_weights or None))
        uo = existing.get(opp.id)
        if not uo:
            uo = UserOpportunity(user_id=user_id, opportunity_id=opp.id)
            db.add(uo)
        uo.score = result.score
        uo.reasons = result.reasons
        scored += 1
    db.commit()
    return scored


def create_alerts_for_user(db: Session, user_id: int, high_score: int = 70) -> int:
    """Crea alertas solo si cumplen umbral y coincidencia con el perfil."""
    profile = db.query(CompanyProfile).filter(CompanyProfile.user_id == user_id).first()
    if not profile_is_configured(profile):
        # No se deben mostrar alertas de compatibilidad sin un perfil que
        # permita justificar la coincidencia.
        db.query(Alert).filter(
            Alert.user_id == user_id,
            Alert.tipo == "alta_compatibilidad",
        ).delete(synchronize_session=False)
        db.commit()
        return 0

    # Mantiene la bandeja alineada con el umbral vigente: una alerta antigua
    # no debe seguir mostrando "alta compatibilidad" si su score quedó por
    # debajo del valor configurado por el usuario.
    stale = []
    existing_alerts = db.query(Alert).filter(
        Alert.user_id == user_id,
        Alert.tipo == "alta_compatibilidad",
    ).all()
    user_opportunities = {
        uo.opportunity_id: uo
        for uo in db.query(UserOpportunity).filter(UserOpportunity.user_id == user_id).all()
    }
    for alert in existing_alerts:
        uo = user_opportunities.get(alert.opportunity_id)
        if not uo or uo.score is None or uo.score < high_score or not has_profile_match(uo):
            stale.append(alert)
    for alert in stale:
        db.delete(alert)
    if stale:
        db.flush()
    rows = (
        db.query(UserOpportunity, Opportunity)
        .join(Opportunity, Opportunity.id == UserOpportunity.opportunity_id)
        .filter(UserOpportunity.user_id == user_id, UserOpportunity.score >= high_score)
        .all()
    )
    rows = [(uo, opp) for uo, opp in rows if has_profile_match(uo)]
    created = 0
    for uo, opp in rows:
        exists = db.query(Alert).filter(
            Alert.user_id == user_id, Alert.opportunity_id == opp.id,
            Alert.tipo == "alta_compatibilidad",
        ).first()
        if exists:
            continue
        db.add(Alert(
            user_id=user_id, opportunity_id=opp.id, tipo="alta_compatibilidad",
            title=f"{uo.score:.0f}% de compatibilidad: {(opp.objeto or 'Proceso')[:90]}",
            body=f"Entidad: {opp.entidad or 'N/D'} · Valor: {opp.valor or 0:,.0f} COP · {opp.departamento or 'N/D'}",
        ))
        created += 1
    db.commit()
    return created


def close_reminders(db: Session, user_id: int, days: list[int] | None = None) -> int:
    """Recordatorios de cierre (D-10, D-5, D-1) según fecha_cierre conocida o analizada."""
    from app.db.models import Analysis

    days = days or [10, 5, 1]
    created = 0
    rows = (
        db.query(UserOpportunity, Opportunity)
        .join(Opportunity, Opportunity.id == UserOpportunity.opportunity_id)
        .filter(UserOpportunity.user_id == user_id, UserOpportunity.triage.in_(["guardada", "proyecto"]))
        .all()
    )
    for uo, opp in rows:
        cierre = opp.fecha_cierre
        if not cierre:
            analysis = db.query(Analysis).filter(Analysis.opportunity_id == opp.id).order_by(Analysis.created_at.desc()).first()
            raw = ((analysis or {}).resumen_ejecutivo or {}).get("fecha_hora_cierre", {}).get("valor") if analysis else None
            cierre = None  # la fuente no expone cierre: solo recordamos si hay fecha analizada/ingresada
            if raw:
                for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                    try:
                        cierre = datetime.strptime(str(raw)[:16].strip(), fmt)
                        break
                    except ValueError:
                        continue
        if not cierre:
            continue
        dias = (cierre - datetime.utcnow()).days
        for d in days:
            if dias == d:
                exists = db.query(Alert).filter(
                    Alert.user_id == user_id, Alert.opportunity_id == opp.id, Alert.tipo == "cierre_proximo",
                ).order_by(Alert.created_at.desc()).first()
                if exists and (datetime.utcnow() - exists.created_at).days < 1:
                    continue
                db.add(Alert(
                    user_id=user_id, opportunity_id=opp.id, tipo="cierre_proximo",
                    title=f"Fecha de cierre en {d} día(s): {(opp.objeto or 'Proceso')[:90]}",
                    body=f"Cierre estimado: {cierre:%d/%m/%Y %H:%M} (fecha analizada en pliegos o registrada por el usuario).",
                ))
                created += 1
    db.commit()
    return created

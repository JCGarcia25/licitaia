"""Cazador en lote + generación de alertas (usado por tareas, API y semilla)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Alert, CompanyProfile, Opportunity, UserOpportunity
from app.services.embeddings import embed
from app.services.matcher import score_opportunity


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
        }, profile_vector=p_vector)
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
    """Alerta in-app por oportunidades de alta compatibilidad."""
    rows = (
        db.query(UserOpportunity, Opportunity)
        .join(Opportunity, Opportunity.id == UserOpportunity.opportunity_id)
        .filter(UserOpportunity.user_id == user_id, UserOpportunity.score >= high_score)
        .all()
    )
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

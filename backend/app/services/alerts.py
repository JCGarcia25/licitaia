"""Cazador en lote + generación de alertas (usado por tareas, API y semilla)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Alert, CompanyProfile, Opportunity, UserOpportunity
from app.services.embeddings import embed
from app.services.matcher import domain_terms, score_opportunity
from app.services.opportunity_status import classify_opportunity
from app.services.opportunity_filters import profile_constraints

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


def has_profile_match(user_opportunity: UserOpportunity, profile: CompanyProfile, opportunity: Opportunity) -> bool:
    """Exige coincidencias actuales con la actividad o la categoría de la empresa."""
    codes = {str(code).strip() for code in (profile.unspsc_codes or [])}
    if opportunity.unspsc_code and str(opportunity.unspsc_code).strip() in codes:
        return True
    profile_text = ' '.join(str(value or '') for value in (
        profile.sector, profile.actividades, profile.productos_servicios,
        ' '.join(profile.keywords or []),
    ))
    opportunity_text = ' '.join(str(value or '') for value in (opportunity.objeto, opportunity.descripcion))
    return bool(domain_terms(profile_text) & domain_terms(opportunity_text))


def opportunity_is_current(opportunity: Opportunity) -> bool:
    return classify_opportunity(opportunity)['status'] in {'OPEN', 'UNKNOWN'}


def rescore_user(db: Session, user_id: int) -> int:
    """Adaptador explícito para semillas/CLI; HTTP utiliza trabajos asíncronos."""
    from app.services.match_jobs import process_batch, request_job
    job = request_job(db, user_id)
    identifier = job.id
    db.commit()
    while True:
        result = process_batch(db, identifier)
        if result['status'] != 'PENDING':
            break
    db.expire_all()
    from app.db.models import MatchJob
    return db.get(MatchJob, identifier).scored


def iter_visible_alerts(db, user_id, threshold=70, unread=False):
    """Una misma política para bandeja, dashboard y ambos resúmenes."""
    from sqlalchemy import and_, or_
    from app.services.match_versions import current_score_condition
    profile = db.query(CompanyProfile).filter_by(user_id=user_id).first()
    rows = (db.query(Alert, UserOpportunity, Opportunity)
        .outerjoin(UserOpportunity, and_(UserOpportunity.user_id == Alert.user_id,
                                        UserOpportunity.opportunity_id == Alert.opportunity_id))
        .outerjoin(Opportunity, Opportunity.id == Alert.opportunity_id)
        .filter(Alert.user_id == user_id,
            or_(Alert.tipo != 'alta_compatibilidad', and_(current_score_condition(), UserOpportunity.score >= threshold,
                func.coalesce(UserOpportunity.triage, 'detectada') != 'descartada', *profile_constraints(profile))))
        .order_by(Alert.created_at.desc(), Alert.id.desc()))
    if unread:
        rows = rows.filter(Alert.read_at.is_(None))
    for alert, uo, opp in rows.yield_per(200):
        if alert.tipo == 'alta_compatibilidad' and (not profile_is_configured(profile) or not opp
                or not has_profile_match(uo, profile, opp)):
            continue
        yield alert


def create_alerts_for_user(db: Session, user_id: int, high_score: int = 70) -> int:
    """Actualiza alertas vigentes por lotes; las antiguas se conservan ocultas."""
    from app.core.config import get_settings
    from app.services.match_versions import current_score_condition
    profile = db.query(CompanyProfile).filter_by(user_id=user_id).first()
    if not profile_is_configured(profile):
        return 0
    cursor, created = 0, 0
    while True:
        rows = (db.query(UserOpportunity, Opportunity)
            .join(Opportunity, Opportunity.id == UserOpportunity.opportunity_id)
            .filter(UserOpportunity.user_id == user_id, UserOpportunity.id > cursor,
                    current_score_condition(), UserOpportunity.score >= high_score,
                    func.coalesce(UserOpportunity.triage, 'detectada') != 'descartada', *profile_constraints(profile))
            .order_by(UserOpportunity.id).limit(get_settings().match_batch_size).all())
        if not rows:
            break
        ids = [opp.id for _, opp in rows]
        previous = {a.opportunity_id: a for a in db.query(Alert).filter(
            Alert.user_id == user_id, Alert.opportunity_id.in_(ids), Alert.tipo == 'alta_compatibilidad').all()}
        for uo, opp in rows:
            cursor = uo.id
            if not has_profile_match(uo, profile, opp):
                continue
            alert = previous.get(opp.id)
            if alert is None:
                alert = Alert(user_id=user_id, opportunity_id=opp.id, tipo='alta_compatibilidad')
                db.add(alert)
                created += 1
            alert.title = f"{uo.score:.0f}% de compatibilidad: {(opp.objeto or 'Proceso')[:90]}"
            alert.body = f"Entidad: {opp.entidad or 'N/D'} · Valor: {opp.valor or 0:,.0f} COP · {opp.departamento or 'N/D'}"
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
            analysis = db.query(Analysis).filter(Analysis.opportunity_id == opp.id, Analysis.user_id == user_id).order_by(Analysis.created_at.desc()).first()
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

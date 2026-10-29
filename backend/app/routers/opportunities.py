"""Dashboard y oportunidades: filtros, buscador de lenguaje natural, triage, métricas."""
from datetime import datetime, timedelta
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Alert, AlertPrefs, Analysis, CompanyProfile, Opportunity, User, UserOpportunity
from app.db.session import get_db
from app.schemas import FeedbackIn, TriajeIn
from app.services import alerts as alerts_service
from app.services import nlq

router = APIRouter(prefix="/api", tags=["dashboard"])


def _user_scores(db: Session, user_id: int) -> dict[int, UserOpportunity]:
    rows = db.query(UserOpportunity).filter(UserOpportunity.user_id == user_id).all()
    return {r.opportunity_id: r for r in rows}


def _serialize(opp: Opportunity, uo: UserOpportunity | None) -> dict:
    return {
        "id": opp.id, "source": opp.source, "source_id": opp.source_id,
        "entidad": opp.entidad, "nit_entidad": opp.nit_entidad,
        "departamento": opp.departamento, "ciudad": opp.ciudad,
        "objeto": opp.objeto, "descripcion": opp.descripcion,
        "modalidad": opp.modalidad, "tipo_contrato": opp.tipo_contrato,
        "unspsc_code": opp.unspsc_code, "valor": opp.valor,
        "estado": opp.estado, "fecha_publicacion": opp.fecha_publicacion,
        "fecha_cierre": opp.fecha_cierre,
        "url_oficial": None if "binpar.cloud" in (opp.url_oficial or "").lower() else opp.url_oficial,
        "cancelled": opp.cancelled, "captured_at": opp.captured_at, "updated_at": opp.updated_at,
        "score": uo.score if uo else None,
        "triage": uo.triage if uo else "detectada",
        "reasons": uo.reasons if uo else [],
    }


@router.get("/opportunities")
def list_opportunities(
    q: str | None = None,
    departamento: str | None = None,
    modalidad: str | None = None,
    source: str | None = None,
    estado: str | None = None,
    valor_min: float | None = None,
    valor_max: float | None = None,
    score_min: float | None = Query(default=None, ge=0, le=100),
    triage: str | None = Query(default=None, pattern="^(detectada|guardada|descartada|proyecto)$"),
    include_cancelled: bool = False,
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    solo_con_score: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Opportunity)
    if not include_cancelled:
        query = query.filter(Opportunity.cancelled.is_(False))
    if q:
        stopwords = {"procesos", "proceso", "contratación", "contratacion", "pública", "publica", "superior", "millones", "pesos", "buscar", "para", "con", "los", "las", "del", "una"}
        words = [w for w in re.split(r"[^\wáéíóúñü]+", q.lower()) if len(w) > 3 and w not in stopwords][:8]
        if words:
            for word in words:
                like = f"%{word}%"
                query = query.filter(or_(
                    Opportunity.objeto.ilike(like), Opportunity.entidad.ilike(like), Opportunity.descripcion.ilike(like),
                ))
        if any(term in q.lower() for term in ("abierto", "abiertos", "publicado", "publicados")):
            query = query.filter(
                ~Opportunity.estado.ilike("%cancel%"),
                ~Opportunity.estado.ilike("%cerrad%"),
                ~Opportunity.estado.ilike("%adjudic%"),
                ~Opportunity.estado.ilike("%terminado%"),
            )
    if departamento:
        query = query.filter(Opportunity.departamento.ilike(f"%{departamento}%"))
    if modalidad:
        query = query.filter(Opportunity.modalidad.ilike(f"%{modalidad}%"))
    if source:
        query = query.filter(Opportunity.source == source)
    if estado:
        query = query.filter(Opportunity.estado.ilike(f"%{estado}%"))
    if valor_min is not None:
        query = query.filter(Opportunity.valor >= valor_min)
    if valor_max is not None:
        query = query.filter(Opportunity.valor <= valor_max)

    scores = _user_scores(db, user.id)
    rows = query.order_by(Opportunity.updated_at.desc()).offset(offset).limit(limit).all()
    total = query.count()
    items = []
    for opp in rows:
        uo = scores.get(opp.id)
        if solo_con_score and not uo:
            continue
        if triage and (not uo or uo.triage != triage):
            continue
        if score_min is not None and (not uo or uo.score < score_min):
            continue
        items.append(_serialize(opp, uo))
    if triage or score_min is not None or solo_con_score:
        # filtra también dentro del total real
        all_rows = query.all()
        filtered = []
        for opp in all_rows:
            uo = scores.get(opp.id)
            if triage and (not uo or uo.triage != triage):
                continue
            if score_min is not None and (not uo or uo.score < score_min):
                continue
            if solo_con_score and not uo:
                continue
            filtered.append(opp)
        total = len(filtered)
        items = [_serialize(o, scores.get(o.id)) for o in filtered[offset:offset + limit]]
    return {"total": total, "items": items}


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(opportunity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Oportunidad no encontrada")
    uo = db.query(UserOpportunity).filter(
        UserOpportunity.user_id == user.id, UserOpportunity.opportunity_id == opp.id
    ).first()
    data = _serialize(opp, uo)
    analysis = db.query(Analysis).filter(Analysis.opportunity_id == opp.id).order_by(Analysis.created_at.desc()).first()
    data["analysis"] = {
        "id": analysis.id, "resumen": analysis.resumen_ejecutivo, "requisitos": analysis.requisitos,
        "estado": analysis.estado, "created_at": analysis.created_at,
    } if analysis else None
    return data


@router.post("/opportunities/{opportunity_id}/triaje")
def set_triaje(opportunity_id: int, data: TriajeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Oportunidad no encontrada")
    uo = db.query(UserOpportunity).filter(
        UserOpportunity.user_id == user.id, UserOpportunity.opportunity_id == opp.id
    ).first()
    if not uo:
        uo = UserOpportunity(user_id=user.id, opportunity_id=opp.id, score=0, reasons=[])
        db.add(uo)
    uo.triage = data.triage
    db.commit()
    return {"id": opp.id, "triage": uo.triage}


@router.post("/opportunities/{opportunity_id}/feedback")
def feedback(opportunity_id: int, data: FeedbackIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fase 3: retroalimentación del usuario — ajusta los pesos de aprendizaje del perfil
    y mejora recomendaciones futuras al re-puntuar (POST /api/rescore)."""
    uo = db.query(UserOpportunity).filter(
        UserOpportunity.user_id == user.id, UserOpportunity.opportunity_id == opportunity_id
    ).first()
    if not uo:
        raise HTTPException(404, "Oportunidad no puntuada para este usuario")
    uo.feedback = data.util
    uo.feedback_note = data.nota
    profile = db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first()
    weights = None
    if profile is not None and uo.reasons:
        w = dict(profile.learning_weights or {})
        delta = 1.0 if data.util else -1.0
        for r in uo.reasons[:5]:
            factor = (r or {}).get("factor")
            if factor:
                w[factor] = round(max(-10.0, min(10.0, w.get(factor, 0.0) + delta)), 1)
        profile.learning_weights = w
        weights = w
    db.commit()
    return {"ok": True, "feedback": data.util, "learning_weights": weights,
            "nota": "Ejecute POST /api/rescore para aplicar los nuevos pesos."}


@router.post("/search")
def smart_search(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Buscador en lenguaje natural → filtros estructurados + resultados."""
    parsed = nlq.parse_query(payload.get("q", ""))
    filtros = nlq.parsed_to_filters(parsed)
    query = db.query(Opportunity)
    if not filtros.get("estado"):
        query = query.filter(Opportunity.cancelled.is_(False))
    if filtros.get("q"):
        for word in filtros["q"].split():
            like = f"%{word}%"
            query = query.filter(or_(Opportunity.objeto.ilike(like), Opportunity.descripcion.ilike(like)))
    if filtros.get("departamento"):
        query = query.filter(Opportunity.departamento.ilike(f"%{filtros['departamento']}%"))
    if filtros.get("modalidad"):
        query = query.filter(Opportunity.modalidad.ilike(f"%{filtros['modalidad']}%"))
    if filtros.get("estado") == "abiertos":
        query = query.filter(~Opportunity.estado.ilike("%adjudicado%"), ~Opportunity.estado.ilike("%cerrado%"), ~Opportunity.estado.ilike("%cancelado%"))
    if filtros.get("valor_min") is not None:
        query = query.filter(Opportunity.valor >= filtros["valor_min"])
    if filtros.get("valor_max") is not None:
        query = query.filter(Opportunity.valor <= filtros["valor_max"])
    if filtros.get("publicado_dias"):
        query = query.filter(Opportunity.fecha_publicacion >= datetime.utcnow() - timedelta(days=filtros["publicado_dias"]))
    rows = query.order_by(Opportunity.updated_at.desc()).limit(50).all()
    scores = _user_scores(db, user.id)
    return {"filtros_interpretados": filtros, "total": len(rows),
            "items": [_serialize(o, scores.get(o.id)) for o in rows]}


@router.get("/dashboard/metrics")
def metrics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    scores = _user_scores(db, user.id)
    base = db.query(Opportunity).filter(Opportunity.cancelled.is_(False))
    ahora = datetime.utcnow()
    uos = db.query(UserOpportunity).filter(UserOpportunity.user_id == user.id).all()
    ids = list(scores.keys())
    opps = {o.id: o for o in db.query(Opportunity).filter(Opportunity.id.in_(ids)).all()} if ids else {}

    alta = [s for s in uos if s.score >= 70 and s.triage != "descartada"]
    guardadas = [s for s in uos if s.triage == "guardada"]
    descartadas = [s for s in uos if s.triage == "descartadas" or s.triage == "descartada"]
    proyectos = [s for s in uos if s.triage == "proyecto"]
    valor_total = sum((opps[s.opportunity_id].valor or 0) for s in alta if s.opportunity_id in opps)

    # tendencia por mes (últimos 6 meses) según fecha_publicacion
    tendencia: dict[str, int] = {}
    for i in range(5, -1, -1):
        mes = (ahora.month - i - 1) % 12 + 1
        anio = ahora.year - (1 if ahora.month - i <= 0 else 0)
        tendencia[f"{anio}-{mes:02d}"] = 0
    for o in opps.values():
        if o.fecha_publicacion:
            key = f"{o.fecha_publicacion.year}-{o.fecha_publicacion.month:02d}"
            if key in tendencia:
                tendencia[key] += 1

    docs_pendientes = db.query(Analysis).filter(Analysis.user_id == user.id, Analysis.estado == "borrador").count()
    alertas_no_leidas = db.query(Alert).filter(Alert.user_id == user.id, Alert.read_at.is_(None)).count()

    # próximos a cerrar: solo con fecha de cierre conocida (analizada o registrada);
    # la fuente SECOP II (p6dx-8zbt) NO expone fecha de cierre (ver docs/fuentes-secop.md)
    proximos = 0
    for s in guardadas + proyectos:
        o = opps.get(s.opportunity_id)
        if not o or not o.fecha_cierre:
            continue
        dias = (o.fecha_cierre - ahora).days
        if 0 <= dias <= 7:
            proximos += 1
    return {
        "oportunidades_detectadas": len(uos),
        "procesos_nuevos_base": base.filter(Opportunity.fecha_publicacion >= ahora - timedelta(days=7)).count(),
        "proximos_a_cerrar": proximos,
        "alta_compatibilidad": len(alta),
        "valor_agregado_cop": valor_total,
        "guardadas": len(guardadas),
        "descartadas": len(descartadas),
        "proyectos_propuesta": len(proyectos),
        "documentos_pendientes": docs_pendientes,
        "alertas_no_leidas": alertas_no_leidas,
        "tendencia_mensual": [{"mes": k, "total": v} for k, v in tendencia.items()],
    }


@router.post("/rescore")
def rescore(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(400, "Complete su perfil empresarial para activar al Agente 1")
    scored = alerts_service.rescore_user(db, user.id)
    prefs = db.query(AlertPrefs).filter(AlertPrefs.user_id == user.id).first()
    threshold = prefs.high_score_threshold if prefs else 70
    created = alerts_service.create_alerts_for_user(db, user.id, high_score=threshold)
    return {"puntuadas": scored, "alertas_creadas": created}

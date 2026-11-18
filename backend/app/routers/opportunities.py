"""Dashboard y oportunidades: filtros, buscador de lenguaje natural, triage, métricas."""
from datetime import datetime, timedelta
import re
import unicodedata
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from sqlalchemy import and_, cast, func, or_, Text
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Alert, AlertPrefs, Analysis, CompanyProfile, OfferProject, Opportunity, User, UserOpportunity
from app.db.session import get_db
from app.schemas import FeedbackIn, TriajeIn, MatchJobOut
from app.services import alerts as alerts_service
from app.services import nlq
from app.services.match_jobs import coverage
from app.services.opportunity_status import classify_opportunity, potentially_current_condition
from app.services.match_versions import current_score_condition, calculation_state, score_versions_condition, failed_score_condition
from app.services.opportunity_filters import _location_condition, _text_variants, _modality_condition, profile_constraints
from pydantic import BaseModel

from app.services.saved_opportunities import saved_first, saved_condition, is_saved

router = APIRouter(prefix="/api", tags=["dashboard"])

class OpportunitySearchState(BaseModel):
    q: str = ""
    departamento: str = ""
    municipio: str = ""
    modalidad: str = ""
    valorMin: str = ""
    scoreMin: str = ""
    triage: str = ""
    soloScore: bool = False

@router.get("/opportunities/last-search")
def get_last_opportunity_search(user: User = Depends(get_current_user)):
    return {"search": user.last_opportunity_search}

@router.put("/opportunities/last-search")
def save_last_opportunity_search(payload: OpportunitySearchState = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.last_opportunity_search = payload.model_dump()
    db.commit()
    return {"search": user.last_opportunity_search}
PROFILE_MATCH_MIN_SCORE = 40


def _vigente_condition():
    """Procesos publicados y no terminales según el estado disponible en SECOP.

    El dataset p6dx-8zbt no expone fecha de cierre; por eso la vigencia se
    determina con la fecha de publicación (no futura) y los estados oficiales
    de cierre/cancelación/adjudicación. Nunca se infiere una fecha de cierre.
    """
    return potentially_current_condition()


def _public_document_count(value) -> int:
    if isinstance(value, dict):
        return sum(_public_document_count(v) for v in value.values())
    if isinstance(value, list):
        return sum(_public_document_count(v) for v in value)
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        low = value.lower()
        if any(host in low for host in ("secop.gov.co", "datos.gov.co", "colombiacompra.gov.co")) and any(ext in low for ext in (".pdf", ".docx", ".xlsx", "document", "anexo", "pliego")):
            return 1
    return 0


def _user_scores(db: Session, user_id: int, opportunity_ids: list[int] | None = None) -> dict[int, UserOpportunity]:
    """Carga solo los scores necesarios para evitar crecer en memoria con el historial."""
    query = db.query(UserOpportunity).filter(UserOpportunity.user_id == user_id)
    if opportunity_ids is not None:
        if not opportunity_ids:
            return {}
        query = query.filter(UserOpportunity.opportunity_id.in_(opportunity_ids))
    rows = query.with_entities(UserOpportunity, current_score_condition(), failed_score_condition()).all()
    result = {}
    for row, current, versions_current in rows:
        row._match_current = bool(current)
        row._match_failed_current = bool(versions_current)
        result[row.opportunity_id] = row
    return result


def _serialize(opp: Opportunity, uo: UserOpportunity | None) -> dict:
    url = opp.url_oficial
    if "binpar.cloud" in (url or "").lower():
        url = None
    elif "/STS/Users/Login/Index" in (url or ""):
        # This is only SECOP's login landing page, not the expediente. Do not
        # fabricate a noticeUID URL: SECOP rejects IDs that are not notices.
        url = None
    if url:
        host = (urlparse(url).hostname or "").lower()
        if host not in {"community.secop.gov.co", "www.colombiacompra.gov.co", "colombiacompra.gov.co"}:
            url = None
    match_state = calculation_state(uo)
    return {
        "id": opp.id, "source": opp.source, "source_id": opp.source_id,
        "entidad": opp.entidad, "nit_entidad": opp.nit_entidad,
        "departamento": opp.departamento, "ciudad": opp.ciudad,
        "objeto": opp.objeto, "descripcion": opp.descripcion,
        "modalidad": opp.modalidad, "tipo_contrato": opp.tipo_contrato,
        "unspsc_code": opp.unspsc_code, "valor": opp.valor,
        "estado": opp.estado, "fecha_publicacion": opp.fecha_publicacion,
        "vigencia": classify_opportunity(opp),
        "fecha_cierre": opp.fecha_cierre,
        "url_oficial": url,
        # No se usa el dataset general como sustituto de un expediente.
        "url_consulta_secop": None,
        "documentos_publicos_disponibles": _public_document_count(opp.raw_json or {}),
        "cancelled": opp.cancelled, "captured_at": opp.captured_at, "updated_at": opp.updated_at,
        "score": uo.score if uo and match_state == "CURRENT" else None,
        "score_state": match_state,
        "triage": uo.triage if uo else "detectada",
        "is_saved": is_saved(uo),
        "reasons": uo.reasons if uo and match_state == "CURRENT" else [],
    }


@router.get("/opportunities")
def list_opportunities(
    q: str | None = None,
    departamento: str | None = None,
    municipio: str | None = None,
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
    profile_match: bool = False,
    prioritize_saved: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = saved_first(db.query(Opportunity), user.id) if prioritize_saved else db.query(Opportunity)
    profile = db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first()
    # Al abrir Oportunidades, el perfil es el filtro de entrada. Los filtros
    # escritos por el usuario tienen prioridad para permitir explorar después.
    profile_configured = alerts_service.profile_is_configured(profile)
    if profile_match and not profile_configured:
        return {"total": 0, "items": [], "profile_configured": False, "profile_required": True}
    if profile_match and profile:
        query = query.filter(*profile_constraints(profile, departamento, municipio, modalidad, valor_min, valor_max))
    if not include_cancelled:
        query = query.filter(_vigente_condition())
    if q:
        stopwords = {"procesos", "proceso", "contratación", "contratacion", "pública", "publica", "superior", "millones", "pesos", "buscar", "para", "con", "los", "las", "del", "una"}
        words = [w for w in re.split(r"[^\wáéíóúñü]+", q.lower()) if len(w) > 3 and w not in stopwords][:8]
        if words:
            # La búsqueda debe ser tolerante: una consulta en lenguaje natural
            # no debe exigir que cada palabra aparezca literalmente en el mismo
            # campo. SECOP distribuye el texto entre objeto, descripción y
            # entidad; se acepta cualquier término relevante y se prioriza la
            # coincidencia de la frase completa cuando exista.
            term_conditions = []
            for word in words:
                term_conditions.append(or_(*[
                    clause
                    for variant in _text_variants(word)
                    for clause in (
                        Opportunity.objeto.ilike(f"%{variant}%"), Opportunity.entidad.ilike(f"%{variant}%"),
                        Opportunity.descripcion.ilike(f"%{variant}%"), Opportunity.modalidad.ilike(f"%{variant}%"),
                        Opportunity.tipo_contrato.ilike(f"%{variant}%"),
                    )
                ]))
            query = query.filter(or_(*term_conditions))
            phrase = " ".join(words)
            query = query.order_by(
                (func.lower(func.coalesce(Opportunity.objeto, "")).like(f"%{phrase}%")).desc(),
                Opportunity.updated_at.desc(), Opportunity.id.desc(),
            )
        if any(term in q.lower() for term in ("abierto", "abiertos", "publicado", "publicados")):
            query = query.filter(
                ~Opportunity.estado.ilike("%cancel%"),
                ~Opportunity.estado.ilike("%cerrad%"),
                ~Opportunity.estado.ilike("%adjudic%"),
                ~Opportunity.estado.ilike("%terminado%"),
            )
    if departamento:
        query = query.filter(_location_condition(Opportunity.departamento, departamento))
    if municipio:
        query = query.filter(_location_condition(Opportunity.ciudad, municipio))
    if modalidad:
        query = query.filter(_modality_condition(modalidad))
    if source:
        query = query.filter(Opportunity.source == source)
    if estado:
        query = query.filter(Opportunity.estado.ilike(f"%{estado}%"))
    if valor_min is not None:
        query = query.filter(Opportunity.valor >= valor_min)
    if valor_max is not None:
        query = query.filter(Opportunity.valor <= valor_max)

    # Los filtros de puntuación/triage deben aplicarse en SQL antes de contar y
    # paginar. Antes se paginaban primero y se filtraban después, provocando
    # páginas vacías aunque existieran coincidencias en páginas posteriores.
    user_opp = db.query(UserOpportunity).filter(
        UserOpportunity.user_id == user.id,
        UserOpportunity.opportunity_id == Opportunity.id,
    ).correlate(Opportunity)
    user_project = db.query(OfferProject).filter(
        OfferProject.user_id == user.id,
        OfferProject.opportunity_id == Opportunity.id,
        OfferProject.status != "archivado",
    )
    # Descartar es persistente para este usuario: no debe reaparecer en nuevas
    # búsquedas, salvo que se solicite explícitamente el filtro de descartadas.
    if triage != "descartada":
        query = query.filter(~user_opp.filter(UserOpportunity.triage == "descartada").exists())
    if solo_con_score or profile_match:
        min_score = (score_min if score_min is not None else PROFILE_MATCH_MIN_SCORE) if profile_match else 0
        query = query.filter(user_opp.filter(current_score_condition(), UserOpportunity.score >= min_score).exists())
    if triage == "guardada":
        query = query.filter(user_opp.filter(saved_condition()).exists())
    elif triage == "proyecto":
        query = query.filter(or_(user_opp.filter(UserOpportunity.triage == "proyecto").exists(), user_project.exists()))
    elif triage == "detectada":
        query = query.filter(or_(~user_opp.exists(), user_opp.filter(UserOpportunity.triage == "detectada").exists()))
    elif triage:
        query = query.filter(user_opp.filter(UserOpportunity.triage == triage).exists())
    if score_min is not None:
        query = query.filter(user_opp.filter(current_score_condition(), UserOpportunity.score >= score_min).exists())

    if profile_match and profile:
        # La relevancia debe verificarse antes de paginar y ordenar: de lo
        # contrario se muestran coincidencias genéricas o no las de mayor score.
        # La afinidad léxica utiliza domain_terms en Python; el recorrido por
        # lotes limita memoria sin paginar antes de aplicar ese criterio.
        ranked_query = query.order_by(None)
        if prioritize_saved: ranked_query = saved_first(ranked_query, user.id)
        ranked = (ranked_query.join(UserOpportunity, and_(
            UserOpportunity.opportunity_id == Opportunity.id,
            UserOpportunity.user_id == user.id,
        )).with_entities(Opportunity, UserOpportunity)
            .order_by(UserOpportunity.score.desc(), Opportunity.id.desc()))
        total, items = 0, []
        for opp, score in ranked.yield_per(200):
            if not alerts_service.opportunity_is_current(opp) or not alerts_service.has_profile_match(score, profile, opp):
                continue
            if offset <= total < offset + limit:
                score._match_current = True
                items.append(_serialize(opp, score))
            total += 1
        return {"total": total, "items": items, "profile_configured": True, "profile_required": False}
    total = query.order_by(None).count()
    rows = query.order_by(Opportunity.updated_at.desc(), Opportunity.id.desc()).offset(offset).limit(limit).all()
    scores = _user_scores(db, user.id, [opp.id for opp in rows])
    items = [_serialize(opp, scores.get(opp.id)) for opp in rows]
    return {"total": total, "items": items, "profile_configured": profile_configured, "profile_required": False}


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(opportunity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Oportunidad no encontrada")
    uo = db.query(UserOpportunity).filter(
        UserOpportunity.user_id == user.id, UserOpportunity.opportunity_id == opp.id
    ).first()
    uo = _user_scores(db, user.id, [opp.id]).get(opp.id)
    data = _serialize(opp, uo)
    analysis = db.query(Analysis).filter(Analysis.opportunity_id == opp.id, Analysis.user_id == user.id).order_by(Analysis.created_at.desc()).first()
    data["analysis"] = {
        "id": analysis.id, "resumen": analysis.resumen_ejecutivo, "requisitos": analysis.requisitos,
        "estado": analysis.estado, "created_at": analysis.created_at,
    } if analysis else None
    return data


class SavedIn(BaseModel):
    saved: bool

@router.patch("/opportunities/{opportunity_id}/saved")
def save_opportunity(opportunity_id:int,body:SavedIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    if db.get(Opportunity,opportunity_id) is None:raise HTTPException(404,"Oportunidad no encontrada")
    row=db.query(UserOpportunity).filter_by(user_id=user.id,opportunity_id=opportunity_id).first()
    if row is None:
        row=UserOpportunity(user_id=user.id,opportunity_id=opportunity_id,score=None,reasons=[])
        db.add(row)
        try:db.flush()
        except IntegrityError:
            db.rollback();row=db.query(UserOpportunity).filter_by(user_id=user.id,opportunity_id=opportunity_id).one()
    row.is_saved=body.saved
    if body.saved and row.triage != "proyecto":row.triage="guardada"
    elif not body.saved and row.triage=="guardada":row.triage="detectada"
    db.commit()
    return {"id":opportunity_id,"is_saved":body.saved,"triage":row.triage}


@router.post("/opportunities/{opportunity_id}/triaje")
def set_triaje(opportunity_id: int, data: TriajeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Oportunidad no encontrada")
    uo = db.query(UserOpportunity).filter(
        UserOpportunity.user_id == user.id, UserOpportunity.opportunity_id == opp.id
    ).first()
    if not uo:
        uo = UserOpportunity(user_id=user.id, opportunity_id=opp.id, score=None, reasons=[])
        db.add(uo)
    if data.triage == "guardada": uo.is_saved = True
    elif data.triage in {"detectada", "descartada"}: uo.is_saved = False
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
    # Los selectores explícitos de la interfaz tienen prioridad sobre lo que
    # el parser pueda inferir del texto natural.
    for key in ("departamento", "municipio", "modalidad"):
        if payload.get(key): filtros[key] = payload[key]
    if payload.get("valor_min"):
        filtros["valor_min"] = float(payload["valor_min"])
    query = saved_first(db.query(Opportunity), user.id)
    if not filtros.get("estado") or filtros.get("estado") == "abiertos":
        query = query.filter(_vigente_condition())
    if filtros.get("q"):
        # La búsqueda manual es flexible: basta con que el proceso coincida
        # con al menos un término relevante. Exigir todos los términos hacía
        # que consultas naturales razonables terminaran siempre sin resultados.
        term_clauses = []
        for word in filtros["q"].split():
            variants = _text_variants(word)
            if word in {"movil", "moviles"}: variants += ["móvil", "móviles"]
            term_clauses.append(or_(*[
                clause for variant in variants for clause in (
                    Opportunity.objeto.ilike(f"%{variant}%"), Opportunity.descripcion.ilike(f"%{variant}%"),
                    Opportunity.entidad.ilike(f"%{variant}%"), cast(Opportunity.raw_json, Text).ilike(f"%{variant}%")
                )
            ]))
        if term_clauses:
            # Cada palabra relevante puede coincidir en cualquier campo del
            # registro SECOP, incluidos entidad, descripción y datos crudos.
            query = query.filter(or_(*term_clauses))
    if filtros.get("departamento"):
        query = query.filter(_location_condition(Opportunity.departamento, filtros["departamento"]))
    if filtros.get("municipio"):
        query = query.filter(_location_condition(Opportunity.ciudad, filtros["municipio"]))
    if filtros.get("modalidad"):
        query = query.filter(_modality_condition(filtros["modalidad"]))
    if filtros.get("estado") == "abiertos":
        query = query.filter(~Opportunity.estado.ilike("%adjudicado%"), ~Opportunity.estado.ilike("%cerrado%"), ~Opportunity.estado.ilike("%cancelado%"))
    if filtros.get("valor_min") is not None:
        query = query.filter(Opportunity.valor >= filtros["valor_min"])
    if filtros.get("valor_max") is not None:
        query = query.filter(Opportunity.valor <= filtros["valor_max"])
    if filtros.get("publicado_dias"):
        query = query.filter(Opportunity.fecha_publicacion >= datetime.utcnow() - timedelta(days=filtros["publicado_dias"]))
    limit = min(max(int(payload.get("limit", 25)), 1), 100)
    offset = max(int(payload.get("offset", 0)), 0)
    solo_con_score = bool(payload.get("solo_con_score", False))
    score_min = payload.get("score_min")
    triage = payload.get("triage")
    user_opp = db.query(UserOpportunity).filter(
        UserOpportunity.user_id == user.id,
        UserOpportunity.opportunity_id == Opportunity.id,
    )
    user_project = db.query(OfferProject).filter(
        OfferProject.user_id == user.id,
        OfferProject.opportunity_id == Opportunity.id,
        OfferProject.status != "archivado",
    )
    if triage != "descartada":
        query = query.filter(~user_opp.filter(UserOpportunity.triage == "descartada").exists())
    if solo_con_score:
        # En búsquedas manuales el perfil no impone el umbral inicial; la
        # casilla solo exige que exista una puntuación calculada (> 0).
        query = query.filter(user_opp.filter(current_score_condition()).exists())
    if score_min is not None:
        try:
            query = query.filter(user_opp.filter(current_score_condition(), UserOpportunity.score >= float(score_min)).exists())
        except (TypeError, ValueError):
            raise HTTPException(422, "El puntaje mínimo no es válido")
    if triage == "guardada":
        query = query.filter(user_opp.filter(saved_condition()).exists())
    elif triage == "proyecto":
        query = query.filter(or_(user_opp.filter(UserOpportunity.triage == "proyecto").exists(), user_project.exists()))
    elif triage == "detectada":
        query = query.filter(or_(~user_opp.exists(), user_opp.filter(UserOpportunity.triage == "detectada").exists()))
    elif triage:
        query = query.filter(user_opp.filter(UserOpportunity.triage == triage).exists())
    total = query.order_by(None).count()
    rows = query.order_by(Opportunity.updated_at.desc(), Opportunity.id.desc()).offset(offset).limit(limit).all()
    scores = _user_scores(db, user.id, [opp.id for opp in rows])
    return {"filtros_interpretados": filtros, "total": total,
            "items": [_serialize(o, scores.get(o.id)) for o in rows]}


@router.get("/dashboard/metrics")
def metrics(
    compatibility_threshold: int | None = Query(default=None, ge=0, le=100),
    new_days: int = Query(default=7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = db.query(Opportunity).filter(_vigente_condition())
    prefs = db.query(AlertPrefs).filter(AlertPrefs.user_id == user.id).first()
    umbral_compatibilidad = compatibility_threshold if compatibility_threshold is not None else (prefs.high_score_threshold if prefs else 70)
    ahora = datetime.utcnow()
    profile = db.query(CompanyProfile).filter_by(user_id=user.id).first()
    uos = db.query(UserOpportunity).filter(UserOpportunity.user_id == user.id)
    alta_count, valor_total = 0, 0
    high = (db.query(UserOpportunity, Opportunity).join(Opportunity, Opportunity.id == UserOpportunity.opportunity_id)
            .filter(UserOpportunity.user_id == user.id, current_score_condition(),
                    UserOpportunity.score >= umbral_compatibilidad, func.coalesce(UserOpportunity.triage, 'detectada') != 'descartada'))
    high = high.filter(*profile_constraints(profile))
    for score, opp in high.yield_per(200):
        if profile and alerts_service.has_profile_match(score, profile, opp):
            alta_count += 1
            valor_total += opp.valor or 0

    # tendencia por mes (últimos 6 meses) según fecha_publicacion
    tendencia: dict[str, int] = {}
    for i in range(5, -1, -1):
        mes = (ahora.month - i - 1) % 12 + 1
        anio = ahora.year - (1 if ahora.month - i <= 0 else 0)
        tendencia[f"{anio}-{mes:02d}"] = 0
    dated = (db.query(func.extract('year', Opportunity.fecha_publicacion),
                      func.extract('month', Opportunity.fecha_publicacion), func.count(Opportunity.id))
        .join(UserOpportunity, UserOpportunity.opportunity_id == Opportunity.id)
        .filter(UserOpportunity.user_id == user.id, Opportunity.fecha_publicacion.isnot(None))
        .group_by(func.extract('year', Opportunity.fecha_publicacion), func.extract('month', Opportunity.fecha_publicacion)))
    for year, month, count in dated:
        key = f'{int(year):04d}-{int(month):02d}'
        if key in tendencia:
            tendencia[key] = count

    # El indicador del dashboard debe reflejar el trabajo real del preparador:
    # documentos pendientes dentro de ofertas existentes, no análisis sueltos.
    proyectos_oferta = db.query(OfferProject).filter(
        OfferProject.user_id == user.id,
        OfferProject.status == "activo",
    )
    docs_pendientes = sum(
        1 for proyecto in proyectos_oferta.yield_per(200)
        for item in (proyecto.checklist or [])
        if item.get("estado") != "listo"
    )
    alertas_no_leidas = sum(1 for _ in alerts_service.iter_visible_alerts(db, user.id, umbral_compatibilidad, unread=True))

    # Próximos a cerrar: únicamente ofertas activas del Preparador, no procesos
    # meramente detectados o descartados.
    # la fuente SECOP II (p6dx-8zbt) NO expone fecha de cierre (ver docs/fuentes-secop.md)
    proximos = (proyectos_oferta.join(Opportunity, Opportunity.id == OfferProject.opportunity_id)
        .filter(Opportunity.fecha_cierre >= ahora, Opportunity.fecha_cierre < ahora + timedelta(days=8)).count())
    return {
        "oportunidades_detectadas": uos.count(),
        "procesos_nuevos_base": base.filter(
            Opportunity.source == "secop2_procesos",
            Opportunity.fecha_publicacion >= ahora - timedelta(days=new_days),
        ).count(),
        "proximos_a_cerrar": proximos,
        "alta_compatibilidad": alta_count,
        "umbral_compatibilidad": umbral_compatibilidad,
        "valor_agregado_cop": valor_total,
        "guardadas": uos.filter(UserOpportunity.triage == 'guardada').count(),
        "descartadas": uos.filter(UserOpportunity.triage == 'descartada').count(),
        "proyectos_propuesta": uos.filter(UserOpportunity.triage == 'proyecto').count(),
        "ofertas_activas": proyectos_oferta.count(),
        "documentos_pendientes": docs_pendientes,
        "alertas_no_leidas": alertas_no_leidas,
        "coverage": coverage(db, user.id),
        "tendencia_mensual": [{"mes": k, "total": v} for k, v in tendencia.items()],
    }


@router.post("/rescore", status_code=202, response_model=MatchJobOut)
def rescore(background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.match_jobs import request_job, enqueue, job_progress
    try:
        job = request_job(db, user.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    db.commit()
    background.add_task(enqueue, job.id)
    return job_progress(db, job)

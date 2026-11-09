"""Dashboard y oportunidades: filtros, buscador de lenguaje natural, triage, métricas."""
from datetime import datetime, timedelta
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, cast, func, or_, Text
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Alert, AlertPrefs, Analysis, CompanyProfile, OfferProject, Opportunity, User, UserOpportunity
from app.db.session import get_db
from app.schemas import FeedbackIn, TriajeIn
from app.services import alerts as alerts_service
from app.services import nlq

router = APIRouter(prefix="/api", tags=["dashboard"])
PROFILE_MATCH_MIN_SCORE = 40


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
    rows = query.all()
    return {r.opportunity_id: r for r in rows}


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
    return {
        "id": opp.id, "source": opp.source, "source_id": opp.source_id,
        "entidad": opp.entidad, "nit_entidad": opp.nit_entidad,
        "departamento": opp.departamento, "ciudad": opp.ciudad,
        "objeto": opp.objeto, "descripcion": opp.descripcion,
        "modalidad": opp.modalidad, "tipo_contrato": opp.tipo_contrato,
        "unspsc_code": opp.unspsc_code, "valor": opp.valor,
        "estado": opp.estado, "fecha_publicacion": opp.fecha_publicacion,
        "fecha_cierre": opp.fecha_cierre,
        "url_oficial": url,
        # No se usa el dataset general como sustituto de un expediente.
        "url_consulta_secop": None,
        "documentos_publicos_disponibles": _public_document_count(opp.raw_json or {}),
        "cancelled": opp.cancelled, "captured_at": opp.captured_at, "updated_at": opp.updated_at,
        "score": uo.score if uo else None,
        "triage": uo.triage if uo else "detectada",
        "reasons": uo.reasons if uo else [],
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Opportunity)
    profile = db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first()
    # Al abrir Oportunidades, el perfil es el filtro de entrada. Los filtros
    # escritos por el usuario tienen prioridad para permitir explorar después.
    profile_configured = bool(profile and any([
        (profile.sector or "").strip(), (profile.actividades or "").strip(),
        (profile.productos_servicios or "").strip(), profile.keywords,
        profile.departamentos, profile.municipios, profile.modalidades,
    ]))
    if profile_match and not profile_configured:
        return {"total": 0, "items": [], "profile_configured": False, "profile_required": True}
    if profile_match and profile:
        departamentos = [x for x in (profile.departamentos or []) if x and "toda" not in x.lower()]
        municipios = [x for x in (profile.municipios or []) if x and "todo" not in x.lower()]
        modalidades = [x for x in (profile.modalidades or []) if x and "toda" not in x.lower()]
        profile_conditions = []
        if not departamento and departamentos:
            profile_conditions.append(or_(*[Opportunity.departamento.ilike(f"%{x}%") for x in departamentos]))
        if not municipio and municipios:
            profile_conditions.append(or_(*[Opportunity.ciudad.ilike(f"%{x}%") for x in municipios]))
        if not modalidad and modalidades:
            profile_conditions.append(or_(*[Opportunity.modalidad.ilike(f"%{x}%") for x in modalidades]))
        if valor_min is None and profile.presupuesto_min is not None:
            profile_conditions.append(Opportunity.valor >= profile.presupuesto_min)
        if valor_max is None and profile.presupuesto_max is not None:
            profile_conditions.append(Opportunity.valor <= profile.presupuesto_max)
        if profile_conditions:
            preserved_ids = [row.opportunity_id for row in db.query(UserOpportunity.opportunity_id).filter(
                UserOpportunity.user_id == user.id, UserOpportunity.triage.in_(["guardada", "proyecto"])
            ).all()]
            match_condition = and_(*profile_conditions)
            query = query.filter(or_(match_condition, Opportunity.id.in_(preserved_ids))) if preserved_ids else query.filter(match_condition)
    if not include_cancelled:
        query = query.filter(or_(Opportunity.cancelled.is_(False), Opportunity.cancelled.is_(None)))
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
                like = f"%{word}%"
                term_conditions.append(or_(
                    Opportunity.objeto.ilike(like), Opportunity.entidad.ilike(like), Opportunity.descripcion.ilike(like),
                    Opportunity.modalidad.ilike(like), Opportunity.tipo_contrato.ilike(like),
                ))
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
        query = query.filter(Opportunity.departamento.ilike(f"%{departamento}%"))
    if municipio:
        query = query.filter(Opportunity.ciudad.ilike(f"%{municipio}%"))
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

    # Los filtros de puntuación/triage deben aplicarse en SQL antes de contar y
    # paginar. Antes se paginaban primero y se filtraban después, provocando
    # páginas vacías aunque existieran coincidencias en páginas posteriores.
    user_opp = db.query(UserOpportunity).filter(
        UserOpportunity.user_id == user.id,
        UserOpportunity.opportunity_id == Opportunity.id,
    )
    # Descartar es persistente para este usuario: no debe reaparecer en nuevas
    # búsquedas, salvo que se solicite explícitamente el filtro de descartadas.
    if triage != "descartada":
        query = query.filter(~user_opp.filter(UserOpportunity.triage == "descartada").exists())
    if solo_con_score or profile_match:
        min_score = PROFILE_MATCH_MIN_SCORE if profile_match else 1
        query = query.filter(user_opp.filter(UserOpportunity.score >= min_score).exists())
    if triage:
        query = query.filter(user_opp.filter(UserOpportunity.triage == triage).exists())
    if score_min is not None:
        query = query.filter(user_opp.filter(UserOpportunity.score >= score_min).exists())

    total = query.count()
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
    # Los selectores explícitos de la interfaz tienen prioridad sobre lo que
    # el parser pueda inferir del texto natural.
    for key in ("departamento", "municipio", "modalidad"):
        if payload.get(key): filtros[key] = payload[key]
    if payload.get("valor_min"):
        filtros["valor_min"] = float(payload["valor_min"])
    query = db.query(Opportunity)
    if not filtros.get("estado"):
        query = query.filter(or_(Opportunity.cancelled.is_(False), Opportunity.cancelled.is_(None)))
    if filtros.get("q"):
        # La búsqueda manual es flexible: basta con que el proceso coincida
        # con al menos un término relevante. Exigir todos los términos hacía
        # que consultas naturales razonables terminaran siempre sin resultados.
        term_clauses = []
        for word in filtros["q"].split():
            variants = [word]
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
        query = query.filter(Opportunity.departamento.ilike(f"%{filtros['departamento']}%"))
    if filtros.get("municipio"):
        query = query.filter(Opportunity.ciudad.ilike(f"%{filtros['municipio']}%"))
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
    limit = min(max(int(payload.get("limit", 25)), 1), 100)
    offset = max(int(payload.get("offset", 0)), 0)
    rows = query.order_by(Opportunity.updated_at.desc(), Opportunity.id.desc()).offset(offset).limit(limit).all()
    solo_con_score = bool(payload.get("solo_con_score", False))
    score_min = payload.get("score_min")
    triage = payload.get("triage")
    user_opp = db.query(UserOpportunity).filter(
        UserOpportunity.user_id == user.id,
        UserOpportunity.opportunity_id == Opportunity.id,
    )
    if triage != "descartada":
        query = query.filter(~user_opp.filter(UserOpportunity.triage == "descartada").exists())
    if solo_con_score:
        # En búsquedas manuales el perfil no impone el umbral inicial; la
        # casilla solo exige que exista una puntuación calculada (> 0).
        query = query.filter(user_opp.filter(UserOpportunity.score > 0).exists())
    if score_min is not None:
        try:
            query = query.filter(user_opp.filter(UserOpportunity.score >= float(score_min)).exists())
        except (TypeError, ValueError):
            raise HTTPException(422, "El puntaje mínimo no es válido")
    if triage:
        query = query.filter(user_opp.filter(UserOpportunity.triage == triage).exists())
    total = query.count()
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
    scores = _user_scores(db, user.id)
    base = db.query(Opportunity).filter(or_(Opportunity.cancelled.is_(False), Opportunity.cancelled.is_(None)))
    prefs = db.query(AlertPrefs).filter(AlertPrefs.user_id == user.id).first()
    umbral_compatibilidad = compatibility_threshold if compatibility_threshold is not None else (prefs.high_score_threshold if prefs else 70)
    ahora = datetime.utcnow()
    uos = db.query(UserOpportunity).filter(UserOpportunity.user_id == user.id).all()
    ids = list(scores.keys())
    opps = {o.id: o for o in db.query(Opportunity).filter(Opportunity.id.in_(ids)).all()} if ids else {}

    alta = [s for s in uos if s.score >= umbral_compatibilidad and s.triage != "descartada"]
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

    # El indicador del dashboard debe reflejar el trabajo real del preparador:
    # documentos pendientes dentro de ofertas existentes, no análisis sueltos.
    proyectos_oferta = db.query(OfferProject).filter(
        OfferProject.user_id == user.id,
        OfferProject.status == "activo",
    ).all()
    docs_pendientes = sum(
        1 for proyecto in proyectos_oferta
        for item in (proyecto.checklist or [])
        if item.get("estado") != "listo"
    )
    alertas_no_leidas = db.query(Alert).filter(Alert.user_id == user.id, Alert.read_at.is_(None)).count()

    # Próximos a cerrar: únicamente ofertas activas del Preparador, no procesos
    # meramente detectados o descartados.
    # la fuente SECOP II (p6dx-8zbt) NO expone fecha de cierre (ver docs/fuentes-secop.md)
    proximos = 0
    for proyecto in proyectos_oferta:
        o = opps.get(proyecto.opportunity_id)
        if not o or not o.fecha_cierre:
            continue
        dias = (o.fecha_cierre - ahora).days
        if 0 <= dias <= 7:
            proximos += 1
    return {
        "oportunidades_detectadas": len(uos),
        "procesos_nuevos_base": base.filter(
            Opportunity.source == "secop2_procesos",
            Opportunity.fecha_publicacion >= ahora - timedelta(days=new_days),
        ).count(),
        "proximos_a_cerrar": proximos,
        "alta_compatibilidad": len(alta),
        "umbral_compatibilidad": umbral_compatibilidad,
        "valor_agregado_cop": valor_total,
        "guardadas": len(guardadas),
        "descartadas": len(descartadas),
        "proyectos_propuesta": len(proyectos),
        "ofertas_activas": len(proyectos_oferta),
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

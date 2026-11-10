"""Agentes 2, 3 y 4 expuestos como API: análisis de pliegos, viabilidad y ofertas."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.agents.pliegos import analizar_documento
from app.agents.viability import DISCLAIMER, PESOS_INICIALES, evaluar_viabilidad
from app.core.security import get_current_user
from app.db.models import (
    Analysis, CompanyProfile, Document, OfferProject, Opportunity, User, UserOpportunity, Viability,
)
from app.db.session import get_db
from app.schemas import BorradorIn, ChecklistItemIn, CommentIn, CronogramaItemIn, OfferStatusIn, ViabilityIn
from app.services import alerts as alerts_service
from app.services.audit import log_action
from app.services.eligibility import evaluar_elegibilidad
from app.services.exporter import export_docx, export_pdf_matriz, export_xlsx
from app.services.quota import check_quota, consume, require_pro
from app.agents.pliegos import extract_text
import re

router = APIRouter(prefix="/api", tags=["agentes"])

DEFAULT_CHECKLIST = [
    {"item": "Certificado de existencia y representación legal", "tipo": "jurídico", "estado": "pendiente"},
    {"item": "RUP (Registro Único de Proponentes) vigente", "tipo": "documental", "estado": "pendiente"},
    {"item": "Carta de presentación y propuesta", "tipo": "documental", "estado": "pendiente"},
    {"item": "Propuesta técnica", "tipo": "técnico", "estado": "pendiente"},
    {"item": "Propuesta económica", "tipo": "financiero", "estado": "pendiente"},
    {"item": "Pólizas y garantías exigidas", "tipo": "jurídico", "estado": "pendiente"},
    {"item": "Experiencia acreditada (contratos similares)", "tipo": "experiencia", "estado": "pendiente"},
]

_PALABRAS_COMUNES = {"para", "del", "las", "los", "una", "uno", "con", "por", "de", "en", "y", "el", "la", "que", "servicios", "adquisicion", "adquisición", "contratacion", "contratación", "proceso"}


def _cronograma_sugerido(opp: Opportunity, analysis: Analysis | None) -> list[dict]:
    """Construye un plan interno desde el cierre oficial cuando existe.

    SECOP no siempre publica la fecha de cierre en el dataset. En ese caso se
    conserva una guía relativa y se marca explícitamente como estimada.
    """
    requisitos = list(analysis.requisitos or []) if analysis else []
    documentales = sum(1 for r in requisitos if r.get("tipo") == "documental")
    tareas = [
        ("Análisis de pliegos y aclaratorios", "análisis"),
        (f"Recolección de documentos y certificaciones ({documentales or 'base'} requisito(s))", "documentos"),
        ("Elaboración de propuesta técnica", "técnica"),
        ("Propuesta económica y revisión de márgenes", "económica"),
        ("Revisión jurídica y aprobación humana", "revisión"),
        ("Carga final y presentación manual en SECOP", "presentación"),
    ]
    cierre = opp.fecha_cierre
    if not cierre:
        return [{"tarea": tarea, "plazo": f"D+{2 + i * 2}", "tipo": tipo, "estimado": True, "estado": "pendiente"}
                for i, (tarea, tipo) in enumerate(tareas)]
    ahora = datetime.utcnow()
    dias = max(0, (cierre - ahora).days)
    resultado = []
    for i, (tarea, tipo) in enumerate(tareas):
        # Distribuye hitos hasta el cierre; con poco tiempo se concentran en
        # hoy y el cierre, pero nunca se inventa tiempo adicional.
        fecha = ahora + (cierre - ahora) * ((i + 1) / len(tareas))
        resultado.append({
            "tarea": tarea,
            "plazo": fecha.strftime("%d/%m/%Y"),
            "fecha": fecha.isoformat(timespec="minutes"),
            "tipo": tipo,
            "estimado": False,
            "estado": "pendiente",
            "dias_disponibles": dias,
            "vencido": cierre <= ahora,
        })
    return resultado


def _documento_corresponde(doc: Document, opp: Opportunity, data: bytes) -> bool:
    """Comprueba que el texto del archivo mencione el proceso seleccionado.

    Se exige coincidencia de dos términos distintivos del objeto o una coincidencia
    de entidad + objeto. Así se evita analizar accidentalmente un pliego ajeno.
    """
    texto = " ".join(t for _, t in extract_text(doc.filename, data)).lower()
    if not texto.strip():
        return False
    referencia = f"{opp.objeto or ''} {opp.entidad or ''} {opp.source_id or ''}".lower()
    tokens = {t for t in re.findall(r"[a-záéíóúñü0-9]{5,}", referencia) if t not in _PALABRAS_COMUNES}
    presentes = {t for t in tokens if t in texto}
    objeto_tokens = {t for t in re.findall(r"[a-záéíóúñü0-9]{5,}", (opp.objeto or '').lower()) if t not in _PALABRAS_COMUNES}
    entidad_tokens = {t for t in re.findall(r"[a-záéíóúñü0-9]{5,}", (opp.entidad or '').lower()) if t not in _PALABRAS_COMUNES}
    coincidencia_fuerte = any(len(token) >= 8 for token in (objeto_tokens & presentes))
    return len(presentes) >= 2 or coincidencia_fuerte or (bool(objeto_tokens & presentes) and bool(entidad_tokens & presentes))


# ---------------- AGENTE 2: Analista de Pliegos ----------------

@router.post("/opportunities/{opportunity_id}/analyze")
def analyze(opportunity_id: int, document_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_pro(db, user)
    quota = check_quota(db, user)
    if not quota["allowed"]:
        raise HTTPException(402, f"Límite mensual de análisis alcanzado ({quota['used']}/{quota['limit']}). Plan: {quota['plan']}. Actualice su suscripción.")
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Oportunidad no encontrada")
    doc_filter = or_(Document.user_id == user.id, Document.company_id == user.company_id) if user.company_id else Document.user_id == user.id
    query = db.query(Document).filter(doc_filter, Document.opportunity_id == opportunity_id)
    if document_id:
        query = query.filter(Document.id == document_id)
    docs = query.order_by(Document.uploaded_at.desc()).all()
    if not docs:
        raise HTTPException(400, "Adjunte primero un documento del proceso (PDF, DOCX o XLSX) en /api/documents")

    from app.services.alerts import profile_dict

    perfil = profile_dict(db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first())
    resumen: dict = {}
    requisitos: list[dict] = []
    docs_analizados = 0
    validacion_documentos: list[dict] = []
    documentos_invalidos: list[str] = []
    for doc in docs:
        try:
            with open(doc.storage_path, "rb") as fh:
                data = fh.read()
            corresponde = _documento_corresponde(doc, opp, data)
            validacion_documentos.append({"documento": doc.filename, "pertenece_al_proceso": corresponde})
            if not corresponde:
                documentos_invalidos.append(doc.filename)
                continue
            analisis = analizar_documento(doc.filename, data, perfil)
        except FileNotFoundError:
            validacion_documentos.append({"documento": doc.filename, "pertenece_al_proceso": False, "motivo": "No se encontró el archivo almacenado"})
            documentos_invalidos.append(doc.filename)
            continue
        docs_analizados += 1
        if not resumen:
            resumen = analisis.resumen
        else:
            for clave, valor in analisis.resumen.items():
                if clave not in resumen or (isinstance(valor, dict) and valor.get("valor") and not resumen[clave].get("valor")):
                    resumen[clave] = valor
        for r in analisis.requisitos:
            requisitos.append({
                "descripcion": r.descripcion, "tipo": r.tipo, "estado": r.estado,
                "evidencia": r.evidencia, "documento": r.documento, "referencia": r.referencia,
                "observaciones": r.observaciones, "nivel_confianza": r.nivel_confianza,
                "es_excluyente": r.es_excluyente,
            })
    if documentos_invalidos:
        raise HTTPException(422, detail={
            "message": "Algunos documentos no parecen pertenecer al proceso seleccionado. Por favor, carga únicamente los pliegos y anexos oficiales de este proceso.",
            "documentos": validacion_documentos,
        })
    if not docs_analizados:
        raise HTTPException(400, "No fue posible leer los documentos almacenados")
    resumen["descargo"] = (
        "Resultado orientativo generado automáticamente. Exige validación humana antes de elaborar una propuesta. "
        "Los requisitos no listados no deben asumirse ausentes: verificar el documento oficial completo."
    )
    analysis = Analysis(opportunity_id=opp.id, user_id=user.id, company_id=user.company_id, resumen_ejecutivo=resumen, requisitos=requisitos[:120], estado="borrador")
    db.add(analysis)
    db.commit()
    consume(db, user)
    log_action(db, user, "analizar_pliego", "opportunity", opp.id, {"requisitos": len(requisitos)})
    return {"id": analysis.id, "resumen": resumen, "total_requisitos": len(requisitos), "estado": "borrador", "documentos": validacion_documentos,
            "nota": "Requiere validación humana. Estados: Cumple / No cumple / Por verificar / Información insuficiente."}


# ---------------- AGENTE 3: Evaluador de Viabilidad ----------------

def _dias_hasta_cierre(opp: Opportunity, resumen: dict) -> int | None:
    if opp.fecha_cierre:
        return (opp.fecha_cierre - datetime.utcnow()).days
    raw = (resumen.get("fecha_hora_cierre") or {}).get("valor")
    if not raw:
        return None
    texto = str(raw)[:16].strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return (datetime.strptime(texto, fmt) - datetime.utcnow()).days
        except ValueError:
            continue
    return None


@router.post("/opportunities/{opportunity_id}/viability")
def viability(opportunity_id: int, data: ViabilityIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_pro(db, user)
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Oportunidad no encontrada")
    analysis = db.query(Analysis).filter(Analysis.opportunity_id == opp.id).order_by(Analysis.created_at.desc()).first()
    from app.services.alerts import profile_dict

    perfil = profile_dict(db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first())
    resumen = analysis.resumen_ejecutivo if analysis else {}
    requisitos = analysis.requisitos if analysis else []
    pesos = (data.pesos if data else None) or {}
    resultado = evaluar_viabilidad(perfil, resumen, requisitos, pesos=pesos, dias_hasta_cierre=_dias_hasta_cierre(opp, resumen))
    row = Viability(
        opportunity_id=opp.id, user_id=user.id, company_id=user.company_id, global_score=resultado.global_score,
        factors=resultado.factors, critical_failures=resultado.critical_failures,
        fortalezas=resultado.fortalezas, debilidades=resultado.debilidades,
        docs_faltantes=resultado.docs_faltantes, riesgos=resultado.riesgos,
        costo_estimado=resultado.costo_estimado, recommendation=resultado.recommendation,
        weights_json={**PESOS_INICIALES, **pesos}, disclaimer=DISCLAIMER,
    )
    db.add(row)
    db.commit()
    return {
        "id": row.id, "global_score": resultado.global_score, "factors": resultado.factors,
        "critical_failures": resultado.critical_failures, "fortalezas": resultado.fortalezas,
        "debilidades": resultado.debilidades, "docs_faltantes": resultado.docs_faltantes,
        "riesgos": resultado.riesgos, "costo_estimado": resultado.costo_estimado,
        "recommendation": resultado.recommendation, "disclaimer": DISCLAIMER,
        "nota": "Diferente de toda probabilidad de adjudicación: modelo propio y configurable de LicitaIA.",
    }


@router.get("/opportunities/{opportunity_id}/eligibility")
def eligibility(opportunity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fase 3: elegibilidad jurídica, financiera y técnica SEPARADA de la compatibilidad comercial.
    Sin evidencia documental la dimensión queda en 'informacion_insuficiente': nunca se declara
    elegibilidad sin soporte (ver app/services/eligibility.py)."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Oportunidad no encontrada")
    analysis = db.query(Analysis).filter(Analysis.opportunity_id == opp.id).order_by(Analysis.created_at.desc()).first()
    from app.services.alerts import profile_dict

    perfil = profile_dict(db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first())
    resultado = evaluar_elegibilidad(perfil, analysis.requisitos if analysis else [])
    log_action(db, user, "evaluar_elegibilidad", "opportunity", opp.id, {"resumen": resultado["resumen"]})
    return resultado


# ---------------- AGENTE 4: Preparador de Ofertas ----------------

@router.post("/offer-projects", status_code=201)
def create_project(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_pro(db, user)
    opp_id = int(payload.get("opportunity_id", 0))
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(404, "Oportunidad no encontrada")
    analysis = db.query(Analysis).filter(Analysis.opportunity_id == opp.id).order_by(Analysis.created_at.desc()).first()
    checklist = list(DEFAULT_CHECKLIST)
    if analysis:
        for r in analysis.requisitos:
            if r.get("tipo") == "documental":
                checklist.append({"item": (r.get("descripcion") or "")[:150], "tipo": "documental", "estado": "pendiente"})
    project = OfferProject(
        user_id=user.id, company_id=user.company_id, opportunity_id=opp.id,
        name=payload.get("name") or f"Propuesta — {(opp.objeto or 'Proceso')[:80]}",
        checklist=checklist,
        cronograma=_cronograma_sugerido(opp, analysis),
        borradores=[],
        comentarios=[],
    )
    db.add(project)
    # marca la oportunidad como proyecto en el triage
    uo = db.query(UserOpportunity).filter(UserOpportunity.user_id == user.id, UserOpportunity.opportunity_id == opp.id).first()
    if not uo:
        uo = UserOpportunity(user_id=user.id, opportunity_id=opp.id, score=0, reasons=[])
        db.add(uo)
    uo.triage = "proyecto"
    db.commit()
    return {"id": project.id, "name": project.name, "checklist": project.checklist, "cronograma": project.cronograma}


@router.get("/offer-projects")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(OfferProject).filter(OfferProject.user_id == user.id).order_by(OfferProject.updated_at.desc()).all()
    return [{"id": p.id, "name": p.name, "opportunity_id": p.opportunity_id, "status": p.status,
             "version": p.version, "updated_at": p.updated_at,
             "pendientes": sum(1 for c in (p.checklist or []) if c.get("estado") != "listo")} for p in rows]


@router.get("/offer-projects/{project_id}")
def get_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(OfferProject).filter(OfferProject.id == project_id, OfferProject.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Proyecto no encontrado")
    opp = db.query(Opportunity).filter(Opportunity.id == p.opportunity_id).first()
    return {
        "id": p.id, "name": p.name, "status": p.status, "version": p.version, "approved_by": p.approved_by,
        "opportunity": {"id": opp.id, "objeto": opp.objeto, "entidad": opp.entidad, "url_oficial": opp.url_oficial} if opp else None,
        "checklist": p.checklist, "matriz_cumplimiento": p.matriz_cumplimiento,
        "borradores": p.borradores, "cronograma": p.cronograma, "comentarios": p.comentarios,
    }


@router.delete("/offer-projects/{project_id}", status_code=204)
def delete_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(OfferProject).filter(OfferProject.id == project_id, OfferProject.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Oferta no encontrada")
    db.delete(p)
    db.commit()
    return Response(status_code=204)


@router.patch("/offer-projects/{project_id}/checklist")
def update_checklist(project_id: int, item: ChecklistItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(OfferProject).filter(OfferProject.id == project_id, OfferProject.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Proyecto no encontrado")
    # copia profunda de cada ítem: nunca se mutan en sitio los dicts compartidos
    checklist = [dict(c) for c in (p.checklist or [])]
    if item.index < 0 or item.index >= len(checklist):
        raise HTTPException(400, "Índice de checklist inválido")
    if item.estado is not None:
        checklist[item.index]["estado"] = item.estado
    if item.evidencia is not None:
        checklist[item.index]["evidencia"] = item.evidencia
    p.checklist = checklist
    flag_modified(p, "checklist")  # fuerza la marca de columna modificada
    db.commit()
    return {"checklist": p.checklist}


@router.patch("/offer-projects/{project_id}/cronograma")
def update_cronograma(project_id: int, item: CronogramaItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(OfferProject).filter(OfferProject.id == project_id, OfferProject.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Proyecto no encontrado")
    cronograma = [dict(c) for c in (p.cronograma or [])]
    if item.index < 0 or item.index >= len(cronograma):
        raise HTTPException(400, "Índice de cronograma inválido")
    cronograma[item.index]["estado"] = item.estado
    p.cronograma = cronograma
    p.version += 1
    flag_modified(p, "cronograma")
    db.commit()
    return {"cronograma": cronograma}


@router.post("/offer-projects/{project_id}/borradores")
def add_borrador(project_id: int, data: BorradorIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Genera o guarda un borrador. El contenido de respuestas técnicas SOLO usa
    información proporcionada por el cliente (nunca datos inventados)."""
    p = db.query(OfferProject).filter(OfferProject.id == project_id, OfferProject.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Proyecto no encontrado")
    opp = db.query(Opportunity).filter(Opportunity.id == p.opportunity_id).first()
    perfil = db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first()
    if data.contenido:
        contenido = data.contenido
    elif data.tipo == "carta_presentacion":
        nombre = perfil.nombre_comercial if perfil else "La empresa"
        contenido = (
            f"Señores\n{(opp.entidad or 'Entidad contratante')}\n\n"
            f"Referencia: {opp.objeto or 'Proceso de contratación'}\n\n"
            f"En calidad de representante legal de {nombre}, me permito presentar nuestra propuesta "
            f"para el proceso de referencia, la cual cumple con los requisitos habilitantes exigidos "
            f"en los pliegos de condiciones.\n\n"
            f"NOTA: Borrador generado por MySECOP. Debe ser revisado, completado y firmado por una "
            f"persona autorizada antes de su presentación. MySECOP no firma ni presenta propuestas."
        )
    elif data.tipo == "matriz_cumplimiento":
        analysis = db.query(Analysis).filter(Analysis.opportunity_id == p.opportunity_id).order_by(Analysis.created_at.desc()).first()
        filas = [["#", "Requisito", "Cumplimiento", "Evidencia", "Referencia"]]
        for i, r in enumerate((analysis.requisitos if analysis else [])[:50], 1):
            filas.append([str(i), (r.get("descripcion") or "")[:200], "Por verificar", "", r.get("referencia") or ""])
        contenido = "\n".join(" | ".join(fila) for fila in filas) if filas else "Sin análisis previo."
    else:  # respuestas_tecnicas
        raise HTTPException(400, "Las respuestas técnicas requieren contenido proporcionado por el cliente (campo 'contenido'). MySECOP no las inventa.")
    borradores = list(p.borradores or [])
    version = max([b.get("version", 1) for b in borradores if b.get("tipo") == data.tipo], default=0) + 1
    borradores.append({"tipo": data.tipo, "contenido": contenido, "version": version, "fecha": datetime.utcnow().isoformat(timespec="seconds")})
    p.borradores = borradores
    p.version += 1
    p.history = list(p.history or []) + [{"version": p.version, "accion": f"borrador {data.tipo} v{version}", "fecha": datetime.utcnow().isoformat(timespec="seconds")}]
    db.commit()
    return {"borradores": p.borradores}


@router.post("/offer-projects/{project_id}/comentarios")
def add_comment(project_id: int, data: CommentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(OfferProject).filter(OfferProject.id == project_id, OfferProject.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Proyecto no encontrado")
    comentarios = list(p.comentarios or []) + [{"autor": user.full_name or user.email, "texto": data.texto, "fecha": datetime.utcnow().isoformat(timespec="seconds")}]
    p.comentarios = comentarios
    db.commit()
    return {"comentarios": p.comentarios}


@router.post("/offer-projects/{project_id}/status")
def set_status(project_id: int, data: OfferStatusIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(OfferProject).filter(OfferProject.id == project_id, OfferProject.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Proyecto no encontrado")
    p.status = data.status
    if data.status == "aprobado":
        p.approved_by = data.approved_by or (user.full_name or user.email)
    db.commit()
    return {"status": p.status, "approved_by": p.approved_by}


@router.get("/offer-projects/{project_id}/export")
def export_project(project_id: int, formato: str = "docx", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(OfferProject).filter(OfferProject.id == project_id, OfferProject.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Proyecto no encontrado")
    opp = db.query(Opportunity).filter(Opportunity.id == p.opportunity_id).first()
    proceso_rows = [["Campo", "Información"], ["Entidad", opp.entidad if opp else "N/D"], ["Objeto", opp.objeto if opp else "N/D"], ["Estado de la oferta", p.status], ["Expediente SECOP", opp.url_oficial if opp else "N/D"]]
    checklist_rows = [["#", "Documento", "Tipo", "Estado", "Evidencia"]] + [
        [str(i + 1), c.get("item", ""), c.get("tipo", ""), c.get("estado", ""), c.get("evidencia", "")]
        for i, c in enumerate(p.checklist or [])
    ]
    matriz = list(p.matriz_cumplimiento or [])
    matriz_rows = (matriz if matriz and isinstance(matriz[0], list) else [["Matriz de cumplimiento pendiente"]])
    cronograma = list(p.cronograma or [])
    avance = round(sum(1 for c in cronograma if c.get("estado") == "listo") / len(cronograma) * 100) if cronograma else 0
    bloques = round(avance / 10)
    barra = "█" * bloques + "░" * (10 - bloques)
    cronograma_rows = [["Avance del cronograma", f"{barra} {avance}%"], ["Tarea", "Plazo", "Estado", "Tipo"]] + [[c.get("tarea", ""), c.get("plazo", ""), "Lista" if c.get("estado") == "listo" else "Pendiente", "Estimado" if c.get("estimado") else "Plan oficial"] for c in cronograma]
    borradores_rows = [["Tipo", "Versión", "Fecha", "Contenido"]] + [[b.get("tipo", ""), str(b.get("version", 1)), b.get("fecha", ""), b.get("contenido", "")] for b in (p.borradores or [])]
    comentarios_rows = [["Autor", "Fecha", "Comentario"]] + [[c.get("autor", ""), c.get("fecha", ""), c.get("texto", "")] for c in (p.comentarios or [])]
    secciones = [("Información del proceso", proceso_rows), ("Checklist documental", checklist_rows), ("Cronograma interno sugerido · avance total", cronograma_rows), ("Borradores", borradores_rows), ("Comentarios y aprobaciones", comentarios_rows)]
    formato = formato.lower()
    if formato == "xlsx":
        content = export_xlsx({
            "Proceso": proceso_rows,
            "Checklist": checklist_rows,
            "Matriz": matriz_rows,
            "Cronograma": cronograma_rows,
            "Borradores": borradores_rows,
            "Comentarios": comentarios_rows,
        })
        media, filename = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "oferta_checklist.xlsx"
    elif formato == "pdf":
        content = export_pdf_matriz(f"Oferta — {p.name}", secciones)
        media, filename = "application/pdf", "oferta_checklist.pdf"
    else:
        content = export_docx(p.name, secciones)
        media, filename = "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "oferta_checklist.docx"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})

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
from app.schemas import BorradorIn, ChecklistItemIn, CommentIn, OfferStatusIn, ViabilityIn
from app.services import alerts as alerts_service
from app.services.audit import log_action
from app.services.eligibility import evaluar_elegibilidad
from app.services.exporter import export_docx, export_pdf_matriz, export_xlsx
from app.services.quota import check_quota, consume

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


# ---------------- AGENTE 2: Analista de Pliegos ----------------

@router.post("/opportunities/{opportunity_id}/analyze")
def analyze(opportunity_id: int, document_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    for doc in docs:
        try:
            with open(doc.storage_path, "rb") as fh:
                data = fh.read()
            analisis = analizar_documento(doc.filename, data, perfil)
        except FileNotFoundError:
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
    return {"id": analysis.id, "resumen": resumen, "total_requisitos": len(requisitos), "estado": "borrador",
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
        cronograma=[
            {"tarea": "Análisis de pliegos y aclaratorios", "plazo": "D+2"},
            {"tarea": "Recolección de documentos y certificaciones", "plazo": "D+5"},
            {"tarea": "Elaboración de propuesta técnica", "plazo": "D+8"},
            {"tarea": "Propuesta económica y revisión de márgenes", "plazo": "D+10"},
            {"tarea": "Revisión jurídica y aprobación humana", "plazo": "D+12"},
            {"tarea": "Carga final y presentación (manual en SECOP)", "plazo": "D+14"},
        ],
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
            f"NOTA: Borrador generado por LicitaIA. Debe ser revisado, completado y firmado por una "
            f"persona autorizada antes de su presentación. LicitaIA no firma ni presenta propuestas."
        )
    elif data.tipo == "matriz_cumplimiento":
        analysis = db.query(Analysis).filter(Analysis.opportunity_id == p.opportunity_id).order_by(Analysis.created_at.desc()).first()
        filas = [["#", "Requisito", "Cumplimiento", "Evidencia", "Referencia"]]
        for i, r in enumerate((analysis.requisitos if analysis else [])[:50], 1):
            filas.append([str(i), (r.get("descripcion") or "")[:200], "Por verificar", "", r.get("referencia") or ""])
        contenido = "\n".join(" | ".join(fila) for fila in filas) if filas else "Sin análisis previo."
    else:  # respuestas_tecnicas
        raise HTTPException(400, "Las respuestas técnicas requieren contenido proporcionado por el cliente (campo 'contenido'). LicitaIA no las inventa.")
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
    checklist_rows = [["#", "Documento", "Tipo", "Estado", "Evidencia"]] + [
        [str(i + 1), c.get("item", ""), c.get("tipo", ""), c.get("estado", ""), c.get("evidencia", "")]
        for i, c in enumerate(p.checklist or [])
    ]
    matriz = list(p.matriz_cumplimiento or [])
    matriz_rows = (matriz if matriz and isinstance(matriz[0], list) else [["Matriz de cumplimiento pendiente"]])
    formato = formato.lower()
    if formato == "xlsx":
        content = export_xlsx({
            "Checklist": checklist_rows,
            "Matriz": matriz_rows,
            "Cronograma": [["Tarea", "Plazo"]] + [[c.get("tarea", ""), c.get("plazo", "")] for c in (p.cronograma or [])],
        })
        media, filename = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "oferta_checklist.xlsx"
    elif formato == "pdf":
        content = export_pdf_matriz(f"Checklist de oferta — {p.name}", checklist_rows)
        media, filename = "application/pdf", "oferta_checklist.pdf"
    else:
        secciones = [("Datos del proceso", [[f"Entidad: {opp.entidad if opp else 'N/D'}"], [f"Objeto: {opp.objeto if opp else 'N/D'}"], [f"Expediente: {opp.url_oficial if opp else 'N/D'}"]]),
                     ("Checklist documental", checklist_rows),
                     ("Cronograma interno", [["Tarea", "Plazo"]] + [[c.get("tarea", ""), c.get("plazo", "")] for c in (p.cronograma or [])]),
                     ("Borradores", [[b.get("tipo", "") + f" (v{b.get('version', 1)})"] for b in (p.borradores or [])] or [["Sin borradores generados"]])]
        content = export_docx(p.name, secciones)
        media, filename = "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "oferta_checklist.docx"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})

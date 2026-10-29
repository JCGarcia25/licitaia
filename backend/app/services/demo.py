"""Datos de demostración (opcional, solo desarrollo).

Simula filas con los campos REALES verificados del dataset SECOP II -
Procesos de Contratación (p6dx-8zbt) para probar el pipeline sin red.
Se marcan como fuente 'secop2_procesos' y son datos de ejemplo; la referencia
definitiva es siempre el expediente oficial en SECOP.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import AlertPrefs, CompanyProfile, User
from app.services.ingest import seed_sample

logger = logging.getLogger("licitaia.demo")

DEMO_EMAIL = "demo@licitaia.co"
DEMO_PASSWORD = "LicitAIA2026"

# Campos con los nombres reales verificados en p6dx-8zbt
SAMPLE_PROCESOS = [
    {
        "id_del_proceso": "CO1.DEMO.1000001-1",
        "entidad": "Alcaldía Mayor de Bogotá D.C. (Secretaría Distrital de Gobierno) - Secretaría de Gobierno",
        "nit_entidad": "899999006-1",
        "departamento_entidad": "Bogotá D.C.",
        "ciudad_entidad": "Bogotá D.C.",
        "nombre_del_procedimiento": "Adquisición de licencias y desarrollo de software para la modernización tecnológica y el sistema de información de trámites distritales",
        "descripci_n_del_procedimiento": "Modernización del sistema de información, interoperabilidad entre plataformas y mantenimiento de aplicaciones institucionales.",
        "modalidad_de_contratacion": "Licitación Pública",
        "tipo_de_contrato": "Compra y Venta",
        "codigo_principal_de_categoria": "81101500",
        "precio_base": "2000000000",
        "estado_del_procedimiento": "En proceso",
        "fecha_de_publicacion_del": "2026-10-20T10:30:00",
        "fecha_de_ultima_publicaci": "2026-10-24T08:00:00",
        "urlproceso": "https://community.binpar.cloud/compra-bogota/secop2/CodigoEntidadProcesoDinamico",
    },
    {
        "id_del_proceso": "CO1.DEMO.1000002-2",
        "entidad": "E.S.E. Hospital Regional del Meta - Nivel 2",
        "nit_entidad": "900123456-7",
        "departamento_entidad": "Meta",
        "ciudad_entidad": "Villavicencio",
        "nombre_del_procedimiento": "Suministro de equipos biomédicos para el servicio de hospitalización",
        "descripci_n_del_procedimiento": "Compra de equipos biomédicos con instalación y capacitación.",
        "modalidad_de_contratacion": "Selección Abreviada",
        "tipo_de_contrato": "Compra y Venta",
        "codigo_principal_de_categoria": "42172000",
        "precio_base": "350000000",
        "estado_del_procedimiento": "En proceso",
        "fecha_de_publicacion_del": "2026-10-22T09:00:00",
        "fecha_de_ultima_publicaci": "2026-10-25T11:00:00",
        "urlproceso": "https://community.binpar.cloud/compra-bogota/secop2/CodigoEntidadProcesoDinamico",
    },
    {
        "id_del_proceso": "CO1.DEMO.1000003-3",
        "entidad": "Universidad Nacional del Quindío",
        "nit_entidad": "899999019-5",
        "departamento_entidad": "Quindío",
        "ciudad_entidad": "Armenia",
        "nombre_del_procedimiento": "Mantenimiento y conservación de la infraestructura física del campus",
        "descripci_n_del_procedimiento": "Mantenimiento preventivo y correctivo de edificaciones.",
        "modalidad_de_contratacion": "Contratación Mínima Cuantía",
        "tipo_de_contrato": "Obra",
        "codigo_principal_de_categoria": "30199000",
        "precio_base": "98000000",
        "estado_del_procedimiento": "En proceso",
        "fecha_de_publicacion_del": "2026-10-15T08:00:00",
        "fecha_de_ultima_publicaci": "2026-10-23T15:30:00",
        "urlproceso": "https://community.binpar.cloud/compra-bogota/secop2/CodigoEntidadProcesoDinamico",
    },
    {
        "id_del_proceso": "CO1.DEMO.1000004-4",
        "entidad": "Instituto de Deportes y Recreación de Cali - Coldeportes",
        "nit_entidad": "899999027-6",
        "departamento_entidad": "Valle del Cauca",
        "ciudad_entidad": "Cali",
        "nombre_del_procedimiento": "Transformación digital y modernización tecnológica: plataforma de gestión deportiva e interoperabilidad",
        "descripci_n_del_procedimiento": "Implementación de plataforma de gestión, migración de sistemas y soporte de aplicaciones.",
        "modalidad_de_contratacion": "Contratación Directa",
        "tipo_de_contrato": "Prestación de Servicios",
        "codigo_principal_de_categoria": "81101500",
        "precio_base": "450000000",
        "estado_del_procedimiento": "En proceso",
        "fecha_de_publicacion_del": "2026-10-24T14:00:00",
        "fecha_de_ultima_publicaci": "2026-10-26T09:45:00",
        "urlproceso": "https://community.binpar.cloud/compra-bogota/secop2/CodigoEntidadProcesoDinamico",
    },
    {
        "id_del_proceso": "CO1.DEMO.1000005-5",
        "entidad": "Gobernación de Cundinamarca - Secretaría de Hacienda",
        "nit_entidad": "899999030-3",
        "departamento_entidad": "Cundinamarca",
        "ciudad_entidad": "Bogotá D.C.",
        "nombre_del_procedimiento": "Suministro de equipamentos y muebles de oficina",
        "descripci_n_del_procedimiento": "Compra de mobiliario administrativo.",
        "modalidad_de_contratacion": "Contratación Mínima Cuantía",
        "tipo_de_contrato": "Compra y Venta",
        "codigo_principal_de_categoria": "56101500",
        "precio_base": "60000000",
        "estado_del_procedimiento": "Cancelado",
        "fecha_de_publicacion_del": "2026-09-30T10:00:00",
        "fecha_de_ultima_publicaci": "2026-10-18T10:00:00",
        "urlproceso": "https://community.binpar.cloud/compra-bogota/secop2/CodigoEntidadProcesoDinamico",
    },
    {
        "id_del_proceso": "CO1.DEMO.1000006-6",
        "entidad": "Alcaldía de Medellín - Secretaría de Salud",
        "nit_entidad": "890980057-1",
        "departamento_entidad": "Antioquia",
        "ciudad_entidad": "Medellín",
        "nombre_del_procedimiento": "Suministro de medicamentos e insumos hospitalarios",
        "descripci_n_del_procedimiento": "Compra de insumos hospitalarios de bajo y alto costo.",
        "modalidad_de_contratacion": "Licitación Pública",
        "tipo_de_contrato": "Compra y Venta",
        "codigo_principal_de_categoria": "51400000",
        "precio_base": "1200000000",
        "estado_del_procedimiento": "En proceso",
        "fecha_de_publicacion_del": "2026-10-19T11:00:00",
        "fecha_de_ultima_publicaci": "2026-10-26T16:20:00",
        "urlproceso": "https://community.binpar.cloud/compra-bogota/secop2/CodigoEntidadProcesoDinamico",
    },
]


def seed_demo_if_empty(db: Session | None = None) -> None:
    """Crea usuario demo + perfil + datos de ejemplo si la base está vacía."""
    from app.db.session import SessionLocal

    own = db is None
    if own:
        db = SessionLocal()
    try:
        from app.db.models import Opportunity

        settings = get_settings()
        if settings.environment == "production" or not settings.allow_demo_seed:
            logger.info("Seed de datos de demostración desactivado (entorno=%s, ALLOW_DEMO_SEED=%s)", settings.environment, settings.allow_demo_seed)
            return
        if db.query(Opportunity).count() > 0:
            return
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if not user:
            user = User(email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD),
                        full_name="Usuario Demo LicitaIA")
            db.add(user)
            db.flush()
            db.add(AlertPrefs(user_id=user.id))
            db.add(CompanyProfile(
                user_id=user.id,
                nombre_comercial="TechSoft Andina S.A.S.",
                razon_social="TechSoft Andina Soluciones Tecnológicas S.A.S.",
                nit="901.234.567-8",
                sector="Tecnologías de la información",
                actividades="Desarrollo de software, integración de sistemas y soporte de aplicaciones",
                productos_servicios="Desarrollo de software a la medida, sistemas de información, interoperabilidad, mantenimiento de aplicaciones, transformación digital",
                keywords=["desarrollo de software", "sistemas de información", "interoperabilidad",
                          "mantenimiento de aplicaciones", "transformación digital", "modernización tecnológica"],
                unspsc_codes=["81101500"],
                departamentos=["Bogotá D.C.", "Cundinamarca", "Valle del Cauca"],
                presupuesto_min=100_000_000,
                presupuesto_max=5_000_000_000,
                modalidades=["Licitación Pública", "Contratación Directa", "Selección Abreviada"],
                experiencia="10 años en proyectos de modernización tecnológica para entidades públicas",
                capacidades="Equipo de 30 ingenieros; capacidad financiera para contratos de hasta 5.000 millones COP",
                certificaciones=["ISO 9001"],
                acepta_consorcios=True,
            ))
        created = seed_sample(db, [("secop2_procesos", row) for row in SAMPLE_PROCESOS])
        from app.services.alerts import rescore_user
        rescore_user(db, user.id)
        db.commit()
        logger.info("Demo listo: %s oportunidades de ejemplo, usuario %s / %s", created, DEMO_EMAIL, DEMO_PASSWORD)
    finally:
        if own:
            db.close()

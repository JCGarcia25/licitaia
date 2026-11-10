"""Crea el piloto Elite exclusivamente en DEV.

No envía correo, no llama a Mercado Pago y nunca modifica usuarios existentes.
Ejecutar dentro del contenedor API con ENVIRONMENT=development.
"""
from datetime import datetime
import os
import sys

from app.core.security import hash_password
from app.db.models import Company, Subscription, User
from app.db.session import SessionLocal, init_db

USERS = [
    ("Johan Felipe Ochoa Jiménez", "asesorgerencia@elite.com.co"),
    ("Dayana Marisella Martínez Forez", "directorlicitaciones@elite.com.co"),
    ("Julio César Higuera Ibáñez", "analistalicitaciones@sarupetrol.com"),
    ("Juan David Cortés Prada", "comercial@elite.com.co"),
    ("Jonathan Cuellar Niño", "comercial@g.cienporciento.com.co"),
]

def main() -> None:
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise SystemExit("Bloqueado: este seed solo puede ejecutarse en DEV.")
    init_db()
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.nombre == "Elite (piloto DEV)").first()
        if not company:
            company = Company(nombre="Elite (piloto DEV)", sector="Contratación estatal")
            db.add(company)
            db.flush()
        created = []
        skipped = []
        for index, (name, email) in enumerate(USERS):
            user = db.query(User).filter(User.email == email).first()
            if user:
                skipped.append(email)
                continue
            user = User(email=email, full_name=name, hashed_password=hash_password(f"EliteDev2026!{index + 1}"),
                        role="analista" if index else "owner", company_id=company.id, email_verified=True)
            db.add(user)
            db.flush()
            created.append(email)
        db.flush()
        # Una suscripción por empresa da acceso Pro a todos sus miembros.
        sub = db.query(Subscription).filter(Subscription.company_id == company.id).first()
        if not sub:
            sub = Subscription(company_id=company.id, user_id=company.owner_user_id,
                               plan="profesional", status="activa", provider="manual",
                               current_period_end=datetime(2026, 12, 11, 4, 59, 59))
            db.add(sub)
        if not company.owner_user_id:
            owner = db.query(User).filter(User.company_id == company.id, User.role == "owner").first()
            if owner:
                company.owner_user_id = owner.id
                sub.user_id = owner.id
        db.commit()
        print({"company": company.id, "created": created, "skipped_existing": skipped,
               "password_pattern": "EliteDev2026!<número>",
               "premium_until_utc": "2026-12-11T04:59:59"})
    finally:
        db.close()

if __name__ == "__main__":
    main()

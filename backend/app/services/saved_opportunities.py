"""Saved state is user-owned and independent of the proposal workflow."""
from sqlalchemy import case,select,or_,and_
from app.db.models import UserOpportunity,Opportunity

def saved_condition():
    return or_(UserOpportunity.is_saved.is_(True),and_(UserOpportunity.is_saved.is_(None),UserOpportunity.triage.in_(['guardada','proyecto'])))

def is_saved(row):
    return bool(row and (row.is_saved if row.is_saved is not None else row.triage in {'guardada','proyecto'}))

def saved_first(query,user_id):
    saved=select(UserOpportunity.id).where(UserOpportunity.user_id==user_id,
        UserOpportunity.opportunity_id==Opportunity.id,saved_condition()).correlate(Opportunity).exists()
    return query.order_by(case((saved,0),else_=1))

from datetime import timedelta
import pytest
from sqlalchemy import event
from test_match_jobs import match_factory, prepare,run_job
from app.db.models import CompanyProfile,MatchJob,MatchSlot,UserOpportunity
from app.services import match_jobs as jobs
from app.services import match_execution as execution
from app.services.matcher import MatchResult


def test_external_compute_has_no_transaction_and_profile_edit_wins(match_factory,monkeypatch):
    uid=prepare(match_factory)
    with match_factory() as db:
        job=jobs.request_job(db,uid);db.commit()
        def score(*args,**kwargs):
            assert not db.in_transaction()
            with match_factory() as writer:
                p=writer.query(CompanyProfile).filter_by(user_id=uid).one();p.actividades='cambio concurrente';writer.commit()
            return MatchResult(75,[])
        monkeypatch.setattr(jobs,'score_opportunity',score)
        assert jobs.process_batch(db,job.id)['status']=='SUPERSEDED'
        assert db.query(UserOpportunity).count()==0


def test_lost_lease_cannot_confirm(match_factory,monkeypatch):
    uid=prepare(match_factory)
    with match_factory() as db:
        job=jobs.request_job(db,uid);db.commit()
        def score(*args,**kwargs):
            with match_factory() as writer:
                writer.query(MatchJob).filter_by(id=job.id).update({'lease_token':'replacement'})
                writer.query(MatchSlot).update({'token':'replacement'})
                writer.commit()
            return MatchResult(75,[])
        monkeypatch.setattr(jobs,'score_opportunity',score)
        jobs.process_batch(db,job.id)
        assert db.query(UserOpportunity).count()==0
        db.expire_all();assert db.get(MatchJob,job.id).cursor_id==0


def test_after_commit_failure_redelivery_is_idempotent(match_factory):
    uid=prepare(match_factory)
    with match_factory() as db:
        job=jobs.request_job(db,uid);db.commit();jid=job.id;once=[]
        def fail(session):
            if not once and any(isinstance(o,MatchJob) and o.state=='COMPLETED' for o in session.identity_map.values()):
                once.append(True);raise RuntimeError('lost commit acknowledgement')
        event.listen(db,'after_commit',fail)
        result=jobs.process_batch(db,jid)
        assert result['status']=='COMPLETED'
        assert jobs.process_batch(db,jid)['status']=='BUSY'
        assert db.query(UserOpportunity).count()==5


def test_coverage_never_rounds_incomplete_to_100():
    assert jobs.coverage_percentage(49999,50000)==99.99
    assert jobs.coverage_percentage(50000,50000)==100
    assert jobs.coverage_percentage(0,0) is None

def test_embedding_configuration_changed_before_confirmation(match_factory,monkeypatch):
    uid=prepare(match_factory)
    with match_factory() as db:
        job=jobs.request_job(db,uid);db.commit()
        def score(*a,**k):
            monkeypatch.setattr(jobs.get_settings(),'match_algorithm_version','changed-during-compute')
            return MatchResult(75,[])
        monkeypatch.setattr(jobs,'score_opportunity',score)
        assert jobs.process_batch(db,job.id)['status']=='SUPERSEDED'
        assert db.query(UserOpportunity).count()==0


def test_heartbeat_renews_only_current_owner(match_factory):
    uid=prepare(match_factory)
    with match_factory() as db:
        job=jobs.request_job(db,uid);db.commit()
        slot,token=jobs._acquire(db,job.id)
        assert execution.renew_lease(match_factory,slot,job.id,token)
        assert not execution.renew_lease(match_factory,slot,job.id,'foreign')
        db.query(MatchSlot).update({'lease_until':jobs.utc_now()-timedelta(seconds=1)});db.commit()
        assert not execution.renew_lease(match_factory,slot,job.id,token)

def test_failed_attempt_does_not_relabel_last_good_score(match_factory,monkeypatch):
    from app.db.models import MatchScoreHistory
    uid=prepare(match_factory,1);run_job(match_factory,uid)
    with match_factory() as db:
        old=db.query(UserOpportunity).one();good_version=old.profile_version
        p=db.query(CompanyProfile).one();p.actividades='nueva actividad';db.commit()
    original=jobs.score_opportunity
    def fail(*args,**kwargs):raise RuntimeError('provider unavailable')
    monkeypatch.setattr(jobs,'score_opportunity',fail);run_job(match_factory,uid)
    with match_factory() as db:
        old=db.query(UserOpportunity).one()
        assert old.profile_version==good_version
        assert old.failed_input_versions['profile_version']!=good_version
        assert jobs.coverage(db,uid)['failed_scores']==1
    monkeypatch.setattr(jobs,'score_opportunity',original);run_job(match_factory,uid)
    with match_factory() as db:
        history=db.query(MatchScoreHistory).one()
        assert history.versions['profile_version']==good_version
        assert db.query(UserOpportunity).one().failed_input_versions is None

def test_cancellation_during_compute_releases_only_own_slot(match_factory,monkeypatch):
    uid=prepare(match_factory,1)
    with match_factory() as db:
        job=jobs.request_job(db,uid);db.commit();jid=job.id
        def cancel(*a,**k):
            with match_factory() as other:
                jobs.cancel_job(other,other.get(MatchJob,jid));other.commit()
            return MatchResult(75,[])
        monkeypatch.setattr(jobs,'score_opportunity',cancel)
        assert jobs.process_batch(db,jid)['status']=='CANCELLED'
        assert db.query(UserOpportunity).count()==0
        assert db.query(MatchSlot).filter(MatchSlot.token.isnot(None)).count()==0

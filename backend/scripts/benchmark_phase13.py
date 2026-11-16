"""Benchmark sintético PG; presupuesto publicado antes de medir, sin extrapolar."""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import json
import hashlib
from datetime import datetime,timezone
import logging
import os
from pathlib import Path
import resource
from statistics import median
import sys
import tempfile
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pgserver import PostgresServer
import psycopg2
from sqlalchemy import create_engine,event,text,func
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.db.models import Base,CompanyProfile,MatchJob,MatchScoreHistory,Opportunity,User,UserOpportunity
from app.services import match_jobs as jobs
from app.services.matcher import MatchResult
from app.services.match_versions import current_score_condition
from app.services.opportunity_status import potentially_current_condition

BUDGET={'candidate_p95_ms':250,'ranking_p95_ms':500,'coverage_p95_ms':2000,'confirm_p95_ms':1000,
        'rss_bytes':512*1024*1024,'scores_per_second_min':500,'scenario_seconds_max':120,
        'pool_size':4,'workers':2,'batch_size':200,'embedding_dim':64}


def percentile(values,p):
    values=sorted(values)
    return values[min(len(values)-1,max(0,int((len(values)-1)*p)))] if values else None


class Recorder(logging.Handler):
    def __init__(self):super().__init__();self.records=[]
    def emit(self,record):
        try:
            value=json.loads(record.getMessage())
            if value.get('event')=='match_batch':self.records.append(value)
        except (ValueError,TypeError):pass


def scenario(server,count,users,output):
    name=f'mysecop_test_bench_{count}_{users}'
    c=psycopg2.connect(server.get_uri());c.autocommit=True
    with c.cursor() as cursor:cursor.execute(f'CREATE DATABASE {name}')
    c.close()
    engine=create_engine(server.get_uri(name).replace('postgresql://','postgresql+psycopg2://'),pool_size=4,max_overflow=0,pool_timeout=10)
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    for start in range(0,count,1000):
        with factory() as db:
            db.bulk_insert_mappings(Opportunity,[{'source':'secop1' if i%10==0 else 'qa','source_id':str(i),
                'objeto':f'software sector {i%6}','descripcion':'Suministros tecnológicos sintéticos',
                'departamento':'Meta' if i%2 else 'Bogotá D.C.','modalidad':'Licitación Pública',
                'estado':'Adjudicado' if i%10==1 else 'En proceso','cancelled':False,'valor':100000+i} for i in range(start,min(start+1000,count))])
            db.commit()
    job_ids=[]
    with factory() as db:
        for i in range(users):
            user=User(email=f'bench-{i}@example.invalid',hashed_password='fixture');db.add(user);db.flush()
            db.add(CompanyProfile(user_id=user.id,sector='software',keywords=['software']));db.commit()
            job=jobs.request_job(db,user.id);db.commit();job_ids.append((job.id,user.id))
    recorder=Recorder();jobs.logger.addHandler(recorder);jobs.logger.setLevel(logging.INFO)
    counts=Counter();pool={'active':0,'peak':0};lock=threading.Lock()
    def before(conn,cursor,statement,parameters,context,executemany):
        with lock:counts[statement.lstrip().split()[0].upper()]+=1
    def checkout(*args):
        with lock:pool['active']+=1;pool['peak']=max(pool['peak'],pool['active'])
    def checkin(*args):
        with lock:pool['active']-=1
    event.listen(engine,'before_cursor_execute',before);event.listen(engine,'checkout',checkout);event.listen(engine,'checkin',checkin)
    started=time.monotonic();deadline=started+BUDGET['scenario_seconds_max']
    def run(pair):
        jid,_=pair
        while time.monotonic()<deadline:
            with factory() as db:
                result=jobs.process_batch(db,jid)
            if result['status']=='COMPLETED':return True
            if result['status'] not in ('PENDING','BUSY','RETRY'):raise AssertionError(result)
            if result['status']=='BUSY':time.sleep(.01)
        return False
    with ThreadPoolExecutor(max_workers=2) as executor:finished=list(executor.map(run,job_ids))
    duration=time.monotonic()-started
    jobs.logger.removeHandler(recorder)
    latencies={'candidate':[],'ranking':[],'coverage':[]};plans={}
    with factory() as db:
        uid=job_ids[0][1]
        candidate=db.query(Opportunity).filter(Opportunity.id>count//2,potentially_current_condition()).order_by(Opportunity.id).limit(200)
        ranking=db.query(UserOpportunity,Opportunity).join(Opportunity,Opportunity.id==UserOpportunity.opportunity_id).filter(
            UserOpportunity.user_id==uid,current_score_condition(),UserOpportunity.score>=40).order_by(UserOpportunity.score.desc(),Opportunity.id.desc()).limit(25)
        statements={}
        for label,query in [('candidate',candidate),('ranking',ranking)]:
            for _ in range(10):
                t=time.monotonic();query.all();latencies[label].append((time.monotonic()-t)*1000)
            statements[label]=str(query.statement.compile(engine,compile_kwargs={'literal_binds':True}))
        captured=[]
        def capture(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('SELECT') and 'sum(CASE' in statement:captured.append((statement,parameters))
        event.listen(engine,'before_cursor_execute',capture)
        measured=[]
        for _,user_id in job_ids:
            for _ in range(3):
                t=time.monotonic();c=jobs.coverage(db,user_id);latencies['coverage'].append((time.monotonic()-t)*1000)
            measured.append(c['coverage_percent'])
        event.remove(engine,'before_cursor_execute',capture)
        for label,sql in statements.items():plans[label]=db.execute(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+sql)).scalar_one()
        if captured:
            sql,params=captured[0]
            plans['coverage']=db.connection().exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+sql,params).scalar_one()
        for label,sql in {
            'valid_scores':f'SELECT * FROM user_opportunities WHERE user_id={uid} ORDER BY opportunity_id LIMIT 200',
            'jobs':f'SELECT * FROM match_jobs WHERE user_id={uid} ORDER BY created_at DESC LIMIT 1',
            'slots':'SELECT * FROM match_slots WHERE id=1 FOR UPDATE',
            'history':f'SELECT * FROM match_score_history WHERE user_id={uid} ORDER BY recorded_at DESC LIMIT 20',
            'filters':"SELECT id FROM opportunities WHERE departamento='Meta' AND valor>=100000 ORDER BY id LIMIT 25",
        }.items():plans[label]=db.execute(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+sql)).scalar_one()
        confirmed=db.query(func.sum(MatchJob.scored)).scalar() or 0
        db.rollback()
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss=rss if sys.platform=='darwin' else rss*1024
    result={'opportunities':count,'users':users,'completed':all(finished),'duration_seconds':duration,'confirmed_scores':confirmed,
        'throughput':confirmed/duration,'sql_statements':dict(counts),'pool_peak':pool['peak'],'pool_timeout_errors':0,
        'rss_process_peak_bytes':rss,'coverage_percent_per_user':measured,
        'latencies_ms':{k:{'p50':median(v),'p95':percentile(v,.95)} for k,v in latencies.items()},
        'batch_confirm_ms':{'p50':percentile([r['confirm_seconds']*1000 for r in recorder.records],.5),
                            'p95':percentile([r['confirm_seconds']*1000 for r in recorder.records],.95)},
        'batch_sql_max':max((r['queries'] for r in recorder.records),default=0),
        'batch_selects_max':max((r['read_queries'] for r in recorder.records),default=0)}
    result['budget_pass']=(all(finished) and result['throughput']>=500 and rss<=BUDGET['rss_bytes']
        and latencies['candidate'] and result['latencies_ms']['candidate']['p95']<=250
        and result['latencies_ms']['ranking']['p95']<=500 and result['latencies_ms']['coverage']['p95']<=2000
        and (result['batch_confirm_ms']['p95'] or 0)<=1000)
    (output/f'plans-{count}-{users}.json').write_text(json.dumps(plans,indent=2,default=str))
    engine.dispose()
    print(json.dumps(result),flush=True)
    return result


def main():
    output=Path(__file__).resolve().parents[1]/'benchmarks/phase13';output.mkdir(parents=True,exist_ok=True)
    settings=get_settings();settings.embedding_provider='fake';settings.embedding_dim=64;settings.match_batch_size=200;settings.match_global_concurrency=2
    # Controla scoring para aislar infra/DB; embeddings fake reales, no API externa.
    jobs.score_opportunity=lambda *a,**k:MatchResult(75,[])
    results=[]
    with PostgresServer(Path(tempfile.mkdtemp(prefix='mysecop-phase13-bench-')),cleanup_mode='stop') as server:
        for count in (1000,10000,50000):
            for users in (1,10):
                results.append(scenario(server,count,users,output))
                (output/'results.json').write_text(json.dumps({'budget':BUDGET,'scoring':'controlled constant; fake vectors 64; synthetic only',
                    'measured_at':datetime.now(timezone.utc).isoformat(),
                    'engine_sha256':hashlib.sha256((Path(__file__).resolve().parents[1]/'app/services/match_execution.py').read_bytes()).hexdigest(),
                    'results':results},indent=2))
    return 0

if __name__=='__main__':sys.exit(main())

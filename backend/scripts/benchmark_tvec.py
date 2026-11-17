"""10k fictional orders in a newly created disposable PG; no operational URL input."""
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import statistics
import sys
import tempfile
from time import perf_counter

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    from pgserver import PostgresServer
    import psycopg2
    from sqlalchemy import create_engine,event,text
    from sqlalchemy.orm import Session
    from app.db.models import Base,TvecPurchaseOrder as Order
    from app.routers.tvec import orders,groups,summary
    directory=Path(tempfile.mkdtemp(prefix='mysecop-tvec-benchmark-'))
    with PostgresServer(directory,cleanup_mode='stop') as server:
        connection=psycopg2.connect(server.get_uri());connection.autocommit=True
        with connection.cursor() as cursor:cursor.execute('CREATE DATABASE mysecop_test_tvec_benchmark')
        connection.close()
        engine=create_engine(server.get_uri('mysecop_test_tvec_benchmark').replace('postgresql://','postgresql+psycopg2://'))
        Base.metadata.create_all(engine,tables=[t for t in Base.metadata.tables.values() if t.name.startswith('tvec_')])
        rows=[]
        for i in range(10000):
            rows.append(dict(official_id='BENCH-'+str(i).zfill(8),source_row_id='ROW-'+str(i),buyer='Synthetic buyer '+str(i%100),
                supplier='Synthetic supplier '+str(i%200),description='Synthetic software purchase',instrument='Synthetic instrument '+str(i%10),
                department='Meta' if i%2==0 else 'Cundinamarca',amount=Decimal(i*100),issued_at=datetime(2025,1+i%12,1),
                raw_json={'synthetic':True},version='fixture',seen_cycle='synthetic-cycle',synced_at=datetime(2026,11,16)))
        with engine.begin() as c:c.execute(Order.__table__.insert(),rows);c.execute(text('ANALYZE tvec_purchase_orders'))
        count=[0]
        @event.listens_for(engine,'before_cursor_execute')
        def measure(*args):count[0]+=1
        results={}
        with Session(engine) as db:
            for label,call in {
                'page20_filtered':lambda:orders(db,[Order.department=='Meta',Order.amount>=20000],20,0),
                'page50_filtered':lambda:orders(db,[Order.department=='Meta',Order.amount>=20000],50,0),
                'page20_offset5000':lambda:orders(db,[],20,5000),
                'buyers_grouped':lambda:groups(db,[],Order.buyer,20,0),
                'summary':lambda:summary(db,[]),
            }.items():
                timings=[];queries=[]
                for _ in range(7):
                    count[0]=0;started=perf_counter();call();timings.append((perf_counter()-started)*1000);queries.append(count[0])
                results[label]={'median_ms':round(statistics.median(timings),3),'max_ms':round(max(timings),3),'sql_queries':queries}
        engine.dispose()
    result={'dataset':'SYNTHETIC_ONLY','orders':10000,'database':'temporary PostgreSQL 16.2','samples_per_query':7,
            'results':results,'limits':'Local single-client evidence, not millions of records, concurrency capacity or operational SLA.'}
    print(json.dumps(result,indent=2))
    return 0

if __name__=='__main__':sys.exit(main())

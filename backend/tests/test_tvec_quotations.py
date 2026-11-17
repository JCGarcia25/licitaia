"""Synthetic official-shape HTML; live HTTP and real PG are separate checks."""
from datetime import datetime,timedelta
from copy import deepcopy
from html import escape
import pytest
from test_tvec import tvec
from app.services import tvec_quotations as events
from app.db.models import TvecQuotationEvent as Event,TvecQuotationSnapshot as Snapshot,Opportunity
from app.core.config import get_settings
INSTANT=datetime(2026,11,17,14)

def table(rows):
    return '<table><tr>'+''.join('<th>'+h+'</th>' for h in events.HEADERS)+'</tr>'+''.join('<tr>'+''.join('<td>'+escape(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</table>'

def source(identifier='901',title='RFQ - Empresa ficticia',start='2026-11-17 08:00:00.0000000',end='2026-11-18 17:00:00.0000000'):
    return [identifier,title,'Entidad ficticia',start,end,'Producción','Instrumento ficticio','','0','$0']

def detail(row):
    fields=dict(zip(['Evento','Nombre','Entidad','Inicio','Final','Estado','Agregacion','Proveedor','Orden','Valor'],row))
    return ''.join('<div><strong>'+k+'</strong> : <span>'+escape(v)+'</span></div>' for k,v in fields.items())

def prepared():
    row=events.listing(table([source()]))[0];row.pop('has_award');row['detail_verified']=True;row['kind_evidence']='EXPLICIT_RFQ_TITLE_AND_MATCHING_DETAIL';return row

class Fake:
    def __init__(self,rows=None):self.rows=deepcopy(rows if rows is not None else [prepared()])
    def collect(self):return self.rows,1

@pytest.fixture
def quotations(tvec,monkeypatch):
    for table_ in [Event.__table__,Snapshot.__table__]:table_.create(tvec.bind,checkfirst=True);tvec.execute(table_.delete())
    tvec.commit();s=get_settings()
    monkeypatch.setattr(s,'tvec_events_enabled',True);monkeypatch.setattr(s,'tvec_events_refresh_enabled',True)
    monkeypatch.setattr(events,'now',lambda:INSTANT);monkeypatch.setattr('app.services.tvec_client.now',lambda:INSTANT)
    return tvec

def test_parser_public_schema_dates_types_detail_and_minimisation():
    rows=events.listing(table([source(),source('902','RFI - información'),source('903','Compra sin tipo'),source('904','RFI RFQ ambiguo'),source('905','RFQ - incompleta',end='2026-11-17 07:00:00.0000000')]))
    assert [r['kind'] for r in rows]==['RFQ','RFI','UNKNOWN','UNKNOWN','UNKNOWN']
    assert rows[0]['opens_at']==datetime(2026,11,17,13)
    assert events.verify_detail(detail(source()),rows[0])
    assert 'Comprador' not in rows[0] and 'amount' not in rows[0]
    with pytest.raises(ValueError):events.verify_detail(detail(source(title='RFQ - cambiado')),rows[0])
    with pytest.raises(ValueError):events.listing(table([source(),source()]))
    with pytest.raises(ValueError):events.listing(table([source(start='not-a-date')]))
    with pytest.raises(ValueError):events.listing(table([source()]).replace('Finaliza','Cambio'))
    awarded=source();awarded[7]='Proveedor ficticio'
    with pytest.raises(ValueError):events.verify_detail(detail(awarded),rows[0])

def test_collector_bounds_rfi_exclusion_and_schema_failure(monkeypatch):
    monkeypatch.setattr(events,'now',lambda:INSTANT);calls=[]
    rows=[source(str(1000+i),'RFI - consulta') for i in range(15)];rows[0]=source()
    def get(self,path,params=None):
        calls.append((path,params));return detail(source()) if 'detalle-' in path else table(rows)
    monkeypatch.setattr(events.Client,'get',get)
    with pytest.raises(ValueError):events.Client().collect()
    assert len([p for p,q in calls if p=='/eventos-cotizacion-tvec'])==2
    assert len([p for p,q in calls if 'detalle-' in p])==1

def test_atomic_refresh_freshness_disappearance_rfi_unknown_and_no_matching(quotations,client,auth_headers,monkeypatch):
    db=quotations;before=db.query(Opportunity).count();rows=[prepared()]
    for ident,title in [('902','RFI - consulta'),('903','Sin tipo')]:
        row=events.listing(table([source(ident,title)]))[0];row.pop('has_award');rows.append(row)
    class OutsideTransaction(Fake):
        def collect(self):assert not db.in_transaction();return super().collect()
    assert events.refresh(db,OutsideTransaction(rows))=='DONE'
    response=client.get('/api/tvec/quotations',headers=auth_headers);assert response.status_code==200,response.text
    result=response.json();assert result['total']==1 and result['items'][0]['eligibility']=='PENDING_VERIFICATION'
    assert result['provenance']['excluded_rfi']==1 and result['provenance']['excluded_unknown']==1
    assert client.get('/api/tvec/quotations?q=%25',headers=auth_headers).json()['total']==0
    assert events.refresh(db,Fake(rows))=='DONE' and db.query(Event).count()==3
    monkeypatch.setattr('app.services.tvec_client.now',lambda:INSTANT+timedelta(minutes=46))
    assert client.get('/api/tvec/quotations',headers=auth_headers).json()['total']==0
    monkeypatch.setattr('app.services.tvec_client.now',lambda:INSTANT)
    assert events.refresh(db,Fake([]))=='DONE'
    assert client.get('/api/tvec/quotations',headers=auth_headers).json()['total']==0
    assert db.query(Event).count()==3 and db.query(Opportunity).count()==before

def test_lease_fencing_and_failed_refresh_preserves_publication(quotations):
    db=quotations;events.refresh(db,Fake());old=db.get(Snapshot,events.SOURCE).published_snapshot;db.rollback()
    class Lost(Fake):
        def collect(self):
            with type(db)(bind=db.bind) as other:
                other.query(Snapshot).update({'lease_token':'successor'});other.commit()
            return super().collect()
    with pytest.raises(RuntimeError):events.refresh(db,Lost())
    assert db.get(Snapshot,events.SOURCE).published_snapshot==old
    assert db.get(Snapshot,events.SOURCE).lease_token=='successor'

def test_expired_future_unverified_and_closed_excluded(quotations,client,auth_headers):
    db=quotations;rows=[]
    for ident,updates in [('901',{}),('902',{'opens_at':INSTANT+timedelta(days=1)}),('903',{'closes_at':INSTANT}),('904',{'status':'Finalizado'}),('905',{'detail_verified':False})]:
        row=prepared();row.update(official_id=ident,**updates);rows.append(row)
    events.refresh(db,Fake(rows));result=client.get('/api/tvec/quotations',headers=auth_headers).json()
    assert [r['official_id'] for r in result['items']]==['901']

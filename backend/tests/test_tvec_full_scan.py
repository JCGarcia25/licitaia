"""Full traversal over synthetic official-shape HTML; no real HTTP."""
from copy import deepcopy
from datetime import timedelta
import httpx
import pytest
from test_tvec import tvec
from test_tvec_quotations import quotations,source,table,detail,prepared,Fake,INSTANT
from app.services import tvec_quotations as quotes,tvec_full_scan as full
from app.db.models import TvecQuotationSnapshot as Snapshot,TvecQuotationEvent as Event,Opportunity


class Pages(full.Client):
    def __init__(self):
        self.pages=[[source(str(1000+i),'RFI - consulta') for i in range(15)],
                    [source(str(1015+i),'Sin tipo') for i in range(15)],
                    [source('1030'),source('1031','RFQ - futura',start='2026-11-18 08:00:00.0000000'),source('1032','RFI - consulta')]]
        self.pages[0][0]=source('1000');self.pages[0][1]=source('1001',end='2026-11-17 07:00:00.0000000')
        self.calls=[];self.fail_page=None
    def get(self,path,params=None):
        self.calls.append((path,params))
        if 'detalle-' in path:
            ident=path.rsplit('/',1)[-1]
            return detail(next(r for page in self.pages for r in page if r[0]==ident))
        number=int(params['page'])
        if number==self.fail_page:raise httpx.ConnectError('synthetic interruption')
        return table(self.pages[number])+'<a href="/eventos-cotizacion-tvec?Estado_1=2&amp;page=2">última »</a>'


@pytest.fixture
def scan(quotations,monkeypatch):
    monkeypatch.setattr(full,'now',lambda:INSTANT)
    return quotations


def test_full_walk_publishes_only_open_after_last_page_and_redelivery_is_noop(scan,client,auth_headers):
    db=scan;quotes.refresh(db,Fake());old=db.get(Snapshot,quotes.SOURCE).published_snapshot;db.rollback()
    before=db.query(Opportunity).count();c=Pages()
    first=full.refresh_batch(db,client=c)
    assert first['status']=='MORE' and first['pages']==2
    assert db.get(Snapshot,quotes.SOURCE).published_snapshot==old and db.query(Event).count()==1
    partial=client.get('/api/tvec/quotations',headers=auth_headers).json()
    assert partial['provenance']['coverage']=='BOUNDED_RECENT_PAGES_NOT_EXHAUSTIVE'
    assert partial['provenance']['scan_progress']['pages']==2 and partial['total']==1
    second=full.refresh_batch(db,first['scan_id'],c)
    assert second['status']=='DONE' and second['pages']==3 and second['rows']==33
    state=db.get(Snapshot,quotes.SOURCE);p=state.scan_progress
    assert p['complete'] and p['published_complete'] and p['counts']['qualified']==2
    assert len(p['seen'])==33 and p['counts']['unavailable']==1 # invalid interval is UNKNOWN, future is unavailable
    visible=db.query(Event).filter_by(snapshot_id=state.published_snapshot).all()
    assert {r.official_id for r in visible}=={'1000','1030'}
    assert all(r.kind=='RFQ' and r.detail_verified for r in visible)
    complete=client.get('/api/tvec/quotations',headers=auth_headers).json()
    assert complete['total']==2 and complete['provenance']['coverage']=='OFFICIAL_LISTING_TRAVERSED'
    assert db.query(Event).count()==3 and db.query(Opportunity).count()==before
    calls=len(c.calls)
    assert full.refresh_batch(db,first['scan_id'],c)['status']=='DONE'
    assert full.refresh_batch(db,client=c)['status']=='DONE' and len(c.calls)==calls
    assert db.get(Snapshot,quotes.SOURCE,populate_existing=True).lease_token is None


def test_resume_after_network_failure_keeps_committed_cursor_and_old_publication(scan):
    db=scan;c=Pages();first=full.refresh_batch(db,client=c);c.fail_page=2
    with pytest.raises(httpx.ConnectError):full.refresh_batch(db,first['scan_id'],c)
    state=db.get(Snapshot,quotes.SOURCE)
    assert state.scan_progress['next_page']==2 and state.published_snapshot is None and state.status=='ERROR'
    assert db.query(Event).count()==0
    c.fail_page=None
    assert full.refresh_batch(db,first['scan_id'],c)['status']=='DONE'
    assert db.query(Event).count()==2


def test_changed_head_restarts_without_mixing_generations_and_old_delivery_cannot_restart(scan):
    db=scan;c=Pages();first=full.refresh_batch(db,client=c)
    c.pages[0][2][1]='RFI - título cambiado'
    restarted=full.refresh_batch(db,first['scan_id'],c)
    assert restarted['status']=='MORE' and restarted['scan_id']!=first['scan_id'] and restarted['pages']==2
    calls=len(c.calls)
    assert full.refresh_batch(db,first['scan_id'],c)['status']=='DONE' and len(c.calls)==calls
    assert full.refresh_batch(db,restarted['scan_id'],c)['status']=='DONE'
    assert db.get(Snapshot,quotes.SOURCE).scan_progress['restarts']==1


def test_full_scan_missing_dates_excluded_and_pager_budget_fail_closed():
    row=source();row[4]=''
    parsed=quotes.listing(table([row]),allow_missing_dates=True)
    assert parsed[0]['kind']=='UNKNOWN'
    with pytest.raises(ValueError):quotes.listing(table([row]))
    with pytest.raises(ValueError):full.last_page('<a href="/eventos-cotizacion-tvec?Estado_1=2&amp;page=1000">última</a>')

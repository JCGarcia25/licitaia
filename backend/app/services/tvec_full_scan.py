"""Traverse all pages in bounded resumable batches; persist only verified open RFQ.

The old publication stays visible until a complete stable traversal is committed.
Source pagination is not a transactional API: completion means all pages walked,
not certified real-time Coupa availability or eligibility for every company.
"""
from copy import deepcopy
from datetime import datetime,timedelta
from html import unescape
import re
import time
from urllib.parse import urlsplit,parse_qs
from uuid import uuid4

import httpx
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.db.models import TvecQuotationSnapshot as Snapshot,TvecQuotationEvent as Event
from app.services import tvec_quotations as source
from app.services.tvec_client import now
from app.services.tvec_guard import require_target
from app.services.match_versions import digest

MAX_SOURCE_PAGES=1000
BATCH_PAGES=2


def last_page(html):
    pages=[0]
    for href in re.findall(r'<a\b[^>]*href=[\"\']([^\"\']+)[\"\']',html,re.I):
        url=urlsplit(unescape(href))
        if url.path!='/eventos-cotizacion-tvec':continue
        query=parse_qs(url.query)
        if query.get('Estado_1')!=['2'] or 'page' not in query:continue
        value=query['page'][0]
        if not value.isdigit() or int(value)>=MAX_SOURCE_PAGES:raise ValueError('Source page budget requires review')
        pages.append(int(value))
    return max(pages)


def signature(rows):
    return digest([{k:r[k].isoformat() if isinstance(r[k],datetime) else r[k]
                    for k in ['official_id','title','buyer','instrument','status','opens_at','closes_at']} for r in rows])


def new_progress(previous=None,restarts=0):
    old=previous or {}
    return {'id':str(uuid4()),'next_page':0,'total_pages':None,'head':None,
            'started_at':now().isoformat(),'complete':False,'seen':[],'candidates':{},
            'counts':{'rows':0,'rfi':0,'unknown':0,'unavailable':0,'detail_failed':0,'qualified':0},
            'restarts':restarts,'published_complete':old.get('published_complete',False),
            'published_counts':old.get('published_counts',{})}


class Client(source.Client):
    def batch(self,progress):
        progress=deepcopy(progress);started=time.monotonic()
        html=self.get('/eventos-cotizacion-tvec',{'Estado_1':'2','page':'0'})
        head=source.listing(html,allow_missing_dates=True);fingerprint=signature(head);pages=last_page(html)+1
        if progress['head'] and (progress['head']!=fingerprint or progress['total_pages']!=pages):
            if progress['restarts']>=3:raise ValueError('Source pagination remains unstable')
            progress=new_progress(progress,progress['restarts']+1)
        progress['head']=fingerprint;progress['total_pages']=pages
        seen=set(progress['seen']);counts=progress['counts']
        for page in range(progress['next_page'],min(pages,progress['next_page']+BATCH_PAGES)):
            rows=head if page==0 else source.listing(self.get('/eventos-cotizacion-tvec',{'Estado_1':'2','page':str(page)}),allow_missing_dates=True)
            if (page<pages-1 and len(rows)!=source.PAGE_SIZE) or (page==pages-1 and pages>1 and not rows):
                raise ValueError('Source pagination shrank during scan')
            for row in rows:
                if time.monotonic()-started>150:raise TimeoutError('Full-scan batch budget expired')
                ident=row['official_id']
                if ident in seen:raise ValueError('Duplicate event across source pages; retain progress for review')
                seen.add(ident);counts['rows']+=1
                if row['kind']=='RFI':counts['rfi']+=1;continue
                if row['kind']!='RFQ':counts['unknown']+=1;continue
                if source.fold(row['status'])!='produccion' or row.pop('has_award') or not row['opens_at']<=now()<row['closes_at']:
                    counts['unavailable']+=1;continue
                try:
                    source.verify_detail(self.get('/detalle-cotizacion/'+ident),row)
                except ValueError:
                    counts['detail_failed']+=1;continue
                except httpx.HTTPStatusError as error:
                    if error.response.status_code not in {404,410}:raise
                    counts['detail_failed']+=1;continue
                row['detail_verified']=True;row['kind_evidence']='EXPLICIT_RFQ_TITLE_AND_MATCHING_DETAIL'
                row['verified_at']=now().isoformat()
                for key in ['opens_at','closes_at']:row[key]=row[key].isoformat()
                progress['candidates'][ident]=row;counts['qualified']+=1
            progress['next_page']=page+1
        progress['seen']=sorted(seen)
        if progress['next_page']==pages:
            # Recheck the pagination boundary after reading the final page.
            final=self.get('/eventos-cotizacion-tvec',{'Estado_1':'2','page':'0'})
            if signature(source.listing(final,allow_missing_dates=True))!=fingerprint or last_page(final)+1!=pages:
                if progress['restarts']>=3:raise ValueError('Source changed at completion')
                return new_progress(progress,progress['restarts']+1),False
            progress['complete']=True
        return progress,progress['complete']


def refresh_batch(db,expected_scan=None,client=None):
    source.configured(refresh=True);require_target(db)
    try:
        if db.get(Snapshot,source.SOURCE) is None:db.add(Snapshot(source=source.SOURCE));db.commit()
        else:db.rollback()
    except IntegrityError:db.rollback()
    token=str(uuid4());instant=now()
    acquired=db.query(Snapshot).filter(Snapshot.source==source.SOURCE,
        or_(Snapshot.lease_until.is_(None),Snapshot.lease_until<=instant)).update(
        {'lease_token':token,'lease_until':instant+timedelta(minutes=5),'status':'RUNNING'},synchronize_session=False)
    db.commit()
    if not acquired:return {'status':'BUSY'}
    try:
        state=db.get(Snapshot,source.SOURCE,populate_existing=True);progress=deepcopy(state.scan_progress)
        # Redelivery of an already-completed or superseded generation cannot start a new crawl.
        stale_delivery=expected_scan and (not progress or progress['id']!=expected_scan or progress['complete'])
        cached=progress and progress['complete'] and state.checked_at and state.checked_at>=now()-timedelta(minutes=1)
        if stale_delivery or cached:
            state.lease_token=None;state.lease_until=None;state.status='IDLE' if progress and progress['complete'] else 'SCANNING'
            db.commit();return {'status':'DONE','scan_id':progress['id'] if progress else None}
        if not progress or progress['complete']:progress=new_progress(progress)
        state.scan_progress=deepcopy(progress);db.commit()
        progress,complete=(client or Client()).batch(progress) # No DB transaction during HTTP.
        source.configured(refresh=True);require_target(db)
        owner=db.query(Snapshot).filter(Snapshot.source==source.SOURCE,Snapshot.lease_token==token,Snapshot.lease_until>now()).with_for_update().populate_existing().one_or_none()
        if owner is None:raise RuntimeError('Full-scan lease lost')
        if complete:
            instant=now();active=[]
            for values in progress['candidates'].values():
                values=deepcopy(values);verified=datetime.fromisoformat(values.pop('verified_at'))
                for key in ['opens_at','closes_at']:values[key]=datetime.fromisoformat(values[key])
                if not values['opens_at']<=instant<values['closes_at']:
                    progress['counts']['unavailable']+=1;continue
                if verified<instant-timedelta(minutes=source.FRESH_MINUTES):
                    progress['counts']['detail_failed']+=1;continue
                active.append((values,verified))
            existing={r.official_id:r for r in db.query(Event).filter(Event.official_id.in_([v['official_id'] for v,t in active])).all()}
            for values,verified in active:
                row=existing.get(values['official_id'])
                if row is None:row=Event(official_id=values['official_id']);db.add(row)
                for key,value in values.items():setattr(row,key,value)
                row.snapshot_id=progress['id'];row.checked_at=verified
            progress['counts']['qualified']=len(active)
            progress['published_complete']=True;progress['published_counts']=deepcopy(progress['counts']);progress['candidates']={}
            owner.published_snapshot=progress['id'];owner.checked_at=instant
            owner.scanned_pages=progress['next_page'];owner.scanned_rows=progress['counts']['rows']
            owner.excluded_rfi=progress['counts']['rfi'];owner.excluded_unknown=progress['counts']['unknown']+progress['counts']['detail_failed']
        owner.scan_progress=deepcopy(progress);owner.status='IDLE' if complete else 'SCANNING';owner.error_type=None
        db.flush()
        if owner.lease_until<=now():raise RuntimeError('Full-scan lease expired before commit')
        owner.lease_token=None;owner.lease_until=None;db.commit()
        return {'status':'DONE' if complete else 'MORE','scan_id':progress['id'],
                'pages':progress['next_page'],'total_pages':progress['total_pages'],'rows':progress['counts']['rows']}
    except Exception as error:
        db.rollback()
        db.query(Snapshot).filter_by(source=source.SOURCE,lease_token=token).update(
            {'status':'ERROR','error_type':type(error).__name__,'lease_token':None,'lease_until':None},synchronize_session=False)
        db.commit();raise

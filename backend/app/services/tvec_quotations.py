"""Bounded official HTML adapter. RFQ evidence is an explicit title marker,
confirmed against the public detail, never inferred from an order or RFI.
Publication is atomic, leased and DEV-only. No buyer-person data is retained.
"""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import re
import time
import unicodedata
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db.models import TvecQuotationEvent as Event, TvecQuotationSnapshot as Snapshot
from app.services.tvec_client import now
from app.services.tvec_guard import configuration, require_target
from app.services.evaluation_guard import EnvironmentDenied

ORIGIN = 'https://operaciones.colombiacompra.gov.co'
SOURCE_URL = ORIGIN + '/eventos-cotizacion-tvec'
SOURCE = 'public-quotations'
HEADERS = ['Id','Nombre','Entidad','Inicio','Finaliza','Estado','Instrumento',
           'Proveedor seleccionado','Orden de compra','Valor']
MAX_PAGES = 2
PAGE_SIZE = 15
FRESH_MINUTES = 45


def configured(*, refresh=False):
    s, _, _ = configuration()
    if not s.tvec_events_enabled or (refresh and not s.tvec_events_refresh_enabled):
        raise EnvironmentDenied('TVEC quotations disabled')
    return s


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.casefold()) if not unicodedata.combining(c))


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[]; self.row=None; self.cell=None; self.text=[]

    def handle_starttag(self, tag, attrs):
        if tag=='tr': self.row=[]
        if tag in {'td','th'} and self.row is not None: self.cell=[]

    def handle_data(self, value):
        self.text.append(value)
        if self.cell is not None: self.cell.append(value)

    def handle_endtag(self, tag):
        if tag in {'td','th'} and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split())); self.cell=None
        if tag=='tr' and self.row is not None:
            self.rows.append(self.row); self.row=None


def date(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{1,7})?', value):
        raise ValueError('Unexpected public date format')
    # The official page publishes Colombian local wall time without an offset.
    return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo('America/Bogota')).astimezone(timezone.utc).replace(tzinfo=None)


def kind(title):
    rfq=bool(re.search(r'(?<!\w)RFQ(?!\w)',title,re.I))
    rfi=bool(re.search(r'(?<!\w)RFI(?!\w)',title,re.I))
    return 'RFQ' if rfq and not rfi else 'RFI' if rfi and not rfq else 'UNKNOWN'


def listing(html, *, allow_missing_dates=False):
    doc=Document(); doc.feed(html)
    if HEADERS not in doc.rows: raise ValueError('Quotation table schema changed')
    data=[]; seen=set()
    for row in doc.rows:
        if row==HEADERS: continue
        if row and re.fullmatch(r'\d+',row[0]):
            if len(row)!=10 or len(row[0])>32 or row[0] in seen: raise ValueError('Invalid or repeated event')
            seen.add(row[0])
            if allow_missing_dates and (not row[3] or not row[4]):
                start=end=datetime.min
            else:start,end=date(row[3]),date(row[4])
            complete=start<end and all(row[i] for i in [1,2,5,6])
            if len(row[1])>4000 or len(row[2])>2000 or len(row[6])>2000: raise ValueError('Unexpected source lengths')
            data.append(dict(official_id=row[0],title=row[1],buyer=row[2],instrument=row[6],
                status=row[5],kind=kind(row[1]) if complete else 'UNKNOWN',opens_at=start,closes_at=end,
                official_url=ORIGIN+'/detalle-cotizacion/'+row[0],detail_verified=False,
                kind_evidence='TITLE_MARKER_ONLY' if complete else 'INCOMPLETE_OR_INCONSISTENT_FIELDS',
                # Award/order absence is checked, not treated as a budget.
                has_award=bool(row[7] or row[8] not in {'','0'})))
    if len(data)>PAGE_SIZE: raise ValueError('Public page size changed')
    return data


def verify_detail(html, row):
    doc=Document(); doc.feed(html); text=' '.join(' '.join(doc.text).split())
    labels=list(re.finditer(r'\b(Evento|Nombre|Entidad|Comprador|Inicio|Final|Estado|Agregacion|Proveedor|Orden|Valor)\s*:\s*',text))
    fields={m[1]:text[m.end():labels[i+1].start() if i+1<len(labels) else len(text)].strip() for i,m in enumerate(labels)}
    if any(fields.get(k)!=row[v] for k,v in [('Evento','official_id'),('Nombre','title'),('Entidad','buyer'),('Estado','status'),('Agregacion','instrument')]):
        raise ValueError('Public listing and detail differ')
    if date(fields.get('Inicio',''))!=row['opens_at'] or date(fields.get('Final',''))!=row['closes_at']:
        raise ValueError('Public dates differ')
    if fields.get('Proveedor') or fields.get('Orden') not in {'','0'}: raise ValueError('Awarded event excluded')
    return True


class Client:
    def get(self, path, params=None):
        for attempt in range(3):
            try:
                with httpx.Client(timeout=10, follow_redirects=False) as client:
                    with client.stream('GET',ORIGIN+path,params=params,headers={'User-Agent':'MySECOP-TVEC-DEV/1.0'}) as response:
                        if response.status_code in {429,502,503,504} and attempt<2:
                            time.sleep(2**attempt);continue
                        response.raise_for_status()
                        chunks=[];size=0
                        for chunk in response.iter_bytes():
                            size+=len(chunk)
                            if size>1_500_000: raise ValueError('Public page too large')
                            chunks.append(chunk)
                        return b''.join(chunks).decode('utf-8')
            except (httpx.NetworkError,httpx.TimeoutException):
                if attempt==2: raise
                time.sleep(2**attempt)

    def collect(self):
        result=[];seen=set();pages=0;started=time.monotonic()
        for page in range(MAX_PAGES):
            rows=listing(self.get('/eventos-cotizacion-tvec',{'Estado_1':'2','page':str(page)}));pages+=1
            for row in rows:
                if time.monotonic()-started>150: raise TimeoutError('Bounded quotation refresh expired')
                if row['official_id'] in seen: raise ValueError('Pagination changed during collection')
                seen.add(row['official_id'])
                if row['kind']=='RFQ' and fold(row['status'])=='produccion' and not row['has_award'] and row['opens_at']<=now()<row['closes_at']:
                    try:
                        row['detail_verified']=verify_detail(self.get('/detalle-cotizacion/'+row['official_id']),row)
                        row['kind_evidence']='EXPLICIT_RFQ_TITLE_AND_MATCHING_DETAIL'
                    except ValueError:
                        row['kind_evidence']='PUBLIC_DETAIL_MISMATCH'
                    except httpx.HTTPStatusError as error:
                        if error.response.status_code not in {404,410}:raise
                        row['kind_evidence']='PUBLIC_DETAIL_UNAVAILABLE'
                row.pop('has_award');result.append(row)
            if len(rows)<PAGE_SIZE: break
        return result,pages


def refresh(db, client=None):
    configured(refresh=True);require_target(db)
    try:
        if db.get(Snapshot,SOURCE) is None:
            db.add(Snapshot(source=SOURCE));db.commit()
        else: db.rollback()
    except IntegrityError: db.rollback()
    token=str(uuid4());instant=now()
    acquired=db.query(Snapshot).filter(Snapshot.source==SOURCE,or_(Snapshot.lease_until.is_(None),Snapshot.lease_until<=instant)).update(
        {'lease_token':token,'lease_until':instant+timedelta(minutes=5),'status':'RUNNING'},synchronize_session=False)
    db.commit()
    if not acquired:return 'BUSY'
    try:
        rows,pages=(client or Client()).collect() # No database transaction during HTTP.
        configured(refresh=True);require_target(db)
        owner=db.query(Snapshot).filter(Snapshot.source==SOURCE,Snapshot.lease_token==token,Snapshot.lease_until>now()).with_for_update().one_or_none()
        if owner is None: raise RuntimeError('Quotation lease lost')
        instant=now();existing={r.official_id:r for r in db.query(Event).filter(Event.official_id.in_([r['official_id'] for r in rows])).all()}
        for values in rows:
            row=existing.get(values['official_id'])
            if row is None:row=Event(official_id=values['official_id']);db.add(row)
            for key,value in values.items():setattr(row,key,value)
            row.checked_at=instant;row.snapshot_id=token
        owner.published_snapshot=token;owner.checked_at=instant;owner.scanned_pages=pages;owner.scanned_rows=len(rows)
        owner.excluded_rfi=sum(r['kind']=='RFI' for r in rows);owner.excluded_unknown=sum(r['kind']=='UNKNOWN' or (r['kind']=='RFQ' and not r['detail_verified']) for r in rows)
        owner.error_type=None;owner.status='IDLE'
        db.flush()
        if owner.lease_until<=now():raise RuntimeError('Quotation lease expired before commit')
        owner.lease_token=None;owner.lease_until=None;db.commit();return 'DONE'
    except Exception as error:
        db.rollback()
        db.query(Snapshot).filter_by(source=SOURCE,lease_token=token).update(
            {'status':'ERROR','error_type':type(error).__name__,'lease_token':None,'lease_until':None},synchronize_session=False)
        db.commit();raise

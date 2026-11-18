"""Verified rgxm-mmea adapter: orders, never open quotation events.

No reliable business update timestamp exists. Reconcile by the official text ID,
not fecha/fecha_vence nor the timestamp of SECOP. Do not parse `items` by ';':
the actual descriptions contain that punctuation within individual products.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import time

import httpx

from app.core.config import get_settings
from app.services.match_versions import digest
from app.services.secop_client import SocrataClient, _parse_date

DATASET = 'rgxm-mmea'
SOURCE_URL = 'https://www.datos.gov.co/Gastos-Gubernamentales/Tienda-Virtual-del-Estado-Colombiano-Consolidado/rgxm-mmea'
CONTRACT = json.loads((Path(__file__).parents[1]/'data/tvec_schema_verified.json').read_text())
EXPECTED = {c['fieldName']: c['dataTypeName'] for c in CONTRACT['columns']}


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def validate_metadata(payload):
    if payload.get('id') != DATASET:
        raise ValueError('Unexpected TVEC dataset')
    columns = {c['fieldName']:c['dataTypeName'] for c in payload['columns'] if not c['fieldName'].startswith(':')}
    if columns != EXPECTED:
        raise ValueError('TVEC schema drift; mapping requires review')
    return columns


class TvecClient(SocrataClient):
    def __init__(self):
        super().__init__(domain='www.datos.gov.co')
        self.page_size = get_settings().tvec_page_size

    def request(self, path, params=None):
        for attempt in range(4):
            try:
                response = httpx.get('https://www.datos.gov.co/'+path, params=params,
                                     headers=self._headers(), timeout=10)
                if response.status_code in {429,502,503,504} and attempt < 3:
                    time.sleep(2**attempt); continue
                response.raise_for_status()
                return response.json()
            except (httpx.NetworkError,httpx.TimeoutException):
                if attempt == 3: raise
                time.sleep(2**attempt)

    def metadata(self):
        payload = self.request('api/views/'+DATASET+'.json')
        validate_metadata(payload)
        return payload

    def count(self):
        row = self.request('resource/'+DATASET+'.json', {
            '$select':'count(*) as total,count(distinct identificador_de_la_orden) as orders'})[0]
        if int(row['total']) != int(row['orders']):
            raise ValueError('TVEC unit changed: repeated or missing order IDs require review')
        return int(row['total'])

    def page(self, after=None):
        selected=','.join(k for k in EXPECTED if k!='solicitante')+', :id AS source_row_id'
        params = {'$select':selected, '$order':'identificador_de_la_orden ASC', '$limit':self.page_size}
        if after is not None:
            params['$where'] = "identificador_de_la_orden > '"+after.replace("'", "''")+"'"
        rows = self.request('resource/'+DATASET+'.json',params)
        if not isinstance(rows,list) or len(rows)>self.page_size:
            raise ValueError('Invalid TVEC page')
        return rows


def normalize(raw):
    official = raw.get('identificador_de_la_orden')
    if not isinstance(official,str) or not official.strip() or len(official)>255:
        raise ValueError('Official order ID missing')
    row_id = raw.get('source_row_id')
    if not isinstance(row_id,str) or not row_id or len(row_id)>255:
        raise ValueError('Socrata row provenance missing')
    # Data minimisation: never retain the requesting person's name.
    payload = {k:v for k,v in raw.items() if k in EXPECTED and k != 'solicitante'}
    amount = None
    if raw.get('total') not in (None,''):
        try:
            amount = Decimal(str(raw['total']))
            if not amount.is_finite() or abs(amount)>=Decimal('1e24') or amount.as_tuple().exponent < -6:
                raise ValueError('Unsupported source amount precision')
        except InvalidOperation as exc: raise ValueError('Invalid TVEC amount') from exc
    dates = {}
    for target,field in [('issued_at','fecha'),('expires_at','fecha_vence'),('initial_request_at','fecha_creacion_solicitud_inicial')]:
        dates[target] = _parse_date(raw.get(field))
        if raw.get(field) and dates[target] is None: raise ValueError('Invalid TVEC date')
    return dict(official_id=official, source_row_id=row_id, buyer=raw.get('entidad'),buyer_nit=raw.get('nit_entidad'),
        supplier=raw.get('proveedor'),supplier_nit=raw.get('nit_proveedor'), description=raw.get('items'),
        instrument=raw.get('agregacion'),category=raw.get('actividad_economica_proveedor'),department=raw.get('departamento'),
        city=raw.get('ciudad'),amount=amount,currency=None,status=raw.get('estado'),official_url=None,
        raw_json=payload,version=digest(payload),**dates)

"""Real Chromium/Next UI, API mocked, exclusively fictional records.

Runs a production frontend build already present, never a shared service or DB.
"""
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
from urllib.parse import urlparse,parse_qs

ROOT=Path(__file__).resolve().parents[2]


async def main():
    from playwright.async_api import async_playwright,expect
    out=Path(tempfile.mkdtemp(prefix='mysecop-tvec-e2e-'))
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    server=subprocess.Popen(['npm','run','start','--','--hostname','127.0.0.1','--port',str(port)],cwd=ROOT/'frontend',start_new_session=True,stdout=open(out/'next.log','w'),stderr=subprocess.STDOUT)
    orders=[]
    for i in range(45):
        orders.append(dict(id=i+1,official_id=f'SYN-{100+i}',buyer=f'Entidad sintética {i%3}',supplier=f'Proveedor sintético {i%4}',
            description='Compra sintética de software; no convocatoria abierta.',instrument=f'Instrumento ficticio {i%2}',category='Actividad sintética',
            department='Meta' if i%2==0 else 'Cundinamarca',city='Ciudad de prueba',amount='100.000000',currency=None,issued_at='2025-02-15T00:00:00',
            expires_at='2027-01-01T00:00:00',status='Emitido',synced_at='2026-11-16T00:00:00',version='fixture',
            source_url='https://www.datos.gov.co/Gastos-Gubernamentales/Tienda-Virtual-del-Estado-Colombiano-Consolidado/rgxm-mmea',official_url=None))
    provenance=dict(source_updated_at='2026-10-28T08:58:07',last_complete_at=None,local_orders=45,source_count_at_check=169444,
                    coverage_note='Muestra sintética parcial',currency_note='Moneda no informada')
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            for _ in range(120):
                if server.poll() is not None:raise RuntimeError('Next exited')
                try:
                    if (await client.get(origin,timeout=1)).status_code==200:break
                except Exception:pass
                await asyncio.sleep(.2)
            else:raise RuntimeError('Next timeout')
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(headless=True)
            for width,height in [(390,844),(768,1024),(1440,900),(320,760)]:
                context=await browser.new_context(viewport={'width':width,'height':height})
                await context.add_init_script("localStorage.setItem('licitaia_token','synthetic-token');")
                page=await context.new_page();errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
                state={'mode':'normal'}
                async def route_api(route):
                    parsed=urlparse(route.request.url);path=parsed.path;params={k:v[0] for k,v in parse_qs(parsed.query).items()}
                    body={};status=200
                    if '/api/tvec/' in path:
                        if state['mode']=='loading':await asyncio.sleep(1.5)
                        if state['mode']=='error':await route.fulfill(status=500,json={'detail':'Fuente de prueba no disponible'});return
                        data=orders
                        q=params.get('q','').lower()
                        if q:data=[o for o in data if q in (o['description']+' '+o['official_id']).lower()]
                        for key in ['department','buyer','supplier','instrument','category','city','status']:
                            if params.get(key):data=[o for o in data if o[key]==params[key]]
                        if path.endswith('/summary'):body=dict(orders=len(data),orders_with_value=len(data),buyers=len({o['buyer'] for o in data}),suppliers=len({o['supplier'] for o in data}),periods=[{'period':'2025-02','orders':len(data)}] if data else [],provenance=provenance)
                        elif '/orders/' in path:body={'order':next(o for o in orders if o['id']==int(path.rsplit('/',1)[1])),'provenance':provenance}
                        elif path.endswith('/orders'):body={'items':data[int(params.get('offset',0)):int(params.get('offset',0))+20],'total':len(data),'provenance':provenance}
                        else:
                            column={'buyers':'buyer','suppliers':'supplier','instruments':'instrument'}[path.rsplit('/',1)[1]]
                            counts=Counter(o[column] for o in data)
                            body={'items':[dict(name=k,orders=n,buyers=3,suppliers=4,categories=1,first_order='2025-02-15',last_order='2025-02-15') for k,n in counts.items()],'total':len(counts),'provenance':provenance}
                    elif path.endswith('/auth/me'):body={'id':1,'email':'synthetic@example.com','full_name':'QA sintética','role':'owner'}
                    elif path.endswith('/billing'):body={'nombre':'Plan sintético','es_pro':True,'status':'activa'}
                    elif path.endswith('/matches/coverage'):body={'candidate_total':1,'current_scores':1,'pending_scores':0,'stale_scores':0,'failed_scores':0,'excluded_total':0,'coverage_percent':100}
                    elif path.endswith('/match-jobs/current'):body=None
                    elif path.endswith('/opportunities/last-search'):body={'search':None}
                    elif path.endswith('/opportunities'):body={'total':1,'items':[{'id':999,'source':'secop2_procesos','source_id':'SECOP-FICTION','objeto':'Proceso SECOP sintético','entidad':'Entidad ficticia','estado':'Publicado','score':81,'score_state':'CURRENT','reasons':[],'valor':100,'vigencia':{'status':'UNKNOWN'},'triage':'detectada'}],'profile_configured':True}
                    await route.fulfill(status=status,json=body,headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'})
                await page.route('**/api/**',route_api)
                async def capture(name):
                    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),name
                    await page.evaluate("document.documentElement.style.scrollBehavior='auto'")
                    if name=='detalle':
                        await page.locator('.surface-card').last.screenshot(path=str(out/f'{width}-{name}.png'))
                    elif name=='filtros':
                        await page.locator('details').last.screenshot(path=str(out/f'{width}-{name}.png'))
                    else:
                        group=page.get_by_role('group',name='Fuente de información')
                        if await group.count():await group.evaluate("e=>e.scrollIntoView({block:'start',behavior:'instant'})")
                        await page.screenshot(path=str(out/f'{width}-{name}.png'),full_page=False)
                    if name=='todas' and width==1440:
                        await page.screenshot(path=str(out/f'{width}-{name}-full.png'),full_page=True)
                await page.goto(origin+'/app/oportunidades');await expect(page.get_by_text('Proceso SECOP sintético',exact=True)).to_be_visible()
                await capture('secop')
                await page.get_by_role('button',name='Todas',exact=True).click();await expect(page.get_by_role('heading',name='Orden SYN-100',exact=True)).to_be_visible();await capture('todas')
                await page.get_by_role('button',name='Tienda Virtual',exact=True).click();await expect(page.get_by_role('button',name='Tienda Virtual',exact=True)).to_have_attribute('aria-pressed','true');await expect(page.get_by_text('Proceso SECOP sintético',exact=True)).not_to_be_visible();await capture('tvec')
                await page.get_by_text('Filtros TVEC',exact=True).focus();await page.keyboard.press('Enter');await expect(page.get_by_label('Departamento (nombre exacto)',exact=True)).to_be_visible();await capture('filtros')
                await page.get_by_label('Departamento (nombre exacto)',exact=True).fill('Meta');await page.get_by_role('button',name='Aplicar filtros TVEC',exact=True).click()
                await expect(page.get_by_text('23 resultados · Página 1 de 2',exact=True)).to_be_visible();await capture('filtrada')
                await page.get_by_role('button',name='Siguiente TVEC',exact=True).click();await expect(page.get_by_text('23 resultados · Página 2 de 2',exact=True)).to_be_visible()
                saved=page.url;await page.get_by_role('link',name='Orden SYN-140',exact=True).click();await page.wait_for_url('**/app/tienda-virtual/**');await expect(page.get_by_role('heading',name='Orden SYN-140',exact=True,level=1)).to_be_visible();await capture('detalle')
                await page.get_by_role('link',name='← Volver a compras y fuentes',exact=True).click();await expect(page.get_by_text('23 resultados · Página 2 de 2',exact=True)).to_be_visible();assert 'tv_department=Meta' in page.url
                await page.reload();await expect(page.get_by_text('23 resultados · Página 2 de 2',exact=True)).to_be_visible()
                await page.get_by_role('button',name='Compradores',exact=True).click();await expect(page.get_by_role('heading',name='Entidad sintética 0',exact=True)).to_be_visible();await capture('compradores')
                for button in ['Proveedores','Instrumentos','Periodos','Órdenes']:
                    await page.get_by_role('button',name=button,exact=True).click();await page.wait_for_timeout(100)
                await page.get_by_label('Buscar compras TVEC',exact=True).fill('NO_RESULTS');await page.get_by_role('button',name='Buscar compras',exact=True).click();await expect(page.get_by_text('No hay compras que coincidan con estos filtros',exact=True)).to_be_visible();assert 'tv_q=NO_RESULTS' in page.url;await capture('vacio')
                state['mode']='loading';await page.get_by_label('Buscar compras TVEC',exact=True).fill('');await page.get_by_role('button',name='Buscar compras',exact=True).click();await expect(page.get_by_text('Consultando compras TVEC…',exact=True)).to_be_visible();await capture('carga');await expect(page.get_by_text('Consultando compras TVEC…',exact=True)).not_to_be_visible(timeout=15000)
                state['mode']='error';await page.get_by_role('button',name='Buscar compras',exact=True).click();await expect(page.get_by_role('alert')).to_be_visible();await capture('error')
                state['mode']='normal';await page.get_by_role('button',name='Reintentar consulta',exact=True).click();await expect(page.get_by_role('heading',name='Orden SYN-100',exact=True)).to_be_visible()
                if width==390:
                    await page.evaluate("document.documentElement.classList.add('dark')")
                    await capture('oscuro')
                assert not errors,errors
                await context.close()
            await browser.close()
        print('TVEC_E2E_PASSED',out,flush=True)
    finally:
        os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=20)

if __name__=='__main__':asyncio.run(main())

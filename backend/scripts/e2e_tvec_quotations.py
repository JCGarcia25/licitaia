"""Real Chromium/Next, synthetic API; isolated local production frontend only."""
import asyncio,json,re,subprocess,os,signal,time,socket,tempfile
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.async_api import async_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(tempfile.mkdtemp(prefix='mysecop-quotations-ui-'))
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
ORIGIN=f'http://127.0.0.1:{port}'
async def main():
 server=subprocess.Popen(['npm','run','start','--','-p',str(port)],cwd=ROOT/'frontend',start_new_session=True,stdout=open(OUT/'next.log','w'),stderr=subprocess.STDOUT)
 try:
  import httpx
  async with httpx.AsyncClient() as client:
   for _ in range(60):
    try:
     if (await client.get(ORIGIN,timeout=1)).status_code==200:break
    except Exception:pass
    await asyncio.sleep(.2)
   else:raise RuntimeError('Next QA server unavailable')
  async with async_playwright() as p:
   browser=await p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'),headless=True)
   for width,height in [(320,760),(390,844),(768,1024),(1440,900)]:
    context=await browser.new_context(viewport={'width':width,'height':height});await context.add_init_script("localStorage.setItem('licitaia_token','synthetic-token')")
    page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));state={'mode':'normal','refresh':'IDLE','posts':0,'reads':0}
    async def route(route):
     parsed=urlparse(route.request.url);path=parsed.path;params=parse_qs(parsed.query);body={}
     if path.endswith('/quotations/refresh'):
      state['posts']+=1;state['refresh']='PENDING'
      body={'state':'PENDING','accepted':True,'pages':0,'total_pages':47,'retry_after':300,'last_updated':None}
     elif path.endswith('/quotations/refresh-status'):
      await asyncio.sleep(.25)
      value='RUNNING' if state['mode']=='progress' else state['refresh']
      body={'state':value,'pages':2,'total_pages':47,'retry_after':300 if value=='COOLDOWN' else 0,'last_updated':'2026-11-17T14:00:00Z'}
     elif path.endswith('/quotations'):
      state['reads']+=1
      if state['mode']=='error':await route.fulfill(status=503,json={'detail':'Fallo sintético de consulta'});return
      if state['mode']=='loading':await asyncio.sleep(1)
      items=[dict(official_id='SYN-1',title='RFQ - Servicios sintéticos',buyer='Entidad de prueba',instrument='Instrumento ficticio',opens_at='2026-11-17T13:00:00Z',closes_at='2027-01-01T22:00:00Z',official_url='https://operaciones.colombiacompra.gov.co/detalle-cotizacion/900001',eligibility_note='Verifica la habilitación de tu empresa.',checked_at='2026-11-17T14:00:00Z')]
      if state['refresh']=='COOLDOWN':
       for item in items:item['title']+=' · actualizados'
      if params.get('q',[''])[0]=='NONE':items=[]
      body=dict(items=items,total=len(items),provenance=dict(checked_at='2026-11-17T14:00:00Z',freshness='REFRESH_PENDING' if state['mode']=='stale' else 'RECENT_PUBLIC_SNAPSHOT',refresh_status='IDLE',scanned_rows=33,scanned_pages=3,coverage='OFFICIAL_LISTING_TRAVERSED',scan_progress={'pages':3,'total_pages':3,'complete':True},excluded_rfi=6,excluded_unknown=16,notice='Publicación con actualización diferida. Confirma en TVEC.',type_evidence='RFQ explícita en título y detalle coincidente.'))
      if state['mode']=='progress':
       body['provenance']['coverage']='BOUNDED_RECENT_PAGES_NOT_EXHAUSTIVE';body['provenance']['scan_progress']={'pages':2,'total_pages':47,'complete':False}
     elif path.endswith('/auth/me'):body={'id':1,'email':'synthetic@example.com','role':'owner','full_name':'QA'}
     elif path.endswith('/billing'):body={'nombre':'QA','es_pro':True,'status':'activa'}
     elif path.endswith('/match-jobs/current'):body=None
     elif path.endswith('/matches/coverage'):body={'candidate_total':0,'current_scores':0,'pending_scores':0,'stale_scores':0,'failed_scores':0,'excluded_total':0,'coverage_percent':0}
     elif path.endswith('/summary'):body={'orders':0,'orders_with_value':0,'buyers':0,'suppliers':0,'periods':[],'provenance':{'source_updated_at':None,'last_complete_at':None,'local_orders':0,'source_count_at_check':None}}
     elif '/api/tvec/' in path:body={'items':[],'total':0,'provenance':{}}
     await route.fulfill(status=200,json=body,headers={'Access-Control-Allow-Origin':'*'})
    await page.route('**/api/**',route)
    await page.goto(ORIGIN+'/app/oportunidades?fuente=tvec')
    await expect(page.get_by_role('heading',name='Cotizaciones TVEC vigentes',exact=True)).to_be_visible()
    await expect(page.get_by_role('heading',name='RFQ - Servicios sintéticos')).to_be_visible()
    await expect(page.get_by_text('Elegibilidad pendiente',exact=True)).to_be_visible()
    await page.get_by_label('Buscar cotizaciones TVEC').fill('Servicios')
    await page.get_by_role('button',name='Buscar cotizaciones',exact=True).click()
    await expect(page.get_by_role('heading',name='RFQ - Servicios sintéticos')).to_be_visible()
    before=state['reads']
    await page.get_by_role('button',name='Actualizar cotizaciones TVEC',exact=True).click()
    await expect(page.get_by_role('button',name='Actualización en curso',exact=True)).to_be_disabled()
    assert state['posts']==1
    state['refresh']='RUNNING'
    await expect(page.get_by_text(re.compile('Recorrido en curso: 2 de 47'))).to_be_visible(timeout=10000)
    await expect(page.get_by_role('status',name='Estamos trabajando…',exact=True)).not_to_be_visible()
    state['refresh']='COOLDOWN'
    await expect(page.get_by_text(re.compile('Podrás solicitar otra actualización en'))).to_be_visible(timeout=10000)
    await expect(page.get_by_role('button',name='Actualizar cotizaciones TVEC',exact=True)).to_be_disabled()
    await expect(page.get_by_label('Buscar cotizaciones TVEC')).to_have_value('Servicios')
    await expect(page.get_by_role('heading',name='RFQ - Servicios sintéticos · actualizados',exact=True)).to_be_visible()
    assert state['reads']>before

    await expect(page.get_by_text(re.compile('Recorrido completo del listado oficial'))).to_be_visible()
    assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    await page.screenshot(path=str(OUT/f'{width}-quotations.png'),full_page=True)
    await page.get_by_label('Buscar cotizaciones TVEC').fill('NONE');await page.get_by_role('button',name='Buscar cotizaciones',exact=True).click()
    await expect(page.get_by_text('No hay cotizaciones verificadas con estos filtros',exact=True)).to_be_visible()
    await page.reload();await expect(page.get_by_label('Buscar cotizaciones TVEC')).to_have_value('NONE')
    await page.get_by_role('button',name=re.compile('Inteligencia de mercado')).click()
    await expect(page.get_by_role('heading',name='Compras registradas en la Tienda Virtual del Estado Colombiano')).to_be_visible()
    await page.get_by_role('button',name=re.compile('Cotizaciones vigentes')).click()
    await expect(page.get_by_role('heading',name='Cotizaciones TVEC vigentes',exact=True)).to_be_visible()
    await expect(page.get_by_label('Buscar cotizaciones TVEC')).to_have_value('NONE')
    await page.get_by_label('Buscar cotizaciones TVEC').fill('');await page.get_by_role('button',name='Buscar cotizaciones',exact=True).click()
    await expect(page.get_by_role('heading',name='RFQ - Servicios sintéticos')).to_be_visible()
    state['mode']='error';await page.get_by_role('button',name='Buscar cotizaciones',exact=True).click();await expect(page.get_by_role('button',name='Reintentar cotizaciones',exact=True)).to_be_visible()
    state['mode']='normal';await page.get_by_role('button',name='Reintentar cotizaciones',exact=True).click();await expect(page.get_by_role('heading',name='RFQ - Servicios sintéticos')).to_be_visible()
    state['mode']='progress';await page.reload();await page.get_by_role('button',name='Buscar cotizaciones',exact=True).click();await expect(page.get_by_text(re.compile('Recorrido en curso: 2 de 47'))).to_be_visible()
    state['mode']='stale';await page.get_by_role('button',name='Buscar cotizaciones',exact=True).click();await expect(page.get_by_text(re.compile('Actualización pendiente:'))).to_be_visible()
    assert not errors,errors
    await context.close()
   await browser.close()
  print(json.dumps({'status':'QUOTATIONS_UI_PASSED','widths':[320,390,768,1440],'api':'mocked synthetic','browser':'real Chrome','screenshots':str(OUT)}))
 finally:
  os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=20)
asyncio.run(main())

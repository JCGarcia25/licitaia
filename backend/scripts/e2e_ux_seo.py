"""Local production Next/Chrome: synthetic private API, no real accounts or sends.
Run after npm run build. Saves screenshots, axe findings and viewport evidence.
"""
import asyncio,json,os,signal,socket,subprocess,tempfile
from html.parser import HTMLParser

class Head(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.metas=[];self.headings=0;self.in_title=False;self.title=""
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=="link":self.links.append(a)
  if tag=="meta":self.metas.append(a)
  if tag=="h1":self.headings+=1
  if tag=="title":self.in_title=True
 def handle_endtag(self,tag):
  if tag=="title":self.in_title=False
 def handle_data(self,data):
  if self.in_title:self.title+=data

from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright,expect
import httpx
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.environ.get('UX_SEO_EVIDENCE',tempfile.mkdtemp(prefix='mysecop-ux-seo-')));OUT.mkdir(parents=True,exist_ok=True)
NOW='2026-11-18T15:00:00Z'
LONG='Suministro de elementos de cafetería, aseo y mantenimiento para las sedes administrativas de la entidad territorial'
OPP=dict(id=1,source='secop2',source_id='QA-1',entidad='Entidad pública de prueba con nombre extenso',objeto=LONG,descripcion=LONG,modalidad='Licitación Pública',valor=500000000,estado='Publicado',departamento='Bogotá D.C.',fecha_publicacion=NOW,fecha_cierre='2027-01-20T22:00:00Z',url_oficial='https://example.com/expediente',score=72,score_state='CURRENT',triage='guardada',is_saved=True,reasons=[dict(factor='Objeto',detalle='Coincidencias con productos y servicios del perfil empresarial de prueba.',evidencia='QA')],analysis=None,cancelled=False,documentos_publicos_disponibles=0)
PROJECT=dict(id=1,name='Propuesta — '+LONG,opportunity_id=1,status='en_revision',version=2,updated_at=NOW,pendientes=3,is_saved=True,url_oficial='https://example.com/expediente')
DETAIL={**PROJECT,'approved_by':'','opportunity':OPP,'checklist':[dict(item='Certificado de existencia y representación legal de la empresa',tipo='jurídico',estado='pendiente',evidencia=''),dict(item='Propuesta técnica con descripción de las especificaciones del servicio',tipo='técnico',estado='listo',evidencia='')],'cronograma':[dict(tarea='Revisión jurídica y aprobación por la persona autorizada',plazo='20/01/2027',estimado=False,estado='pendiente')],'borradores':[dict(tipo='carta_presentacion',contenido=LONG+'\n'+('ReferenciaLargaSinEspacios'*12),version=2,fecha=NOW)],'comentarios':[dict(autor='Persona QA',texto=LONG,fecha=NOW)]}
ORDER=dict(id=1,official_id='QA-100',buyer=OPP['entidad'],supplier='Proveedor de prueba',description=LONG,instrument='Acuerdo Marco de Precios',category='Servicios',department='Bogotá D.C.',city='Bogotá',amount='50000000.00',currency=None,issued_at=NOW,expires_at=None,status='Emitida',synced_at=NOW,version='QA',source_url='https://example.com',official_url=None)
PROV=dict(source_updated_at=NOW,last_complete_at=NOW,local_orders=1,source_count_at_check=1,coverage_note='Muestra sintética',currency_note='Moneda no informada')
PUBLIC=['/','/contacto','/iniciar-sesion','/registro','/restablecer-contrasena','/verificar-correo','/legal/terminos-y-condiciones','/legal/politica-de-privacidad','/legal/tratamiento-de-datos']
PRIVATE=['/app','/app/oportunidades?fuente=secop&q=aseo','/app/oportunidades/1','/app/ofertas?oferta=1','/app/alertas','/app/perfil','/app/plan','/app/sincronizacion','/app/manuales','/app/ayuda','/app/licencia-comercial','/app/admin','/app/oportunidades?fuente=tvec','/app/oportunidades?fuente=tvec&tv_section=history','/app/tienda-virtual/1','/app/diagnostico-compatibilidad','/app/evaluacion-interna']
async def main():
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 origin=f'http://127.0.0.1:{port}'
 server=subprocess.Popen(['npm','run','start','--','-H','127.0.0.1','-p',str(port)],cwd=ROOT/'frontend',start_new_session=True,stdout=open(OUT/'next.log','w'),stderr=subprocess.STDOUT)
 results=[];unknown=set();seo=[]
 async def route(r):
  path=urlparse(r.request.url).path;body={}
  if path=='/api/auth/me':body=dict(id=1,email='jorge@zorbagames.com',full_name='Persona QA sintética',role='admin',email_verified=True)
  elif path=='/api/billing':
   free=r.request.headers.get('x-qa-plan')=='free';body=dict(plan='explorador' if free else 'profesional',nombre='MySECOP Free' if free else 'MySECOP Pro',es_pro=not free,status='activa',usage=dict(used=0,limit=20))
  elif path=='/api/dashboard/metrics':body={**dict.fromkeys(['oportunidades_detectadas','procesos_nuevos_base','proximos_a_cerrar','alta_compatibilidad','valor_agregado_cop','guardadas','descartadas','proyectos_propuesta','documentos_pendientes','ofertas_activas','alertas_no_leidas'],1),'umbral_compatibilidad':50,'tendencia_mensual':[dict(mes='2026-11',total=1)]}
  elif path=='/api/profile':body=None
  elif path=='/api/alerts/prefs':body=dict(email_enabled=False,email_to='synthetic@example.com',high_score_threshold=50,close_days=[10,5,1],digest_hour=7)
  elif path=='/api/alerts':body=[dict(id=1,tipo='cierre',title='Próximo cierre de '+LONG,body=LONG,opportunity_id=1,read_at=None,created_at=NOW)]
  elif path=='/api/opportunities/last-search':body=dict(search=None)
  elif path in ['/api/opportunities','/api/opportunities/search','/api/search']:body=dict(items=[OPP],total=26)
  elif path=='/api/opportunities/1':body=OPP
  elif path=='/api/documents':body=[]
  elif path=='/api/offer-projects':body=[PROJECT,{**PROJECT,'id':2,'name':'Otra oferta guardada'}]
  elif path=='/api/offer-projects/1':body=DETAIL
  elif path.endswith('/closing-reminder'):body=dict(can_schedule=False,can_cancel=False,reason='NO_CLOSING_DATE',message='No podemos programar este recordatorio porque no encontramos la fecha de cierre del proceso. Consulta el expediente en SECOP; podrás crear la alerta cuando la fecha esté disponible.',timezone='America/Bogota',closing_at=None,recipient='synthetic@example.com',reminder=None)
  elif path=='/api/match-jobs/current':body=None
  elif path=='/api/matches/coverage':body=dict(candidate_total=801,current_scores=801,pending_scores=0,stale_scores=0,failed_scores=0,excluded_total=21553,coverage_percent=100)
  elif path=='/api/sync/runs':body=[]
  elif path=='/api/sync/usage':body=dict(es_pro=True,used=0,limit=None)
  elif path=='/api/admin/overview':body=dict(generated_at=NOW,metrics={},usuarios_activos=[],usuarios=[dict(id=2,email='synthetic-with-a-long-name@example.com',nombre='Persona de prueba',ruta='/app/ofertas',ultimo_acceso=NOW,creado=NOW,activo=True,rol='lector',licencia=dict(plan='explorador',status='activa'))],eventos=[])
  elif path=='/api/tvec/summary':body=dict(orders=1,orders_with_value=1,buyers=1,suppliers=1,periods=[],provenance=PROV)
  elif path=='/api/tvec/orders':body=dict(items=[ORDER],total=1,provenance=PROV)
  elif path=='/api/tvec/orders/1':body=dict(order=ORDER)
  elif path=='/api/tvec/quotations':body=dict(items=[dict(official_id='QA-1',title='RFQ — '+LONG,buyer=OPP['entidad'],instrument='Acuerdo Marco',opens_at=NOW,closes_at='2027-01-20T22:00:00Z',official_url='https://example.com',eligibility_note='Verifica tu habilitación.',checked_at=NOW)],total=1,provenance=dict(checked_at=NOW,freshness='RECENT_PUBLIC_SNAPSHOT',refresh_status='IDLE',scanned_rows=1,scanned_pages=1,coverage='OFFICIAL_LISTING_TRAVERSED',scan_progress=dict(pages=1,total_pages=1,complete=True),excluded_rfi=0,excluded_unknown=0,notice='Muestra sintética',type_evidence='RFQ'))
  elif path.endswith('/quotations/refresh-status'):body=dict(state='IDLE',pages=1,total_pages=1,retry_after=0,last_updated=NOW)
  elif path.endswith('/assignments') or path.endswith('/runs'):body=[]
  elif path in ['/api/admin/presence','/api/admin/landing-visit','/api/analytics/visit','/api/analytics/heartbeat']:body={}
  else:unknown.add(path);await r.fulfill(status=404,json={'detail':'Ruta no cubierta por la muestra QA'});return
  await r.fulfill(status=200,json=body)
 try:
  async with httpx.AsyncClient() as c:
   for _ in range(100):
    try:
     if (await c.get(origin,timeout=1)).status_code==200:break
    except Exception:pass
    await asyncio.sleep(.2)
   else:raise RuntimeError('Local Next unavailable')
   for path in PUBLIC+['/app/ofertas','/robots.txt','/sitemap.xml','/opengraph-image']:
    response=await c.get(origin+path);assert response.status_code==200,(path,response.status_code)
    seo.append(dict(path=path,status=response.status_code,robots_header=response.headers.get('x-robots-tag')))
    if path in ['/', '/contacto']:
     head=Head();head.feed(response.text)
     assert [x['href'].rstrip('/') for x in head.links if x.get('rel')=='canonical']==[('https://mysecop.co'+path).rstrip('/')], (path, head.links)
     assert head.headings==1,(path,head.headings)
     assert head.title.count('MySECOP')==1,(path,head.title)
     assert any(x.get('name')=='description' and x.get('content') for x in head.metas)
     assert any(x.get('property')=='og:image' for x in head.metas)
     assert 'noindex' not in str([x for x in head.metas if x.get('name')=='robots'])
    if path in PUBLIC[2:]+['/app/ofertas']:
     assert response.headers.get('x-robots-tag')=='noindex, nofollow',path
   robots=(await c.get(origin+'/robots.txt')).text
   assert 'Disallow: /app' not in robots and 'Allow: /' in robots
   social=await c.get(origin+'/opengraph-image');assert social.headers.get('content-type','').startswith('image/png')
   (OUT/'social-preview.png').write_bytes(social.content)
   assert '/contacto' in (await c.get(origin+'/sitemap.xml')).text
   assert '/registro' not in (await c.get(origin+'/sitemap.xml')).text
  if os.environ.get('UX_SEO_HTTP_ONLY')=='1':
   print(json.dumps(dict(status='HTTP_ONLY_PASS',http=seo)));return
  async with async_playwright() as p:
   browser=await p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
   sem=asyncio.Semaphore(3)
   async def viewport(width,height,theme,free=False):
    async with sem:
     context=await browser.new_context(viewport=dict(width=width,height=height),color_scheme=theme,extra_http_headers={'X-QA-Plan':'free' if free else 'pro'})
     await context.add_init_script(f"localStorage.setItem('licitaia_token','synthetic-token');localStorage.setItem('licitaia-theme','{theme}')")
     await context.route('**/api/**',route)
     page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
     for idx,path in enumerate(['/app','/app/plan','/app/oportunidades?fuente=secop&q=aseo'] if free else PUBLIC+PRIVATE):
      await page.goto(origin+path,wait_until='networkidle');await page.locator('h1').first.wait_for(state='visible',timeout=10000)
      metrics=await page.evaluate('''()=>({overflow:document.documentElement.scrollWidth>innerWidth,wide:[...document.querySelectorAll('main button,main input,main select,main a')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.right>innerWidth+1||r.left< -1)&&!e.closest('.overflow-x-auto')}).map(e=>e.textContent?.slice(0,70)||e.getAttribute('aria-label')),canonical:document.querySelector('link[rel=canonical]')?.href,robots:document.querySelector('meta[name=robots]')?.content,nested:document.querySelectorAll('a button').length})''')
      await page.add_script_tag(path=os.environ.get('AXE_CORE_PATH','/private/tmp/mysecop-offer-axe/node_modules/axe-core/axe.min.js'))
      axe=await page.evaluate("async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))}")
      if not free and width in [320,768,1024,1440] and path in ['/','/app/ofertas?oferta=1','/app/oportunidades?fuente=secop&q=aseo','/app/admin']:
       await page.evaluate('window.scrollTo(0,0)');await page.screenshot(path=str(OUT/f'{width}-{theme}-{idx}.png'),full_page=True)
      results.append(dict(width=width,height=height,theme=theme,plan='free' if free else 'pro',path=path,**metrics,axe=axe,errors=list(errors)));errors.clear()
      (OUT/'progress.json').write_text(json.dumps(results,ensure_ascii=False))
      if path=='/contacto':assert metrics['canonical']=='https://mysecop.co/contacto',metrics
      if path.startswith('/app') or path in PUBLIC[2:]:assert 'noindex' in (metrics['robots'] or ''),(path,metrics)
      if path=='/app/ofertas?oferta=1':
       await page.get_by_role('button',name='Recordatorio de cierre',exact=True).first.click();await expect(page.get_by_role('dialog',name='Recordatorio de cierre por correo',exact=True)).to_be_visible();await page.keyboard.press('Escape')
      if path=='/app' and width<1024:
       await page.get_by_role('button',name='Menú',exact=True).click();await expect(page.get_by_role('dialog',name='MySECOP',exact=True)).to_be_visible();await page.keyboard.press('Escape');await expect(page.get_by_role('button',name='Menú',exact=True)).to_be_focused()
     print(json.dumps(dict(viewport=width,theme=theme,status='complete')),flush=True)
     await context.close()
   await asyncio.gather(*(viewport(w,h,t) for w,h in [(320,760),(390,844),(640,900),(768,1024),(820,1180),(1024,768),(1280,800),(1440,900),(1920,1080),(2560,1440),(844,390)] for t in ['light','dark']))
   await asyncio.gather(*(viewport(w,h,t,True) for w,h in [(320,760),(768,1024),(1024,768)] for t in ['light','dark']))
   await browser.close()
 finally:
  (OUT/'results.json').write_text(json.dumps(dict(pages=results,http=seo,unknown_api=sorted(unknown)),ensure_ascii=False,indent=2))
  os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=20)
 failures=[r for r in results if r['overflow'] or r['wide'] or r['errors'] or r['axe'] or r['nested']]
 print(json.dumps(dict(evidence=str(OUT),pages=len(results),failures=len(failures),axe=sorted(set(v['id'] for r in results for v in r['axe'])),unknown_api=sorted(unknown))))
 assert not unknown,sorted(unknown)
 assert not failures,[(r['width'],r['path'],r['wide'],r['errors'],r['axe']) for r in failures]
asyncio.run(main())

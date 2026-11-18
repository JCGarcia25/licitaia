"""Real local Next/API with disposable SQLite and synthetic users, no email sends."""
import asyncio,json,os,signal,socket,subprocess,sys,tempfile,re
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(tempfile.mkdtemp(prefix='mysecop-offer-reminder-ui-'))
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(ENVIRONMENT='testing',DATABASE_URL='sqlite:///'+str(OUT/'db.sqlite'),SECRET_KEY='synthetic-qa-secret-with-32-characters',ALLOW_DEMO_SEED='false',SMTP_HOST='synthetic.invalid',SMTP_USER='',SMTP_PASSWORD='',LLM_PROVIDER='heuristic',EMBEDDING_PROVIDER='fake',STORAGE_DIR=str(OUT/'storage'))
from app.db.session import init_db,SessionLocal
from app.db.models import User,Opportunity,OfferProject,Subscription
from app.core.security import hash_password
init_db()
with SessionLocal() as db:
    u=User(email='offer-e2e@example.com',hashed_password=hash_password('SyntheticQa2026!'),email_verified=True,is_active=True);db.add(u);db.flush()
    db.add(Subscription(user_id=u.id,plan='profesional',status='activa',provider='test'))
    for i in range(3):
        o=Opportunity(source='qa',source_id=f'offer-e2e-{i}',objeto=f'Recordatorioqa proceso {i}',entidad='Entidad QA',estado='Publicado',fecha_cierre=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(days=3) if i!=1 else None,cancelled=False);db.add(o);db.flush()
        if i<2:db.add(OfferProject(user_id=u.id,opportunity_id=o.id,name='Oferta QA con cierre' if i==0 else 'Oferta QA sin cierre',status='activo'))
    db.commit()
def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
async def main():
    ap,wp=port(),port();origin=f'http://127.0.0.1:{wp}';api=f'http://127.0.0.1:{ap}';processes=[];results=[]
    try:
        env={**os.environ,'CORS_ORIGINS':origin,'NEXT_PUBLIC_API_URL':api}
        processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(ap)],cwd=ROOT/'backend',env=env,start_new_session=True,stdout=open(OUT/'api.log','w'),stderr=subprocess.STDOUT))
        processes.append(subprocess.Popen(['node','node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1','--port',str(wp)],cwd=ROOT/'frontend',env=env,start_new_session=True,stdout=open(OUT/'frontend.log','w'),stderr=subprocess.STDOUT))
        import httpx
        async with httpx.AsyncClient() as c:
            for _ in range(150):
                try:
                    if (await c.get(api+'/health',timeout=1)).status_code==200 and (await c.get(origin+'/iniciar-sesion',timeout=2)).status_code==200:break
                except Exception:pass
                await asyncio.sleep(.2)
            else:raise RuntimeError('Local services unavailable')
        from playwright.async_api import async_playwright,expect
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'),headless=True)
            for width,height,theme in [(w,h,t) for w,h in [(320,760),(390,844),(768,1024),(1440,900)] for t in ["light","dark"]]:
                ctx=await browser.new_context(viewport={'width':width,'height':height},color_scheme=theme);page=await ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                await page.goto(origin+'/iniciar-sesion');await page.get_by_label('Correo electrónico',exact=True).fill('offer-e2e@example.com');await page.get_by_placeholder('••••••••',exact=True).fill('SyntheticQa2026!');await page.get_by_role('button',name='Ingresar',exact=True).click();await page.wait_for_url('**/app')
                await page.goto(origin+'/app/ofertas')
                def card(name):return page.locator('.surface-card').filter(has_text=name).filter(has=page.get_by_role('button',name='Recordatorio de cierre',exact=True))
                await card('Oferta QA con cierre').get_by_role('button',name='Recordatorio de cierre',exact=True).click()
                dialog=page.get_by_role('dialog',name='Recordatorio de cierre por correo',exact=True);await expect(dialog).to_be_visible();await expect(dialog.get_by_label('Fecha del recordatorio',exact=True)).to_be_visible()
                when=datetime.now(ZoneInfo('America/Bogota'))+timedelta(days=1);day=when.strftime('%Y-%m-%d')
                await dialog.get_by_label('Fecha del recordatorio',exact=True).fill(day);await dialog.get_by_label('Hora del recordatorio (Colombia)',exact=True).fill('09:30')
                submit=dialog.get_by_role('button',name=re.compile('Programar recordatorio|Actualizar recordatorio'))
                await submit.click();await expect(dialog.get_by_text('Recordatorio programado para el',exact=False)).to_be_visible()
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                await page.add_script_tag(path=os.environ.get('AXE_CORE_PATH','/private/tmp/mysecop-offer-axe/node_modules/axe-core/axe.min.js'))
                axe=await page.evaluate("async()=>{const r=await axe.run(document.querySelector('dialog[open]'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact}))}")
                assert not axe,axe
                await page.screenshot(path=str(OUT/f'{width}-{theme}-scheduled.png'),full_page=True)
                await page.keyboard.press('Escape');await expect(dialog).not_to_be_visible();await expect(card('Oferta QA con cierre').get_by_role('button',name='Recordatorio de cierre',exact=True)).to_be_focused()
                await page.reload();await card('Oferta QA con cierre').get_by_role('button',name='Recordatorio de cierre',exact=True).click();await expect(dialog.get_by_label('Hora del recordatorio (Colombia)',exact=True)).to_have_value('09:30')
                await dialog.get_by_role('button',name='Cancelar recordatorio',exact=True).click();await expect(dialog.get_by_text('Recordatorio cancelado.',exact=False)).to_be_visible();await dialog.get_by_role('button',name='Cerrar recordatorio').click()
                await card('Oferta QA sin cierre').get_by_role('button',name='Recordatorio de cierre',exact=True).click();await expect(dialog.get_by_text('no encontramos la fecha de cierre',exact=False)).to_be_visible();await expect(dialog.get_by_label('Fecha del recordatorio',exact=True)).to_have_count(0)
                await page.screenshot(path=str(OUT/f'{width}-{theme}-no-date.png'),full_page=True);await page.keyboard.press('Escape')
                save=card('Oferta QA con cierre').get_by_role('button',name='Guardar proceso',exact=True)
                if await save.count():
                    await save.click();await page.get_by_role('button',name='Continuar en MySECOP').click()
                await page.goto(origin+'/app/oportunidades?fuente=secop&q=recordatorioqa&solo_con_score=false&modo=busqueda')
                first=page.get_by_role('link',name='Recordatorioqa proceso 0',exact=True);await expect(first).to_be_visible()
                titles=await page.locator('a[href*="/app/oportunidades/"]').all_text_contents();assert titles[0]=='Recordatorioqa proceso 0',titles
                assert not errors,errors
                results.append({'width':width,'theme':theme,'status':'PASS','checks':['schedule','timezone','persist reload','cancel','no date popup','keyboard focus','saved first','no overflow','axe dialog']})
                (OUT/'results.json').write_text(json.dumps(results,indent=2));await ctx.close()
            await browser.close()
        print(json.dumps({'status':'PASS','api':'real local','records':'synthetic','smtp_sends':0,'results':results,'evidence':str(OUT)}))
    finally:
        for p in reversed(processes):
            if p.poll() is None:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=20)
asyncio.run(main())

"""E2E local: Next/FastAPI + PG/Redis/worker aislados, usuarios sintéticos."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'backend/tests'))
os.environ.update(ENVIRONMENT='isolated-integration',EMBEDDING_PROVIDER='fake',EMBEDDING_DIM='64',
    SECRET_KEY='isolated-test-key-with-32-characters',ALLOW_DEMO_SEED='false',LLM_PROVIDER='heuristic')
from pgserver import PostgresServer
import psycopg2


def port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def main():
    directory=Path(tempfile.mkdtemp(prefix='mysecop-e2e-'))
    print('E2E_EVIDENCE',directory,flush=True)
    api_port,web_port=port(),port()
    api_origin,web_origin=f'http://127.0.0.1:{api_port}',f'http://127.0.0.1:{web_port}'
    processes=[]
    v2_mode=os.environ.get('MYSECOP_E2E_V2')=='1'
    evaluation_mode=os.environ.get('MYSECOP_E2E_EVALUATION')=='1'
    if v2_mode:os.environ['COMPATIBILITY_V2_SHADOW_ENABLED']='true'
    with PostgresServer(directory/'pg',cleanup_mode='stop') as server:
        c=psycopg2.connect(server.get_uri());c.autocommit=True
        with c.cursor() as cursor:cursor.execute('CREATE DATABASE mysecop_test_e2e_phase13')
        c.close()
        url=server.get_uri('mysecop_test_e2e_phase13').replace('postgresql://','postgresql+psycopg2://')
        os.environ.update(DATABASE_URL=url,MYSECOP_TEST_POSTGRES_URL=url)
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.db.models import Base,User,CompanyProfile,Subscription,Opportunity
        from app.core.security import hash_password
        engine=create_engine(url);Base.metadata.create_all(engine);factory=sessionmaker(bind=engine)
        email='e2e-local@example.com';password='LocalQaOnly2026!'
        with factory() as db:
            user=User(email=email,hashed_password=hash_password(password),full_name='QA sintético',email_verified=True,role='admin' if (v2_mode or evaluation_mode) else 'owner')
            db.add(user);db.flush()
            db.add(CompanyProfile(user_id=user.id,sector='software',keywords=['software'],**({'departamentos':['Meta'],'presupuesto_min':1,'presupuesto_max':2000000} if v2_mode else {})))
            db.add(Subscription(user_id=user.id,plan='profesional',status='activa',provider='test'))
            db.add_all([Opportunity(source='qa',source_id=str(i),objeto=f'Software de prueba integral {i}',descripcion='Sistemas de software sintéticos',
                estado='En proceso',departamento='Meta',valor=1000000) for i in range(45)])
            db.commit()
        evaluation_reviewers=[]
        if evaluation_mode:
            with factory() as db:
                for i in range(3):
                    reviewer=User(email=f'reviewer-{i}@example.com',hashed_password=hash_password(password),full_name=f'QA reviewer {i}',email_verified=True,role='evaluation_reviewer')
                    db.add(reviewer);db.flush();evaluation_reviewers.append((reviewer.id,reviewer.email))
                db.commit()
        import redislite
        from test_redis_operations import Services,wait
        redisdir=Path(tempfile.mkdtemp(prefix='mysecop-test-redis-'))
        services=Services(redisdir,str(Path(redislite.__file__).parent/'bin/redis-server'),factory)
        import httpx
        try:
            evaluation_env={}
            if evaluation_mode or v2_mode:
                from app.core.config import get_settings
                from app.db.models import EvaluationEnvironmentIdentity
                from app.services.evaluation_guard import destination
                from app.services.match_versions import digest
                settings=get_settings();identity=str(uuid4())
                settings.evaluation_enabled=evaluation_mode;settings.evaluation_api_origin=api_origin;settings.redis_url=services.broker
                targets=[{'database':url,'broker':services.broker,'api_origin':api_origin,'identity':identity}]
                settings.evaluation_dev_targets=targets
                evaluation_env={'EVALUATION_ENABLED':'true' if evaluation_mode else 'false','EVALUATION_API_ORIGIN':api_origin,'EVALUATION_DEV_TARGETS':json.dumps(targets)}
                os.environ.update(evaluation_env)
                with factory() as db:db.add(EvaluationEnvironmentIdentity(id=identity,fingerprint=digest(destination(settings)),purpose='isolated-development'));db.commit()
            services.redis_start();services.worker_start(queues='matches,compatibility-shadow,evaluation' if (evaluation_mode and v2_mode) else ('matches,evaluation' if evaluation_mode else ('matches,compatibility-shadow' if v2_mode else 'matches')),extra_env=evaluation_env);services.flags(hold=True)
            env={**os.environ,'REDIS_URL':services.broker,'CORS_ORIGINS':web_origin,'STORAGE_DIR':str(directory/'storage')}
            backend=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(api_port)],cwd=ROOT/'backend',env=env,
                start_new_session=True,stdout=open(directory/'api.log','w'),stderr=subprocess.STDOUT);processes.append(backend)
            frontend=subprocess.Popen(['node','node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1','--port',str(web_port)],cwd=ROOT/'frontend',
                env={**os.environ,'NEXT_PUBLIC_API_URL':api_origin,'NEXT_TELEMETRY_DISABLED':'1'},start_new_session=True,
                stdout=open(directory/'frontend.log','w'),stderr=subprocess.STDOUT);processes.append(frontend)
            wait(lambda:httpx.get(api_origin+'/health',timeout=1).status_code==200,30)
            wait(lambda:httpx.get(web_origin+'/iniciar-sesion',timeout=2).status_code==200,60)
            from playwright.sync_api import sync_playwright,expect
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True)
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(web_origin+'/iniciar-sesion')
                page.get_by_label('Correo electrónico',exact=True).fill(email)
                page.get_by_placeholder('••••••••',exact=True).fill(password)
                page.get_by_role('button',name='Ingresar',exact=True).click()
                page.wait_for_url('**/app',timeout=30000)
                expect(page.get_by_text('Cobertura del Cazador',exact=True)).to_be_visible()
                expect(page.get_by_text('0 de 45 candidatas',exact=False)).to_be_visible()
                page.goto(web_origin+'/app/perfil')
                page.get_by_label('Actividades principales',exact=False).fill('software y sistemas integrales')
                page.get_by_role('button',name='Guardar perfil',exact=True).click()
                expect(page.get_by_text('Los cambios relevantes dejan recomendaciones pendientes',exact=False)).to_be_visible(timeout=15000)
                page.goto(web_origin+'/app/oportunidades')
                expect(page.get_by_role('button',name='Cancelar cálculo',exact=True)).to_be_visible(timeout=15000)
                page.get_by_role('button',name='Cancelar cálculo',exact=True).click()
                expect(page.get_by_role('button',name='Actualizar compatibilidad',exact=True)).to_be_visible()
                services.flags()
                page.get_by_role('button',name='Actualizar compatibilidad',exact=True).click()
                expect(page.get_by_text('45 de 45 candidatas',exact=False)).to_be_visible(timeout=30000)
                expect(page.get_by_role('link',name='Software de prueba integral 44',exact=True)).to_be_visible()
                page.screenshot(path=str(directory/'oportunidades.png'),full_page=True)
                # Revisión de stale real: el cálculo queda detenido fuera de DB.
                services.flags(hold=True)
                page.goto(web_origin+'/app/perfil')
                page.get_by_label('Actividades principales',exact=False).fill('software y sistemas actualizados')
                page.get_by_role('button',name='Guardar perfil',exact=True).click()
                expect(page.get_by_text('Los cambios relevantes dejan recomendaciones pendientes',exact=False)).to_be_visible()
                page.goto(web_origin+'/app/oportunidades?modo=busqueda&pagina=2&q=Software')
                expect(page.get_by_text('0 de 45 candidatas',exact=False)).to_be_visible()
                stale_row=page.get_by_role('link',name='Software de prueba integral 0',exact=True).locator('xpath=ancestor::div[contains(@class,"surface-card")][1]')
                expect(stale_row.get_by_text('Pendiente de actualización',exact=True)).to_be_visible()
                expect(stale_row.get_by_text('de compatibilidad estimada',exact=False)).not_to_be_visible()
                page.get_by_role('button',name='Cancelar cálculo',exact=True).click()
                services.flags()
                page.get_by_role('button',name='Actualizar compatibilidad',exact=True).click()
                expect(page.get_by_text('45 de 45 candidatas',exact=False)).to_be_visible(timeout=30000)

                # Filtro sin resultados conserva lo escrito.
                search=page.get_by_placeholder('Búsqueda: texto libre o en lenguaje natural',exact=False)
                search.fill('zzsinresultadoqa');page.get_by_role('button',name='Buscar',exact=True).click()
                expect(search).to_have_value('zzsinresultadoqa')
                search.fill('Software');page.get_by_role('button',name='Buscar',exact=True).click()
                # Guardar/descartar desde una página posterior conserva el score.
                from app.db.models import UserOpportunity
                with factory() as db:
                    uid=db.query(User.id).filter_by(email=email).scalar()
                    before={u.opportunity_id:u.score for u in db.query(UserOpportunity).filter(UserOpportunity.user_id==uid,UserOpportunity.opportunity_id.in_([1,2]))}
                page.goto(web_origin+'/app/oportunidades?modo=busqueda&pagina=2&q=Software')
                link=page.get_by_role('link',name='Software de prueba integral 0',exact=True)
                expect(link).to_be_visible()
                row=link.locator('xpath=ancestor::div[contains(@class,"surface-card")][1]')
                score_text=row.get_by_text('de compatibilidad estimada',exact=False).inner_text()
                row.get_by_role('button',name='Guardar',exact=True).click()
                expect(row.get_by_text('guardada',exact=True)).to_be_visible()
                expect(row.get_by_text(score_text,exact=True)).to_be_visible()
                other=page.get_by_role('link',name='Software de prueba integral 1',exact=True).locator('xpath=ancestor::div[contains(@class,"surface-card")][1]')
                other.get_by_role('button',name='Descartar',exact=True).click()
                expect(page.get_by_role('link',name='Software de prueba integral 1',exact=True)).not_to_be_visible()
                with factory() as db:
                    after={u.opportunity_id:u.score for u in db.query(UserOpportunity).filter(UserOpportunity.user_id==uid,UserOpportunity.opportunity_id.in_([1,2]))}
                    assert after==before
                page.goto(web_origin+'/app/oportunidades/1')
                expect(page.get_by_role('heading',name='Software de prueba integral 0',exact=True)).to_be_visible()
                page.get_by_role('button',name='Crear proyecto de propuesta (Agente 4)',exact=True).click()
                expect(page.get_by_text('Proyecto de oferta creado.',exact=False)).to_be_visible(timeout=15000)
                page.get_by_role('button',name='Continuar en MySECOP',exact=True).click()
                # Documento sintético para probar análisis completo.
                import docx
                doc=docx.Document();doc.add_paragraph('Software de prueba integral y sistemas de software sintéticos. Presupuesto oficial $1.000.000. Experiencia en software. Póliza de cumplimiento del 10%.')
                document=directory/'pliego-sintetico.docx';doc.save(document)
                page.locator('input[type=file]').set_input_files(str(document))
                page.get_by_role('button',name='Subir 1 documento(s)',exact=True).click()
                expect(page.get_by_text('1 documento(s) cargado(s) correctamente.',exact=True)).to_be_visible(timeout=15000)
                page.get_by_role('button',name='Continuar en MySECOP',exact=True).click()
                page.get_by_role('button',name='Analizar documentos',exact=True).click()
                expect(page.get_by_text('Sin análisis generado',exact=True)).not_to_be_visible(timeout=30000)
                page.goto(web_origin+'/app/ofertas')
                expect(page.get_by_text('Software de prueba integral 0',exact=False)).to_be_visible(timeout=15000)
                page.goto(web_origin+'/app/alertas')
                expect(page.get_by_role('heading',name='Alertas',exact=True)).to_be_visible()
                page.goto(web_origin+'/app')
                expect(page.get_by_text('de 45 candidatas',exact=False)).to_be_visible()
                expect(page.get_by_text('Buscando tus mejores oportunidades',exact=False)).not_to_be_visible(timeout=15000)
                page.screenshot(path=str(directory/'dashboard.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                page.goto(web_origin+'/app/oportunidades?modo=busqueda&pagina=2&q=Software')
                expect(page.get_by_role('link',name='Software de prueba integral 0',exact=True)).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(directory/'mobile.png'),full_page=True)
                page.goto(web_origin+'/app/diagnostico-compatibilidad')
                expect(page.get_by_role('heading',name='Diagnóstico privado de compatibilidad V2',exact=True)).to_be_visible()
                if v2_mode:
                    page.get_by_role('button',name='Evaluar muestra de hasta 10 oportunidades',exact=True).click()
                    expect(page.get_by_role('button',name='Actualizar resultado',exact=True)).to_be_visible()
                    from app.db.models import CompatibilityShadowRun,CompatibilityShadowResult
                    def shadow_done():
                        with factory() as db:return db.query(CompatibilityShadowRun).filter_by(user_id=uid,state='COMPLETED').count()==1
                    wait(shadow_done,30)
                    page.get_by_role('button',name='Actualizar resultado',exact=True).click()
                    expect(page.get_by_text('Estado: COMPLETED. Muestra histórica privada, 10/10.',exact=True)).to_be_visible()
                    assert page.get_by_role('table').count()==10
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    page.screenshot(path=str(directory/'v2-mobile.png'),full_page=False)
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.screenshot(path=str(directory/'v2-desktop.png'),full_page=False)
                    with factory() as db:
                        assert db.query(CompatibilityShadowResult).count()==10
                        paired=db.query(CompatibilityShadowResult).all()
                        assert all(r.legacy_score is not None and r.result['compatibility_score'] is not None for r in paired)
                        assert all(r.result['score_status']=='PROVISIONAL' for r in paired)
                        unchanged={u.opportunity_id:u.score for u in db.query(UserOpportunity).filter(UserOpportunity.user_id==uid,UserOpportunity.opportunity_id.in_([1,2]))}
                        assert unchanged==before
                else:
                    expect(page.get_by_text('Diagnóstico no disponible. Requiere autorización de administrador y habilitación en DEV.',exact=True)).to_be_visible()
                if evaluation_mode:
                    from e2e_evaluation_flow import run as evaluate_ui
                    evaluate_ui(browser,page,web_origin,password,evaluation_reviewers,factory,directory)
                assert not errors,errors
                browser.close()
            (directory/'result.json').write_text(json.dumps({'status':'passed','api':'real local','db':'PostgreSQL isolated','broker':'Redis isolated',
                'worker':'Celery prefork','records':'synthetic','page_errors':errors},indent=2))
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=15)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            services.flags();services.worker_stop();services.redis_stop();engine.dispose()
    print('E2E_PASSED',directory,flush=True)

if __name__=='__main__':main()

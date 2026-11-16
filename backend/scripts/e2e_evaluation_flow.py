"""Local browser QA helper; data, accounts and opinions are synthetic fixtures only."""
import json
from playwright.sync_api import expect
from app.db.models import EvaluationCampaign as Campaign,EvaluationSample as Sample,EvaluationAssignment as Assignment,EvaluationReport as Report
from test_redis_operations import wait


def run(browser,page,origin,password,reviewers,factory,directory):
    from app.db.models import UserOpportunity
    with factory() as db:commercial_before={r.id:(r.score,r.match_state,r.triage) for r in db.query(UserOpportunity)}
    page.set_viewport_size({'width':1440,'height':1000})
    page.goto(origin+'/app/evaluacion-interna')
    expect(page.get_by_role('heading',name='Evaluación interna en DEV',exact=True)).to_be_visible()
    page.get_by_role('button',name='Administración',exact=True).click()
    payload={'name':'SYNTHETIC E2E campaign','scope':'synthetic','authorization_reference':'Synthetic QA authorization only','blinded_sharing_authorized':True,'sample_size':4,'synthetic_pairs':[{'company_key':f'synthetic-{i%2}','process_key':f'controlled-process-{i}','profile':{'sector':'software','actividades':'software contable','departamentos':['Meta']},'opportunity':{'objeto':'Software contable para prueba' if i%2 else 'Equipos agrícolas de prueba','estado':'En proceso','modalidad':'Licitación','valor':1000000,'departamento':'Meta'}} for i in range(4)]}
    page.get_by_label('Campaña JSON',exact=True).fill(json.dumps(payload))
    page.get_by_role('button',name='Crear campaña autorizada',exact=True).click()
    def campaign_ready():
        with factory() as db:return db.query(Campaign).filter_by(name=payload['name'],state='READY').count()==1
    wait(campaign_ready,30)
    page.get_by_role('button',name='Actualizar campaña',exact=True).click()
    page.get_by_label('IDs de revisores autorizados, separados por coma',exact=True).fill(','.join(str(uid) for uid,email in reviewers[:2]))
    page.get_by_role('button',name='Asignar doble revisión',exact=True).click()
    expect(page.get_by_text('Asignaciones registradas.',exact=True)).to_be_visible()
    with factory() as db:
        c=db.query(Campaign).filter_by(name=payload['name']).one();cid=c.id
        sample=db.query(Sample).filter_by(campaign_id=cid).order_by(Sample.id).first();sid=sample.id
    def review(uid,email,value,kind):
        context=browser.new_context(viewport={'width':1000,'height':1000});p=context.new_page()
        p.goto(origin+'/iniciar-sesion');p.get_by_label('Correo electrónico',exact=True).fill(email);p.get_by_placeholder('••••••••',exact=True).fill(password)
        p.get_by_role('button',name='Ingresar',exact=True).click();p.wait_for_url('**/app',timeout=30000)
        p.goto(origin+'/app/evaluacion-interna')
        with factory() as db:a=db.query(Assignment).filter_by(sample_id=sid,evaluator_user_id=uid,kind=kind).one();aid=a.id
        p.get_by_role('button',name=f'{kind} · {aid[:8]}',exact=True).click()
        article=p.get_by_test_id('blind-evaluation');expect(article).to_be_visible()
        text=article.inner_text()
        assert not any(k in text for k in ('legacy_score','compatibility_score','evidence_coverage','Heredado:','V2:'))
        p.get_by_label('Relevancia comercial',exact=True).select_option(str(value))
        p.get_by_label('Motivo',exact=True).fill('Evaluación de fixture sintético para QA del procedimiento.')
        article.screenshot(path=str(directory/f'evaluation-{kind}-{value}.png'))
        p.get_by_role('button',name='Sellar juicio independiente',exact=True).click()
        expect(p.get_by_text('Juicio sellado. No puede editarse ni repetirse.',exact=True)).to_be_visible()
        context.close()
    review(*reviewers[0],0,'REVIEW');review(*reviewers[1],3,'REVIEW')
    page.get_by_role('button',name='Actualizar campaña',exact=True).click()
    expect(page.get_by_text(f'Desacuerdo {sid[:8]}',exact=False)).to_be_visible()
    page.get_by_label('IDs de revisores autorizados, separados por coma',exact=True).fill(str(reviewers[2][0]))
    page.get_by_role('button',name='Asignar adjudicación',exact=True).click()
    expect(page.get_by_text('Tercer revisor independiente asignado.',exact=True)).to_be_visible()
    review(*reviewers[2],2,'ADJUDICATION')
    page.get_by_role('button',name='Cerrar y generar informe',exact=True).click()
    expect(page.get_by_text('Campaña cerrada; evaluaciones e informe inmutables.',exact=True)).to_be_visible()
    expect(page.get_by_role('heading',name='Informe anonimizado',exact=True)).to_be_visible()
    page.screenshot(path=str(directory/'evaluation-admin.png'),full_page=False)
    with factory() as db:
        report=db.query(Report).filter_by(campaign_id=cid).one()
        assert report.payload['resolved_pairs']==1 and report.payload['human_label_count']==0
        assert report.payload['statistical_conclusion']=='INCONCLUSIVE' and not report.payload['activation_authorized']
    with page.expect_download() as download_info:
        page.get_by_role('button',name='Exportar informe JSON',exact=True).click()
    exported=directory/'evaluation-report-synthetic.json'
    download_info.value.save_as(str(exported))
    content=exported.read_text();payload=json.loads(content)
    assert payload['human_label_count']==0 and not payload['activation_authorized']
    assert '"profile":' not in content and 'pliego-sintetico.docx' not in content and 'e2e-local@example.com' not in content
    with factory() as db:assert {r.id:(r.score,r.match_state,r.triage) for r in db.query(UserOpportunity)}==commercial_before
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(directory/'evaluation-mobile.png'),full_page=False)

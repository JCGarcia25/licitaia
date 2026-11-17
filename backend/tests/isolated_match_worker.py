"""Worker de prueba: exige base descartable y controles locales explícitos."""
import json
import os
from pathlib import Path
import time
from sqlalchemy.engine import make_url
from app.workers.celery_app import celery_app as app
from app.services import match_jobs, match_execution

url = make_url(os.environ['DATABASE_URL'])
assert (url.database or '').startswith('mysecop_test_')
control = Path(os.environ['MYSECOP_TEST_CONTROL'])
assert control.parent.name.startswith('mysecop-test-redis-')
original_embed = getattr(match_jobs.embed,'_isolated_original',match_jobs.embed)
original_confirm = getattr(match_execution._confirm,'_isolated_original',match_execution._confirm)

def flags():
    return json.loads(control.read_text())

def embed(text):
    if flags().get('hold'):
        control.with_suffix('.entered').write_text('entered')
        while flags().get('hold'):
            time.sleep(.05)
    if flags().get('provider_failure'):
        raise RuntimeError('isolated_provider_failure')
    return original_embed(text)

def confirm(*args, **kwargs):
    if flags().get('fail_commit'):
        raise RuntimeError('isolated_commit_failure')
    return original_confirm(*args, **kwargs)

embed._isolated_original=original_embed
confirm._isolated_original=original_confirm
match_jobs.embed, match_execution._confirm = embed, confirm
# macOS usa spawn dentro del pool prefork; importar también en cada hijo.
app.conf.imports=tuple(app.conf.imports or ())+('isolated_match_worker',)
app.conf.update(broker_transport_options={'visibility_timeout':2,'socket_connect_timeout':.5,'socket_timeout':.5},
    result_backend_transport_options={'visibility_timeout':2},visibility_timeout=2,
    broker_connection_retry_on_startup=True,broker_connection_max_retries=None)

# Evaluation interruption hook, confined to this disposable worker harness.
from app.services import evaluation_platform
original_evaluation = getattr(evaluation_platform.calculate_base,'_isolated_original',evaluation_platform.calculate_base)
def evaluation_calculate(*args,**kwargs):
    if flags().get('evaluation_hold'):
        control.with_suffix('.entered').write_text('entered')
        while flags().get('evaluation_hold'):time.sleep(.05)
    return original_evaluation(*args,**kwargs)
evaluation_calculate._isolated_original=original_evaluation
evaluation_platform.calculate_base=evaluation_calculate

# Opt-in TVEC source stub. This file already enforces a disposable PostgreSQL
# name and owned local control directory before any worker code can execute.
if os.environ.get('MYSECOP_TVEC_FAKE_SOURCE')=='1':
    from app.services import tvec_ingest
    from test_tvec import FakeClient
    class IsolatedTvecClient(FakeClient):
        def page(self,after=None):
            if flags().get('tvec_hold'):
                control.with_suffix('.entered').write_text('entered')
                while flags().get('tvec_hold'):time.sleep(.05)
            return super().page(after)
    tvec_ingest.TvecClient=IsolatedTvecClient

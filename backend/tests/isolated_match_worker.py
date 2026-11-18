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

# Quotation recovery fixture: one network failure after a committed batch.
# This module has already verified the disposable DB and owned control path.
if os.environ.get('MYSECOP_TVEC_QUOTATIONS_FAKE_SOURCE')=='1':
    import httpx
    from app.services import tvec_full_scan
    from test_tvec_full_scan import Pages
    class IsolatedQuotationClient(Pages):
        def __init__(self):
            super().__init__()
            from datetime import datetime,timezone
            from test_tvec_quotations import INSTANT
            shift=datetime.fromisoformat(control.with_suffix('.quotation-clock').read_text())-INSTANT
            for page in self.pages:
                for row in page:
                    for index in (3,4):
                        row[index]=(datetime.fromisoformat(row[index])+shift).strftime('%Y-%m-%d %H:%M:%S.%f')
        def get(self,path,params=None):
            failed=control.with_suffix('.quotation-failed')
            if params and params.get('page')=='2' and not failed.exists():
                failed.write_text('synthetic connection failure')
                raise httpx.ConnectError('synthetic quotation interruption')
            return super().get(path,params)
    tvec_full_scan.Client=IsolatedQuotationClient


if os.environ.get('MYSECOP_OFFER_REMINDER_MAILBOX'):
    from app.services import offer_reminders
    mailbox=Path(os.environ['MYSECOP_OFFER_REMINDER_MAILBOX'])
    assert mailbox.parent==control.parent and mailbox.name=='reminder-mailbox.jsonl'
    def capture_reminder(recipient,subject,body):
        with mailbox.open('a') as handle:handle.write(json.dumps({'recipient':recipient,'subject':subject,'body':body})+'\n')
        return 'SENT',None
    offer_reminders.send=capture_reminder

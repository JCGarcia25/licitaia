"""Own PostgreSQL instance only; never accepts a business DB URL."""
from pathlib import Path
import tempfile,subprocess,sys,os

def main():
    from pgserver import PostgresServer
    import psycopg2
    with PostgresServer(Path(tempfile.mkdtemp(prefix='mysecop-offer-reminders-pg-')),cleanup_mode='stop') as server:
        c=psycopg2.connect(server.get_uri());c.autocommit=True
        with c.cursor() as cursor:cursor.execute('CREATE DATABASE mysecop_test_offer_reminders')
        c.close()
        env={**os.environ,'MYSECOP_TEST_POSTGRES_URL':server.get_uri('mysecop_test_offer_reminders').replace('postgresql://','postgresql+psycopg2://')}
        result=subprocess.run([sys.executable,'-m','pytest','tests/test_postgresql_offer_reminders.py','-q','--tb=short'],cwd=Path(__file__).resolve().parents[1],env=env)
        if result.returncode:return result.returncode
        c=psycopg2.connect(server.get_uri());c.autocommit=True
        with c.cursor() as cursor:cursor.execute('CREATE DATABASE mysecop_test_offer_reminders_redis')
        c.close()
        env['MYSECOP_TEST_POSTGRES_URL']=server.get_uri('mysecop_test_offer_reminders_redis').replace('postgresql://','postgresql+psycopg2://')
        env['MYSECOP_RUN_REDIS_TESTS']='1'
        return subprocess.run([sys.executable,'-m','pytest','tests/test_redis_offer_reminders.py','-q','-s','--tb=short'],cwd=Path(__file__).resolve().parents[1],env=env).returncode
if __name__=='__main__':sys.exit(main())

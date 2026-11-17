"""Create all PostgreSQL databases used by TVEC tests; no external DB URLs."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile


def main():
    from pgserver import PostgresServer
    import psycopg2
    directory=Path(tempfile.mkdtemp(prefix='mysecop-tvec-isolated-'))
    print('TVEC disposable server:',directory,flush=True)
    with PostgresServer(directory,cleanup_mode='stop') as server:
        for name,module in [('mysecop_test_tvec_pg','tests/test_postgresql_tvec.py'),('mysecop_test_tvec_redis','tests/test_redis_tvec.py')]:
            c=psycopg2.connect(server.get_uri());c.autocommit=True
            try:
                with c.cursor() as cursor:cursor.execute('CREATE DATABASE '+name)
            finally:c.close()
            env={**os.environ,'MYSECOP_TEST_POSTGRES_URL':server.get_uri(name).replace('postgresql://','postgresql+psycopg2://'),
                 'MYSECOP_RUN_REDIS_TESTS':'1','PYTHONDONTWRITEBYTECODE':'1'}
            result=subprocess.run([sys.executable,'-m','pytest',module,'-q','-s','--tb=short','--maxfail=1'],cwd=Path(__file__).resolve().parents[1],env=env)
            if result.returncode:return result.returncode
    return 0

if __name__=='__main__':sys.exit(main())

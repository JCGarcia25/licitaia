"""Ejecutor reproducible PG + Redis reales, sin servicios globales."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    from pgserver import PostgresServer
    import psycopg2
    with PostgresServer(Path(tempfile.mkdtemp(prefix='mysecop-phase13-pg-')),cleanup_mode='stop') as server:
        connection=psycopg2.connect(server.get_uri());connection.autocommit=True
        with connection.cursor() as cursor:cursor.execute('CREATE DATABASE mysecop_test_phase13_redis')
        connection.close()
        for name,module in [('mysecop_test_phase13_redis','tests/test_redis_operations.py'),('mysecop_test_phase2_redis','tests/test_redis_compatibility.py'),('mysecop_test_phase21_redis','tests/test_redis_evaluation.py')]:
            if name!='mysecop_test_phase13_redis':
                c=psycopg2.connect(server.get_uri());c.autocommit=True
                with c.cursor() as cursor:cursor.execute('CREATE DATABASE '+name)
                c.close()
            env={**os.environ,'MYSECOP_TEST_POSTGRES_URL':server.get_uri(name).replace('postgresql://','postgresql+psycopg2://'),
                'MYSECOP_RUN_REDIS_TESTS':'1','PYTHONDONTWRITEBYTECODE':'1'}
            result=subprocess.run([sys.executable,'-m','pytest',module,'-q','-s','--tb=short','--maxfail=1'],env=env,
                cwd=Path(__file__).resolve().parents[1])
            if result.returncode:return result.returncode
        return 0

if __name__=='__main__':sys.exit(main())

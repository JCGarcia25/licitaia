"""Integración opt-in con pgserver y psycopg2 instalados en un venv de pruebas.

No instala dependencias ni servicios; crea exclusivamente una base temporal.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    from pgserver import PostgresServer
    import psycopg2

    directory = Path(tempfile.mkdtemp(prefix="mysecop-isolated-pg-"))
    print(f"Directorio PostgreSQL descartable: {directory}", flush=True)
    with PostgresServer(directory, cleanup_mode="stop") as server:
        connection = psycopg2.connect(server.get_uri())
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                print(cursor.fetchone()[0], flush=True)
                cursor.execute("CREATE DATABASE mysecop_test_phase11")
                cursor.execute("CREATE DATABASE mysecop_test_phase12")
                cursor.execute("CREATE DATABASE mysecop_test_phase2")
                cursor.execute("CREATE DATABASE mysecop_test_phase21")
        finally:
            connection.close()
        for name, module in [('mysecop_test_phase11', 'tests/test_postgresql_sync.py'),
                             ('mysecop_test_phase12', 'tests/test_postgresql_matches.py'),
                             ('mysecop_test_phase2', 'tests/test_postgresql_compatibility.py'),
                             ('mysecop_test_phase21', 'tests/test_postgresql_evaluation.py')]:
            env = {**os.environ, "MYSECOP_TEST_POSTGRES_URL": server.get_uri(name).replace(
                "postgresql://", "postgresql+psycopg2://"), "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", module, "--tb=short"],
                env=env, cwd=Path(__file__).resolve().parents[1],
            )
            if result.returncode:
                return result.returncode
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

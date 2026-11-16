"""Build a local, deterministic source snapshot. Never stages or publishes Git.

The manifest identifies the complete source payload, including audited untracked
files. Build output must be outside the repository. Evidence stays outside it.
"""
import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'MYSECOP_COMPATIBILITY_V2_RELEASE_MANIFEST.md'
PATTERNS = {
    'private_key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'openai_key': r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}',
    'aws_key': r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'github_token': r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}',
}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def phase(path, changed):
    if not changed:
        return 'Base comercial preexistente, sin cambios'
    if 'RELEASE_' in path or 'DEV_RUNBOOK' in path or path in {
        '.github/workflows/ci.yml', '.gitignore', 'docker-compose.dev-rc.yml', 'backend/.dockerignore', 'frontend/.dockerignore',
        'backend/Dockerfile', 'frontend/Dockerfile', 'frontend/package.json',
        'frontend/package-lock.json', 'frontend/next-env.d.ts',
        'backend/constraints-release-candidate.txt', 'backend/scripts/release_preflight.py',
        'backend/scripts/prepare_release_candidate.py', 'backend/tests/test_release_security.py',
    }:
        return 'Consolidación RC: seguridad, dependencias o entrega'
    if 'FASE' in path or path.startswith('AUDITORIA_'):
        return 'Documentación histórica de fases 1–2.1'
    if 'evaluation' in path or 'evaluacion-interna' in path or 'phase21' in path:
        return '2.1 evaluación (plantillas ranking anteriores: 1/2)'
    if 'compatibility' in path or 'unspsc' in path or 'diagnostico-compatibilidad' in path or 'compare_compatibility' in path:
        return '2 modelo V2 / guardias 2.1'
    if any(s in path for s in ['0010_', 'incremental_sync', 'postgresql_sync', 'secop_client', '/ingest.py', 'test_secop']):
        return '1.1 sincronización incremental y SECOP I'
    if re.search(r'/000[3-8]_', path):
        return '1.1 compatibilidad histórica de migraciones'
    if any(s in path for s in ['match_', 'match-progress', '/matches.py', '0011_', '0012_', 'phase13', 'redis_operations', 'postgresql_matches']):
        return '1.2 recálculo / 1.3 estabilización'
    if 'ranking' in path or path.startswith('backend/evaluation/'):
        return '1/2 evaluación de ranking y plantillas'
    if 'opportunity_' in path or path in {'backend/app/routers/alerts.py', 'backend/tests/test_opportunities_search.py'}:
        return '1 filtros, vigencia y alertas'
    if path in {'backend/app/routers/agents.py', 'backend/app/routers/opportunities.py', 'backend/app/services/alerts.py'}:
        return '1/1.2 integración comercial + corrección RC de análisis privados'
    if path in {'.env.example', 'backend/app/core/config.py', 'backend/app/db/models.py', 'backend/app/db/session.py',
                'backend/app/main.py', 'backend/app/schemas.py', 'backend/app/workers/celery_app.py',
                'backend/app/workers/tasks.py', 'backend/tests/conftest.py'}:
        return 'Compartido 1.1/1.2/1.3/2/2.1'
    if path == 'backend/app/routers/profile.py' or path.startswith('frontend/app/(private)/app/') or path in {
        'backend/tests/test_flow.py', 'backend/tests/test_feedback.py', 'backend/requirements-isolated-tests.txt',
        'backend/scripts/test_isolated_postgresql.py', 'backend/scripts/evaluate_ranking.py'}:
        return '1/1.2/1.3 integración y regresión'
    return 'NO IDENTIFICADO'


def build(output):
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Output must be outside repository')
    if git('ls-files', '-u').strip():
        raise ValueError('Unresolved Git conflicts')
    tracked = set(git('ls-files', '-z').decode().split('\0')) - {''}
    extra = set(git('ls-files', '--others', '--exclude-standard', '-z').decode().split('\0')) - {''}
    modified = set(git('diff', '--name-only', 'HEAD', '-z').decode().split('\0')) - {''}
    files, excluded, findings = [], [], []
    for name in sorted(tracked | extra):
        p = ROOT / name
        reason = None
        if name == MANIFEST:
            reason = 'Manifiesto externo al payload para evitar hash autorreferente'
        elif not p.is_file() or p.is_symlink():
            reason = 'Ausente/enlace/no regular: revisar si era archivo de aplicación'
        elif name.startswith('backend/benchmarks/'):
            reason = 'Evidencia QA, no imagen de aplicación; conservada localmente'
        elif (p.name.startswith('.env') and p.name != '.env.example') or p.suffix.lower() in {'.pem','.key','.p12','.db','.sqlite','.sqlite3','.log','.pyc'}:
            reason = 'Configuración sensible, persistencia o temporal'
        elif any(s in name.lower() for s in ['private_key','credentials','id_rsa','id_ed25519']):
            reason = 'Nombre sensible'
        if reason:
            excluded.append({'path': name, 'reason': reason})
            continue
        data = p.read_bytes()
        if b'\0' not in data[:8192]:
            text = data.decode(errors='replace')
            for kind, pattern in PATTERNS.items():
                if re.search(pattern, text):
                    findings.append({'path': name, 'kind': kind})
        label = phase(name, name in modified or name in extra)
        if label == 'NO IDENTIFICADO':
            findings.append({'path':name, 'kind':'unclassified change'})
        files.append({'path':name, 'sha256':sha(data), 'mode':'0755' if p.stat().st_mode & 0o111 else '0644',
                      'git_state':'untracked' if name in extra else ('modified' if name in modified else 'HEAD'), 'phase':label})
    if findings:
        raise ValueError(json.dumps(findings))  # names only, no matched values
    # Ignored local secret files are named, never read or hashed.
    for p in [ROOT/'.env', ROOT/'backend/.env', ROOT/'frontend/.env', ROOT/'frontend/.env.local']:
        if p.exists():
            excluded.append({'path':str(p.relative_to(ROOT)), 'reason':'Configuración local ignorada, no leída ni incluida'})
    canonical = ''.join(f"{f['mode']} {f['sha256']} {f['path']}\n" for f in files).encode()
    identity = sha(canonical)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive = output/'mysecop-compatibility-v2-rc1-source.tar.gz'
    with archive.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w') as tar:
            for f in files:
                data = (ROOT/f['path']).read_bytes()
                if sha(data) != f['sha256']:
                    raise ValueError('Source changed during packaging')
                info = tarfile.TarInfo(f['path']); info.size = len(data); info.mode = int(f['mode'],8)
                tar.addfile(info, io.BytesIO(data))
    with tarfile.open(archive) as tar:
        assert tar.getnames() == [f['path'] for f in files]
        for f in files:
            assert sha(tar.extractfile(f['path']).read()) == f['sha256']
    manifest = {'name':'mysecop-compatibility-v2-rc1', 'status':'LOCAL_SNAPSHOT_NOT_GIT_RELEASE',
                'head':git('rev-parse','HEAD').decode().strip(), 'branch':git('branch','--show-current').decode().strip(),
                'payload_sha256':identity, 'archive_sha256':sha(archive.read_bytes()), 'files':files, 'excluded':excluded,
                'credential_pattern_findings':0, 'operational_deployment':False}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
    md = f'''# MySECOP Compatibility V2 — Manifiesto RC1

Fecha de preparación: 16 de noviembre de 2026. Estado: **snapshot local**, sin commit/tag/publicación.

Nombre propuesto: `{manifest['name']}`. Rama `{manifest['branch']}`; base Git `{manifest['head']}`.

Identidad del payload SHA-256: `{identity}`.

Archivo local: `{archive}`. SHA-256 del archivo: `{manifest['archive_sha256']}`.

Manifiesto JSON: `{output/'manifest.json'}`. Backup previo independiente: `/private/tmp/mysecop-rc-preparation-20261116/source-backup.tar.gz`.

La identidad se calcula como SHA-256 de las líneas UTF-8 ordenadas `modo sha256 ruta\\n` de la tabla siguiente. Incluye código completo, assets públicos comerciales, lockfiles, catálogo UNSPSC, fixtures explícitos y documentación. Excluye este manifiesto para evitar autorreferencia. El tar usa metadatos normalizados y gzip mtime=0; se verificaron todos los miembros sin extraerlos. Regenerar con `backend/.venv/bin/python backend/scripts/prepare_release_candidate.py --output /private/tmp/mysecop-rc-final-20261116` desde la raíz. No conecta a servicios ni crea referencias Git.

## Archivos incluidos

La clasificación es por contenido y función, no atribución histórica de autor. Los archivos compartidos contienen varias fases. `HEAD` designa base comercial intacta; `untracked` está capturado en este paquete y debe incorporarse explícitamente a un commit futuro autorizado.

| Archivo | Git | Fase / alcance | Modo | SHA-256 |
|---|---|---|---|---|
'''
    md += ''.join(f"| `{f['path']}` | {f['git_state']} | {f['phase']} | {f['mode']} | `{f['sha256']}` |\n" for f in files)
    md += '\n## Archivos excluidos\n\n| Archivo | Motivo |\n|---|---|\n'
    md += ''.join(f"| `{f['path']}` | {f['reason']} |\n" for f in excluded)
    md += '''
También se excluyen por Git ignore: `.git`, venvs, node_modules, `.next`, caches, logs, archivos de entorno y temporales. No se borran. El backup de código previo no incluye PNG ni benchmarks; el paquete final sí incluye los assets públicos tracked necesarios.

## Dependencias, migraciones y configuración

Python 3.12: `backend/requirements.txt` con `backend/constraints-release-candidate.txt`, más `psycopg2-binary==2.9.13`. QA: `backend/requirements-isolated-tests.txt` con las mismas constraints; Chromium Playwright se provisiona aparte. Frontend: `npm ci`, lockfile incluido, Next 15.5.29 y PostCSS 8.5.33 con override. El build local usa Node 20.11.0/npm 10.2.4; Docker/CI declaran Node 22, aún sin prueba de imagen Linux. Las constraints fijan las versiones observadas, no hashes de wheels ni digest de imagen; no equivale a build binario hermético.

Cadena única 0001 → 0002…0009 → 0010_sync_cursor → 0011_match_jobs → 0012_failed_match_inputs → 0013_compatibility_shadow → 0014_evaluation_platform. No stamp. Ver evidencia PostgreSQL y estrategia histórica en el documento principal. Variables, workers y orden de instalación en DEV_RUNBOOK. Flags experimentales false, llamadas externas cero.

## Riesgos de reproducibilidad y publicación

El checkout Git por sí solo NO reproduce este snapshot: hay modificaciones y archivos sin seguimiento inventariados. El tar y hashes permiten reconstruir el código local exacto. No existe commit/tag RC autorizado, rama nueva ni imagen OCI identificada por digest. El paquete excluye configuraciones privadas y requiere provisión separada de secretos/destinos. Las dependencias de sistema y contenedores usan tags sin digest; instalación Linux/Compose no verificada. Los workflows existentes en develop despliegan al hacer push: no usarlos para publicar el RC sin una orden operativa y una revisión explícita del flujo.

La búsqueda de credenciales por patrones tuvo cero hallazgos; no sustituye un escáner completo de secretos o una auditoría de todo el historial Git. La evidencia QA está separada del payload en `/private/tmp/mysecop-rc-preparation-20261116/evidence/`; nunca se incluye una base de pruebas ni datos operativos.
'''
    (ROOT/MANIFEST).write_text(md)
    print(json.dumps({'payload_sha256':identity, 'archive_sha256':manifest['archive_sha256'],
                      'file_count':len(files), 'output':str(output), 'published':False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)

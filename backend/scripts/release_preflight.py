"""Offline RC configuration check: never opens DB, broker or HTTP connections.

Run from backend with the future DEV environment injected by its operator.
Output contains check names only, never configuration values or credentials.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.services.evaluation_guard import database_identity, broker_identity, configured_target


def check(settings):
    def valid_url(value, schemes):
        try:
            u = urlsplit(value)
            return u.scheme in schemes and bool(u.hostname) and not (
                u.username or u.password or u.query or u.fragment or u.path not in {'', '/'}
            )
        except ValueError:
            return False
    checks = {
        'environment_development': settings.environment == 'development',
        'installation_secret': len(settings.secret_key) >= 32 and 'change-me' not in settings.secret_key,
        'demo_seed_disabled': not settings.allow_demo_seed,
        'debug_disabled': not settings.debug_endpoint_enabled,
        'external_semantics_disabled': not settings.evaluation_semantic_enabled and settings.evaluation_external_max_calls == 0,
        'legacy_embedding_fake': settings.embedding_provider == 'fake',
        'llm_heuristic': settings.llm_provider == 'heuristic',
        'billing_manual': settings.billing_provider == 'manual',
        'frontend_origin': valid_url(settings.frontend_url, {'http','https'}),
        'api_origin': valid_url(settings.evaluation_api_origin, {'http','https'}),
        'cors_matches_frontend': {x.strip().rstrip('/') for x in settings.cors_origins.split(',')} == {settings.frontend_url.rstrip('/')},
    }
    try:
        checks['explicit_postgresql_destination'] = database_identity(settings.database_url)[0] == 'postgresql'
    except (ValueError, TypeError):
        checks['explicit_postgresql_destination'] = False
    try:
        broker_identity(settings.redis_url)
        checks['explicit_redis_destination'] = True
    except (ValueError, TypeError):
        checks['explicit_redis_destination'] = False
    if settings.evaluation_enabled or settings.compatibility_v2_shadow_enabled:
        try:
            configured_target(settings, require_evaluation_enabled=False)
            checks['experimental_tuple_allowlisted'] = True
        except (ValueError, TypeError):
            checks['experimental_tuple_allowlisted'] = False
    return {'status':'PASS_OFFLINE' if all(checks.values()) else 'BLOCKED',
            'checks':checks, 'connections_opened':0,
            'not_verified':['operational_destination_ownership','database_revision_and_schema',
                            'persisted_environment_identity','backups','running_services','secrets_entropy']}


if __name__ == '__main__':
    try:
        result = check(get_settings())
    except Exception:
        # Pydantic errors may contain input values. Never serialize the exception.
        result = {'status':'BLOCKED', 'reason':'invalid configuration; values suppressed', 'connections_opened':0}
    print(json.dumps(result, sort_keys=True))
    sys.exit(0 if result['status'] == 'PASS_OFFLINE' else 2)

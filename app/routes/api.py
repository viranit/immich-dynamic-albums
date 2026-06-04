"""REST API — JSON:API 1.0 (https://jsonapi.org) format.

All responses use ``Content-Type: application/vnd.api+json``.

Request bodies are accepted in both the strict JSON:API envelope::

    {"data": {"type": "albums", "attributes": {…}}}

and as plain JSON (backward-compatible with the browser UI)::

    {"name": "My Album", "album_type": "dynamic", …}

Error responses follow the JSON:API errors object::

    {"jsonapi": {…}, "errors": [{"status": "422", "title": …, "detail": …}]}
"""
import uuid

from flask import Blueprint, request, current_app
from flask_login import login_required

from app import db
from app.models import Album, Setting, SyncLog
from app.utils.validators import validate_query_config
from app.auth import get_immich_client
from app.album_service import AlbumSyncService
import app.utils.jsonapi as jsonapi

bp = Blueprint('api', __name__)

_SENSITIVE_SETTINGS = frozenset({'immich_api_key', 'oidc_client_secret'})


# ---------------------------------------------------------------------------
# Albums
# ---------------------------------------------------------------------------

@bp.route('/albums', methods=['GET'])
@login_required
def get_albums():
    albums = Album.query.order_by(Album.updated_at.desc()).all()
    return jsonapi.ok(
        [a.to_jsonapi_resource() for a in albums],
        meta={'total': len(albums)},
        links={'self': '/api/albums'},
    )


@bp.route('/albums', methods=['POST'])
@login_required
def create_album():
    attrs = jsonapi.get_attributes()
    name = (attrs.get('name') or '').strip()
    query_config = attrs.get('query_config')

    errs = []
    if not name:
        errs.append('name is required')
    if query_config is None:
        errs.append('query_config is required')
    else:
        errs.extend(validate_query_config(query_config))
    if name and Album.query.filter_by(name=name).first():
        errs.append(f'Album "{name}" already exists')

    if errs:
        return jsonapi.errors(errs)

    album = Album(
        id=str(uuid.uuid4()),
        name=name,
        album_type=attrs.get('album_type', 'dynamic'),
        query_config=query_config,
        sync_enabled=attrs.get('sync_enabled', True),
        sync_interval=attrs.get('sync_interval'),
    )
    db.session.add(album)
    db.session.commit()
    return jsonapi.created(
        album.to_jsonapi_resource(),
        links={'self': f'/api/albums/{album.id}'},
    )


@bp.route('/albums/<album_id>', methods=['GET'])
@login_required
def get_album(album_id):
    album = Album.query.get_or_404(album_id)
    return jsonapi.ok(
        album.to_jsonapi_resource(),
        links={'self': f'/api/albums/{album_id}'},
    )


@bp.route('/albums/<album_id>', methods=['PUT', 'PATCH'])
@login_required
def update_album(album_id):
    album = Album.query.get_or_404(album_id)
    attrs = jsonapi.get_attributes()

    errs = []
    if 'name' in attrs:
        new_name = (attrs['name'] or '').strip()
        existing = Album.query.filter_by(name=new_name).first()
        if existing and str(existing.id) != album_id:
            errs.append(f'Album "{new_name}" already exists')
        else:
            album.name = new_name

    if 'query_config' in attrs:
        qerrs = validate_query_config(attrs['query_config'])
        if qerrs:
            errs.extend(qerrs)
        else:
            album.query_config = attrs['query_config']

    if errs:
        return jsonapi.errors(errs)

    for field in ('album_type', 'sync_enabled', 'sync_interval'):
        if field in attrs:
            setattr(album, field, attrs[field])

    db.session.commit()
    return jsonapi.ok(
        album.to_jsonapi_resource(),
        links={'self': f'/api/albums/{album_id}'},
    )


@bp.route('/albums/<album_id>', methods=['DELETE'])
@login_required
def delete_album(album_id):
    album = Album.query.get_or_404(album_id)
    db.session.delete(album)
    db.session.commit()
    return jsonapi.meta_ok({'message': f'Album {album_id} deleted'})


@bp.route('/albums/<album_id>/sync', methods=['POST'])
@login_required
def sync_album(album_id):
    album = Album.query.get_or_404(album_id)
    try:
        result = AlbumSyncService(get_immich_client()).sync_album(album)
        return jsonapi.ok(
            jsonapi.resource(
                type_='sync-results',
                id_=album_id,
                attributes=result,
            )
        )
    except Exception as exc:
        current_app.logger.error(f'API sync error for album {album_id}: {exc}')
        return jsonapi.error(500, 'Sync Failed', str(exc))


@bp.route('/albums/<album_id>/logs', methods=['GET'])
@login_required
def get_sync_logs(album_id):
    Album.query.get_or_404(album_id)  # 404 guard
    limit = min(int(request.args.get('limit', 50)), 200)
    logs = (
        SyncLog.query
        .filter_by(album_id=album_id)
        .order_by(SyncLog.started_at.desc())
        .limit(limit)
        .all()
    )
    return jsonapi.ok(
        [log.to_jsonapi_resource() for log in logs],
        meta={'total': len(logs)},
        links={'self': f'/api/albums/{album_id}/logs'},
    )


# ---------------------------------------------------------------------------
# Immich look-ups (used by the query-builder UI)
# ---------------------------------------------------------------------------

@bp.route('/immich/people', methods=['GET'])
@login_required
def get_people():
    try:
        client = get_immich_client()
        if not client:
            return jsonapi.error(503, 'Service Unavailable', 'Immich client not configured')
        raw = client.get_people()
        # Immich returns {"people": [...]} but handle a plain list for test mocks
        people = raw.get('people', []) if isinstance(raw, dict) else raw
        data = [
            jsonapi.resource('people', p['id'], {'name': p.get('name', '')})
            for p in people
        ]
        return jsonapi.ok(data, meta={'total': len(data)})
    except Exception as exc:
        return jsonapi.error(500, 'Immich Error', str(exc))


@bp.route('/immich/tags', methods=['GET'])
@login_required
def get_tags():
    try:
        client = get_immich_client()
        if not client:
            return jsonapi.error(503, 'Service Unavailable', 'Immich client not configured')
        tags = client.get_tags()
        data = [
            jsonapi.resource('tags', t['id'], {'name': t.get('name', '')})
            for t in tags
        ]
        return jsonapi.ok(data, meta={'total': len(data)})
    except Exception as exc:
        return jsonapi.error(500, 'Immich Error', str(exc))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@bp.route('/settings', methods=['GET'])
@login_required
def get_settings():
    settings = Setting.query.all()
    data = [
        s.to_jsonapi_resource(mask_value=(s.key in _SENSITIVE_SETTINGS))
        for s in settings
    ]
    return jsonapi.ok(
        data,
        meta={'total': len(data)},
        links={'self': '/api/settings'},
    )


@bp.route('/settings', methods=['POST', 'PATCH'])
@login_required
def update_settings():
    attrs = jsonapi.get_attributes()
    if not attrs:
        return jsonapi.error(400, 'Bad Request', 'No attributes provided')

    for key, value in attrs.items():
        setting = Setting.query.get(key)
        if setting:
            setting.value = str(value)
        else:
            db.session.add(Setting(key=key, value=str(value)))
    db.session.commit()

    try:
        from app.scheduler import schedule_sync_jobs
        schedule_sync_jobs()
    except Exception as exc:
        current_app.logger.warning(f'Scheduler update failed after settings change: {exc}')

    return jsonapi.meta_ok({'message': 'Settings updated'})


@bp.route('/settings/test-connection', methods=['POST'])
@login_required
def test_connection():
    """Test the Immich connection using values from the request body (before saving)."""
    try:
        from app.immich_client import ImmichClient

        attrs = jsonapi.get_attributes()
        url = attrs.get('immich_url', '').strip()
        key = attrs.get('immich_api_key', '').strip()

        client = ImmichClient(url, key) if url and key else get_immich_client()
        version = client.version()
        whoami = client.whoami()
        return jsonapi.ok(
            jsonapi.resource(
                type_='connection-tests',
                id_='latest',
                attributes={
                    'ok': True,
                    'message': f'Connected as {whoami.get("email", "unknown")} (v{version})',
                    'version': version,
                    'user': whoami.get('email'),
                },
            )
        )
    except Exception as exc:
        return jsonapi.ok(
            jsonapi.resource(
                type_='connection-tests',
                id_='latest',
                attributes={'ok': False, 'message': str(exc)},
            )
        )


@bp.route('/settings/reschedule', methods=['POST'])
@login_required
def reschedule():
    """Re-apply the sync schedule from the current settings without restarting."""
    try:
        from app.scheduler import schedule_sync_jobs
        count = schedule_sync_jobs()
        return jsonapi.meta_ok({'message': f'Schedule updated: {count} job(s) active'})
    except Exception as exc:
        return jsonapi.error(500, 'Scheduler Error', str(exc))


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

@bp.route('/scheduler/status', methods=['GET'])
@login_required
def scheduler_status():
    from app.scheduler import get_scheduler_status
    status = get_scheduler_status()
    return jsonapi.ok(
        jsonapi.resource(
            type_='scheduler-status',
            id_='default',
            attributes=status,
        )
    )

"""REST API routes (JSON)."""
import uuid

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required

from app import db
from app.models import Album, Setting, SyncLog
from app.utils.validators import validate_query_config

bp = Blueprint('api', __name__)


# ---------------------------------------------------------------------------
# Albums
# ---------------------------------------------------------------------------

@bp.route('/albums', methods=['GET'])
@login_required
def get_albums():
    albums = Album.query.order_by(Album.updated_at.desc()).all()
    return jsonify([a.to_dict() for a in albums])


@bp.route('/albums', methods=['POST'])
@login_required
def create_album():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    query_config = data.get('query_config')

    errors = []
    if not name:
        errors.append('name is required')
    if query_config is None:
        errors.append('query_config is required')
    else:
        errors.extend(validate_query_config(query_config))
    if Album.query.filter_by(name=name).first():
        errors.append(f'Album "{name}" already exists')

    if errors:
        return jsonify({'errors': errors}), 422

    album = Album(
        id=str(uuid.uuid4()),
        name=name,
        album_type=data.get('album_type', 'dynamic'),
        query_config=query_config,
        sync_enabled=data.get('sync_enabled', True),
        sync_interval=data.get('sync_interval'),
    )
    db.session.add(album)
    db.session.commit()
    return jsonify(album.to_dict()), 201


@bp.route('/albums/<album_id>', methods=['GET'])
@login_required
def get_album(album_id):
    album = Album.query.get_or_404(album_id)
    return jsonify(album.to_dict())


@bp.route('/albums/<album_id>', methods=['PUT'])
@login_required
def update_album(album_id):
    album = Album.query.get_or_404(album_id)
    data = request.get_json(force=True, silent=True) or {}

    errors = []
    if 'name' in data:
        existing = Album.query.filter_by(name=data['name']).first()
        if existing and existing.id != album_id:
            errors.append(f'Album "{data["name"]}" already exists')
        else:
            album.name = data['name']

    if 'query_config' in data:
        qerrs = validate_query_config(data['query_config'])
        if qerrs:
            errors.extend(qerrs)
        else:
            album.query_config = data['query_config']

    if errors:
        return jsonify({'errors': errors}), 422

    for field in ('album_type', 'sync_enabled', 'sync_interval'):
        if field in data:
            setattr(album, field, data[field])

    db.session.commit()
    return jsonify(album.to_dict())


@bp.route('/albums/<album_id>', methods=['DELETE'])
@login_required
def delete_album(album_id):
    album = Album.query.get_or_404(album_id)
    db.session.delete(album)
    db.session.commit()
    return jsonify({'message': 'Album deleted'})


@bp.route('/albums/<album_id>/sync', methods=['POST'])
@login_required
def sync_album(album_id):
    album = Album.query.get_or_404(album_id)
    try:
        from app.auth import get_immich_client
        from app.album_service import AlbumSyncService
        result = AlbumSyncService(get_immich_client()).sync_album(album)
        return jsonify(result)
    except Exception as exc:
        current_app.logger.error(f'API sync error for album {album_id}: {exc}')
        return jsonify({'status': 'error', 'error': str(exc)}), 500


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
    return jsonify([log.to_dict() for log in logs])


# ---------------------------------------------------------------------------
# Immich look-ups (used by the query-builder UI)
# ---------------------------------------------------------------------------

@bp.route('/immich/people', methods=['GET'])
@login_required
def get_people():
    try:
        from app.auth import get_immich_client
        client = get_immich_client()
        data = client.get_people()
        return jsonify(data.get('people', []))
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@bp.route('/immich/tags', methods=['GET'])
@login_required
def get_tags():
    try:
        from app.auth import get_immich_client
        client = get_immich_client()
        return jsonify(client.get_tags())
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@bp.route('/settings', methods=['GET'])
@login_required
def get_settings():
    SENSITIVE = {'immich_api_key', 'oidc_client_secret'}
    result = {}
    for s in Setting.query.all():
        value = '***' if s.key in SENSITIVE else s.value
        result[s.key] = {'value': value, 'description': s.description}
    return jsonify(result)


@bp.route('/settings', methods=['POST'])
@login_required
def update_settings():
    data = request.get_json(force=True, silent=True) or {}
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    for key, value in data.items():
        setting = Setting.query.get(key)
        if setting:
            setting.value = str(value)
        else:
            setting = Setting(key=key, value=str(value))
            db.session.add(setting)
    db.session.commit()

    try:
        from app.scheduler import schedule_sync_jobs
        schedule_sync_jobs()
    except Exception as exc:
        current_app.logger.warning(f'Scheduler update failed after settings change: {exc}')

    return jsonify({'message': 'Settings updated'})


@bp.route('/test-connection', methods=['POST'])
@login_required
def test_connection():
    try:
        from app.auth import get_immich_client
        client = get_immich_client()
        version = client.version()
        whoami = client.whoami()
        return jsonify({'status': 'ok', 'version': version, 'user': whoami.get('email')})
    except Exception as exc:
        return jsonify({'status': 'error', 'error': str(exc)}), 500


@bp.route('/scheduler/status', methods=['GET'])
@login_required
def scheduler_status():
    from app.scheduler import get_scheduler_status
    return jsonify(get_scheduler_status())

"""Album CRUD routes."""
import json
import uuid

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app,
)
from flask_login import login_required

from app import db
from app.models import Album, SyncLog
from app.utils.validators import validate_query_config

bp = Blueprint('albums', __name__)


@bp.route('/')
@login_required
def index():
    return redirect(url_for('albums.list_albums'))


@bp.route('/albums')
@login_required
def list_albums():
    """List all albums ordered by most-recently updated."""
    all_albums = Album.query.order_by(Album.updated_at.desc()).all()
    return render_template('albums/list.html', albums=all_albums)


@bp.route('/albums/new', methods=['GET', 'POST'])
@login_required
def new_album():
    """Create a new album."""
    if request.method == 'GET':
        return render_template('albums/form.html', album=None, action='create')

    name = request.form.get('name', '').strip()
    album_type = request.form.get('album_type', 'dynamic')
    query_config_raw = request.form.get('query_config', '{}')
    sync_interval = request.form.get('sync_interval') or None

    errors = []
    if not name:
        errors.append('Album name is required.')

    try:
        query_config = json.loads(query_config_raw)
    except json.JSONDecodeError:
        query_config = {}
        errors.append('Invalid JSON in query configuration.')

    errors.extend(validate_query_config(query_config))

    if Album.query.filter_by(name=name).first():
        errors.append(f'An album named "{name}" already exists.')

    if errors:
        for err in errors:
            flash(err, 'danger')
        return render_template('albums/form.html', album=None, action='create',
                               form_data=request.form)

    album = Album(
        id=str(uuid.uuid4()),
        name=name,
        album_type=album_type,
        query_config=query_config,
        sync_enabled=True,
        sync_interval=int(sync_interval) if sync_interval else None,
    )
    db.session.add(album)
    db.session.commit()

    flash(f'Album "{name}" created.', 'success')

    # Static albums sync immediately on creation
    if album_type == 'static':
        return redirect(url_for('albums.sync_album', album_id=album.id,
                                next=url_for('albums.album_detail', album_id=album.id)))

    return redirect(url_for('albums.album_detail', album_id=album.id))


@bp.route('/albums/<album_id>')
@login_required
def album_detail(album_id):
    """Show album details and recent sync history."""
    album = Album.query.get_or_404(album_id)
    sync_logs = (
        SyncLog.query
        .filter_by(album_id=album_id)
        .order_by(SyncLog.started_at.desc())
        .limit(20)
        .all()
    )
    return render_template('albums/detail.html', album=album, sync_logs=sync_logs)


@bp.route('/albums/<album_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_album(album_id):
    """Edit an existing album."""
    album = Album.query.get_or_404(album_id)

    if request.method == 'GET':
        return render_template('albums/form.html', album=album, action='edit')

    name = request.form.get('name', '').strip()
    album_type = request.form.get('album_type', album.album_type)
    query_config_raw = request.form.get('query_config', '{}')
    sync_interval = request.form.get('sync_interval') or None
    sync_enabled = request.form.get('sync_enabled') == 'on'

    errors = []
    if not name:
        errors.append('Album name is required.')

    try:
        query_config = json.loads(query_config_raw)
    except json.JSONDecodeError:
        query_config = album.query_config
        errors.append('Invalid JSON in query configuration.')

    errors.extend(validate_query_config(query_config))

    existing = Album.query.filter_by(name=name).first()
    if existing and existing.id != album_id:
        errors.append(f'An album named "{name}" already exists.')

    if errors:
        for err in errors:
            flash(err, 'danger')
        return render_template('albums/form.html', album=album, action='edit',
                               form_data=request.form)

    album.name = name
    album.album_type = album_type
    album.query_config = query_config
    album.sync_enabled = sync_enabled
    album.sync_interval = int(sync_interval) if sync_interval else None
    db.session.commit()

    flash(f'Album "{name}" updated.', 'success')
    return redirect(url_for('albums.album_detail', album_id=album.id))


@bp.route('/albums/<album_id>/delete', methods=['POST'])
@login_required
def delete_album(album_id):
    """Delete an album (does not delete the album in Immich)."""
    album = Album.query.get_or_404(album_id)
    name = album.name
    db.session.delete(album)
    db.session.commit()
    flash(f'Album "{name}" deleted from this app (Immich album untouched).', 'success')
    return redirect(url_for('albums.list_albums'))


@bp.route('/albums/<album_id>/sync', methods=['POST'])
@login_required
def sync_album(album_id):
    """Manually trigger an album sync."""
    album = Album.query.get_or_404(album_id)

    try:
        from app.auth import get_immich_client
        from app.album_service import AlbumSyncService
        client = get_immich_client()
        result = AlbumSyncService(client).sync_album(album)

        if result['status'] == 'success':
            flash(
                f'Sync complete — {result["assets_added"]} added, '
                f'{result["assets_removed"]} removed.',
                'success',
            )
        else:
            flash(f'Sync failed: {result.get("error", "Unknown error")}', 'danger')
    except Exception as exc:
        current_app.logger.error(f'Sync error for album {album_id}: {exc}')
        flash(f'Sync error: {exc}', 'danger')

    next_url = request.args.get('next') or url_for('albums.album_detail', album_id=album_id)
    return redirect(next_url)

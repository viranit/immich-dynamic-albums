"""Album CRUD routes."""
import json
import uuid

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app, abort,
)
from flask_login import login_required, current_user
from flask_babel import gettext as _
from sqlalchemy import or_

from app import db
from app.models import Album, SyncLog
from app.utils.validators import validate_query_config

bp = Blueprint('albums', __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_immich_users():
    """Return the list of Immich users, or [] on any error."""
    try:
        from app.auth import get_immich_client
        return get_immich_client().get_users()
    except Exception:
        return []


def _check_album_access(album: Album):
    """Abort 403 if the current (non-admin) user doesn't own this album."""
    if current_user.is_admin:
        return
    # Legacy albums (NULL owner) are accessible to everyone
    if album.user_id is not None and album.user_id != current_user.id:
        abort(403)


def _apply_user_scoping(query_config: dict) -> dict:
    """Inject ``user_ids`` into *query_config* based on the current user's role.

    * **Admins**: respect whatever was submitted via the ``user_ids`` form field
      (already merged by the caller).  This function is a no-op for admins.
    * **Non-admins**: force ``user_ids`` to ``[current_user.immich_user_id]`` so
      that searches are always scoped to the logged-in user's library.
    """
    if current_user.is_admin:
        return query_config
    if current_user.immich_user_id:
        query_config['user_ids'] = [current_user.immich_user_id]
    else:
        # OIDC user without a linked Immich ID — cannot scope; leave empty
        query_config.pop('user_ids', None)
    return query_config


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route('/')
@login_required
def index():
    return redirect(url_for('albums.list_albums'))


@bp.route('/albums')
@login_required
def list_albums():
    """List albums. Admins see all; non-admins see only their own (+ legacy)."""
    if current_user.is_admin:
        all_albums = Album.query.order_by(Album.updated_at.desc()).all()
    else:
        all_albums = (
            Album.query
            .filter(or_(Album.user_id == current_user.id, Album.user_id.is_(None)))
            .order_by(Album.updated_at.desc())
            .all()
        )
    return render_template('albums/list.html', albums=all_albums)


@bp.route('/albums/new', methods=['GET', 'POST'])
@login_required
def new_album():
    """Create a new album."""
    if request.method == 'GET':
        immich_users = _get_immich_users() if current_user.is_admin else []
        return render_template(
            'albums/form.html',
            album=None,
            action='create',
            immich_users=immich_users,
            selected_user_ids=[],
            query_config_form_json='{}',
        )

    name = request.form.get('name', '').strip()
    album_type = request.form.get('album_type', 'dynamic')
    query_config_raw = request.form.get('query_config', '{}')
    sync_interval = request.form.get('sync_interval') or None

    errors = []
    if not name:
        errors.append(_('Album name is required.'))

    try:
        query_config = json.loads(query_config_raw)
    except json.JSONDecodeError:
        query_config = {}
        errors.append(_('Invalid JSON in query configuration.'))

    errors.extend(validate_query_config(query_config))

    if Album.query.filter_by(name=name).first():
        errors.append(_('An album named "%(name)s" already exists.', name=name))

    if errors:
        for err in errors:
            flash(err, 'danger')
        immich_users = _get_immich_users() if current_user.is_admin else []
        return render_template(
            'albums/form.html',
            album=None,
            action='create',
            form_data=request.form,
            immich_users=immich_users,
            selected_user_ids=request.form.getlist('user_ids'),
            query_config_form_json=query_config_raw,
        )

    # Merge admin-selected owner IDs then enforce non-admin scoping
    if current_user.is_admin:
        selected_uids = request.form.getlist('user_ids')
        if selected_uids:
            query_config['user_ids'] = selected_uids
    _apply_user_scoping(query_config)

    album = Album(
        id=str(uuid.uuid4()),
        name=name,
        album_type=album_type,
        query_config=query_config,
        sync_enabled=True,
        sync_interval=int(sync_interval) if sync_interval else None,
        user_id=current_user.id,
    )
    db.session.add(album)
    db.session.commit()

    flash(_('Album "%(name)s" created.', name=name), 'success')

    if album_type == 'static':
        return redirect(url_for('albums.sync_album', album_id=album.id,
                                next=url_for('albums.album_detail', album_id=album.id)))
    return redirect(url_for('albums.album_detail', album_id=album.id))


@bp.route('/albums/<album_id>')
@login_required
def album_detail(album_id):
    """Show album details and recent sync history."""
    album = Album.query.get_or_404(album_id)
    _check_album_access(album)

    sync_logs = (
        SyncLog.query
        .filter_by(album_id=album_id)
        .order_by(SyncLog.started_at.desc())
        .limit(20)
        .all()
    )

    # Build a name map for Immich user IDs stored in query_config.user_ids
    immich_users_map = {}
    if current_user.is_admin:
        for u in _get_immich_users():
            immich_users_map[u.get('id')] = u

    return render_template(
        'albums/detail.html',
        album=album,
        sync_logs=sync_logs,
        immich_users_map=immich_users_map,
    )


@bp.route('/albums/<album_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_album(album_id):
    """Edit an existing album."""
    album = Album.query.get_or_404(album_id)
    _check_album_access(album)

    if request.method == 'GET':
        q = dict(album.query_config or {})
        selected_user_ids = q.pop('user_ids', []) or []
        query_config_form_json = json.dumps(q)
        immich_users = _get_immich_users() if current_user.is_admin else []
        return render_template(
            'albums/form.html',
            album=album,
            action='edit',
            immich_users=immich_users,
            selected_user_ids=selected_user_ids,
            query_config_form_json=query_config_form_json,
        )

    name = request.form.get('name', '').strip()
    album_type = request.form.get('album_type', album.album_type)
    query_config_raw = request.form.get('query_config', '{}')
    sync_interval = request.form.get('sync_interval') or None
    sync_enabled = request.form.get('sync_enabled') == 'on'

    errors = []
    if not name:
        errors.append(_('Album name is required.'))

    try:
        query_config = json.loads(query_config_raw)
    except json.JSONDecodeError:
        query_config = album.query_config
        errors.append(_('Invalid JSON in query configuration.'))

    errors.extend(validate_query_config(query_config))

    existing = Album.query.filter_by(name=name).first()
    if existing and existing.id != album_id:
        errors.append(_('An album named "%(name)s" already exists.', name=name))

    if errors:
        for err in errors:
            flash(err, 'danger')
        immich_users = _get_immich_users() if current_user.is_admin else []
        return render_template(
            'albums/form.html',
            album=album,
            action='edit',
            form_data=request.form,
            immich_users=immich_users,
            selected_user_ids=request.form.getlist('user_ids'),
            query_config_form_json=query_config_raw,
        )

    # Merge admin-selected owner IDs then enforce non-admin scoping
    if current_user.is_admin:
        selected_uids = request.form.getlist('user_ids')
        if selected_uids:
            query_config['user_ids'] = selected_uids
        else:
            query_config.pop('user_ids', None)  # all users
    _apply_user_scoping(query_config)

    album.name = name
    album.album_type = album_type
    album.query_config = query_config
    album.sync_enabled = sync_enabled
    album.sync_interval = int(sync_interval) if sync_interval else None
    db.session.commit()

    flash(_('Album "%(name)s" updated.', name=name), 'success')
    return redirect(url_for('albums.album_detail', album_id=album.id))


@bp.route('/albums/<album_id>/delete', methods=['POST'])
@login_required
def delete_album(album_id):
    """Delete an album (does not delete the album in Immich)."""
    album = Album.query.get_or_404(album_id)
    _check_album_access(album)

    name = album.name
    db.session.delete(album)
    db.session.commit()
    flash(_('Album "%(name)s" deleted from this app (Immich album untouched).', name=name),
          'success')
    return redirect(url_for('albums.list_albums'))


@bp.route('/albums/<album_id>/sync', methods=['POST'])
@login_required
def sync_album(album_id):
    """Manually trigger an album sync."""
    album = Album.query.get_or_404(album_id)
    _check_album_access(album)

    try:
        from app.auth import get_immich_client
        from app.album_service import AlbumSyncService
        client = get_immich_client()
        result = AlbumSyncService(client).sync_album(album)

        if result['status'] == 'success':
            flash(
                _('Sync complete \u2014 %(added)s added, %(removed)s removed.',
                  added=result['assets_added'], removed=result['assets_removed']),
                'success',
            )
        else:
            flash(_('Sync failed: %(error)s', error=result.get('error', 'Unknown error')),
                  'danger')
    except Exception as exc:
        current_app.logger.error(f'Sync error for album {album_id}: {exc}')
        flash(_('Sync error: %(error)s', error=exc), 'danger')

    next_url = request.args.get('next') or url_for('albums.album_detail', album_id=album_id)
    return redirect(next_url)

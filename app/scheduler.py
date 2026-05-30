"""Scheduler for automatic album synchronization."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

scheduler = None
_flask_app = None  # stored reference to avoid circular import via run.py


def init_scheduler(app):
    """Initialize the background scheduler."""
    global scheduler, _flask_app
    _flask_app = app

    if scheduler is None:
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.start()
        app.logger.info('Scheduler started')

        with app.app_context():
            schedule_sync_jobs()


def schedule_sync_jobs():
    """(Re-)schedule synchronization jobs from current settings."""
    global scheduler
    if scheduler is None:
        return

    from app.models import Setting
    from flask import current_app

    scheduler.remove_all_jobs()

    interval_setting = Setting.query.get('global_sync_interval')
    global_interval = int(interval_setting.value) if interval_setting else 60

    enabled_setting = Setting.query.get('sync_enabled')
    sync_enabled = (enabled_setting.value.lower() == 'true') if enabled_setting else True

    if not sync_enabled or global_interval <= 0:
        current_app.logger.info('Automatic syncing is disabled or interval is 0')
        return

    scheduler.add_job(
        func=_run_sync_all_dynamic_albums,
        trigger=IntervalTrigger(minutes=global_interval),
        id='sync_all_dynamic',
        name='Sync all dynamic albums',
        replace_existing=True,
    )
    current_app.logger.info(f'Scheduled sync every {global_interval} minutes')


def _run_sync_all_dynamic_albums():
    """Entry point called by APScheduler; pushes a Flask app context."""
    if _flask_app is None:
        return
    with _flask_app.app_context():
        sync_all_dynamic_albums()


def sync_all_dynamic_albums():
    """Sync all enabled dynamic albums (must be called inside an app context)."""
    from app.models import Album
    from app.album_service import AlbumSyncService
    from app.auth import get_immich_client
    from flask import current_app

    albums = Album.query.filter_by(album_type='dynamic', sync_enabled=True).all()
    if not albums:
        current_app.logger.info('No dynamic albums to sync')
        return

    current_app.logger.info(f'Syncing {len(albums)} dynamic album(s)')
    immich_client = get_immich_client()
    sync_service = AlbumSyncService(immich_client)

    for album in albums:
        try:
            result = sync_service.sync_album(album)
            current_app.logger.info(f'Synced "{album.name}": {result}')
        except Exception as exc:
            current_app.logger.error(f'Failed to sync "{album.name}": {exc}')


def get_scheduler_status():
    """Return scheduler status dict for the API."""
    if scheduler is None or not scheduler.running:
        return {'running': False, 'jobs': []}
    return {
        'running': True,
        'jobs': [
            {
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in scheduler.get_jobs()
        ],
    }

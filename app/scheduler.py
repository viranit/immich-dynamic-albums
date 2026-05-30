"""Scheduler for automatic album synchronization."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask import current_app
from app import db
from app.models import Album, Setting
from app.album_service import AlbumSyncService
from app.auth import get_immich_client
import logging

scheduler = None


def init_scheduler(app):
    """Initialize the background scheduler."""
    global scheduler
    
    if scheduler is None:
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.start()
        app.logger.info("Scheduler started")
        
        # Schedule the sync job
        with app.app_context():
            schedule_sync_jobs()


def schedule_sync_jobs():
    """Schedule synchronization jobs for dynamic albums."""
    global scheduler
    
    if scheduler is None:
        return
    
    # Remove all existing jobs
    scheduler.remove_all_jobs()
    
    # Get global sync interval from settings (default: 60 minutes)
    interval_setting = Setting.query.get('global_sync_interval')
    global_interval = int(interval_setting.value) if interval_setting else 60
    
    # Check if syncing is enabled
    enabled_setting = Setting.query.get('sync_enabled')
    sync_enabled = enabled_setting.value.lower() == 'true' if enabled_setting else True
    
    if not sync_enabled:
        current_app.logger.info("Automatic syncing is disabled")
        return
    
    # Schedule global sync job
    scheduler.add_job(
        func=sync_all_dynamic_albums,
        trigger=IntervalTrigger(minutes=global_interval),
        id='sync_all_dynamic',
        name='Sync all dynamic albums',
        replace_existing=True
    )
    
    current_app.logger.info(f"Scheduled sync job with interval: {global_interval} minutes")


def sync_all_dynamic_albums():
    """Sync all enabled dynamic albums."""
    from run import app
    
    with app.app_context():
        try:
            # Get all enabled dynamic albums
            albums = Album.query.filter_by(
                album_type='dynamic',
                sync_enabled=True
            ).all()
            
            if not albums:
                current_app.logger.info("No dynamic albums to sync")
                return
            
            current_app.logger.info(f"Syncing {len(albums)} dynamic album(s)")
            
            # Get Immich client
            immich_client = get_immich_client()
            sync_service = AlbumSyncService(immich_client)
            
            # Sync each album
            for album in albums:
                try:
                    current_app.logger.info(f"Syncing album: {album.name}")
                    result = sync_service.sync_album(album)
                    current_app.logger.info(f"Sync result for {album.name}: {result}")
                except Exception as e:
                    current_app.logger.error(f"Failed to sync album {album.name}: {e}")
            
            current_app.logger.info("Sync completed")
            
        except Exception as e:
            current_app.logger.error(f"Sync job failed: {e}")


def trigger_manual_sync(album_id: str):
    """Manually trigger a sync for a specific album."""
    try:
        album = Album.query.get(album_id)
        if not album:
            raise ValueError(f"Album {album_id} not found")
        
        immich_client = get_immich_client()
        sync_service = AlbumSyncService(immich_client)
        
        result = sync_service.sync_album(album)
        return result
        
    except Exception as e:
        current_app.logger.error(f"Manual sync failed: {e}")
        raise

"""Unit tests for SQLAlchemy models."""
import pytest
from datetime import datetime, timezone

from app.models import Album, Setting, SyncLog, User


class TestAlbumModel:
    def test_create_dynamic_album(self, db):
        album = Album(
            name='My Dynamic Album',
            album_type='dynamic',
            query_config={'country': 'France'},
        )
        db.session.add(album)
        db.session.commit()
        fetched = db.session.get(Album, album.id)
        assert fetched.name == 'My Dynamic Album'
        assert fetched.album_type == 'dynamic'
        assert fetched.sync_enabled is True

    def test_create_static_album(self, db):
        album = Album(
            name='Static Vacation',
            album_type='static',
            query_config={'tags': ['holiday']},
            sync_enabled=False,
        )
        db.session.add(album)
        db.session.commit()
        assert db.session.get(Album, album.id).album_type == 'static'

    def test_to_dict_keys(self, db):
        album = Album(
            name='Dict Test',
            album_type='dynamic',
            query_config={'favorite': True},
        )
        db.session.add(album)
        db.session.commit()
        d = album.to_dict()
        expected_keys = {'id', 'name', 'album_type', 'query_config',
                         'immich_album_id', 'sync_enabled', 'sync_interval',
                         'last_synced', 'created_at', 'updated_at'}
        assert expected_keys.issubset(d.keys())

    def test_album_name_unique(self, db):
        db.session.add(Album(name='Unique', album_type='dynamic', query_config={}))
        db.session.commit()
        db.session.add(Album(name='Unique', album_type='static', query_config={}))
        with pytest.raises(Exception):
            db.session.commit()


class TestSettingModel:
    def test_create_setting(self, db):
        s = Setting(key='immich_url', value='http://localhost:2283')
        db.session.add(s)
        db.session.commit()
        assert db.session.get(Setting, 'immich_url').value == 'http://localhost:2283'

    def test_to_dict(self, db):
        s = Setting(key='test_key', value='test_val', description='A test setting')
        db.session.add(s)
        db.session.commit()
        d = s.to_dict()
        assert d['key'] == 'test_key'
        assert d['value'] == 'test_val'


class TestSyncLogModel:
    def test_sync_log_linked_to_album(self, db, sample_album):
        log = SyncLog(
            album_id=sample_album.id,
            status='success',
            assets_added=5,
            assets_removed=1,
        )
        db.session.add(log)
        db.session.commit()
        fetched = db.session.get(SyncLog, log.id)
        assert fetched.album_id == sample_album.id
        assert fetched.assets_added == 5

    def test_to_dict(self, db, sample_album):
        log = SyncLog(album_id=sample_album.id, status='error', error_message='timeout')
        db.session.add(log)
        db.session.commit()
        d = log.to_dict()
        assert d['status'] == 'error'
        assert d['error_message'] == 'timeout'


class TestUserModel:
    def test_flask_login_interface(self, db):
        user = User(
            username='alice',
            auth_method='oidc',
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        assert user.is_authenticated is True
        assert user.is_active is True
        assert user.get_id() == user.id

"""Integration tests for REST API routes."""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.models import Album


class TestApiAlbums:
    def test_list_albums(self, auth_client, sample_album):
        resp = auth_client.get('/api/albums')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert any(a['name'] == sample_album.name for a in data)

    def test_get_single_album(self, auth_client, sample_album):
        resp = auth_client.get(f'/api/albums/{sample_album.id}')
        assert resp.status_code == 200
        assert resp.get_json()['id'] == str(sample_album.id)

    def test_get_missing_album_404(self, auth_client):
        resp = auth_client.get('/api/albums/does-not-exist')
        assert resp.status_code == 404

    def test_create_album_via_api(self, auth_client, db):
        resp = auth_client.post('/api/albums', json={
            'name': 'API Album',
            'album_type': 'dynamic',
            'query_config': {'country': 'Brazil'},
        })
        assert resp.status_code == 201
        assert db.session.query(Album).filter_by(name='API Album').first() is not None

    def test_create_album_missing_name(self, auth_client):
        resp = auth_client.post('/api/albums', json={
            'album_type': 'dynamic',
            'query_config': {'country': 'Brazil'},
        })
        assert resp.status_code == 400

    def test_create_album_empty_query(self, auth_client):
        resp = auth_client.post('/api/albums', json={
            'name': 'Empty',
            'album_type': 'dynamic',
            'query_config': {},
        })
        assert resp.status_code == 400

    def test_update_album(self, auth_client, db, sample_album):
        resp = auth_client.put(f'/api/albums/{sample_album.id}', json={
            'name': 'Renamed via API',
        })
        assert resp.status_code == 200
        db.session.refresh(sample_album)
        assert sample_album.name == 'Renamed via API'

    def test_delete_album(self, auth_client, db, sample_album):
        album_id = sample_album.id
        resp = auth_client.delete(f'/api/albums/{album_id}')
        assert resp.status_code == 200
        assert db.session.get(Album, album_id) is None


class TestApiSync:
    def test_sync_album(self, auth_client, sample_album):
        with patch('app.routes.api.get_immich_client') as mock_get, \
             patch('app.routes.api.AlbumSyncService') as mock_svc:
            mock_svc.return_value.sync_album.return_value = {
                'status': 'success', 'assets_added': 5, 'assets_removed': 1
            }
            mock_get.return_value = MagicMock()
            resp = auth_client.post(f'/api/albums/{sample_album.id}/sync')
        assert resp.status_code == 200
        assert resp.get_json()['assets_added'] == 5


class TestApiSettings:
    def test_get_settings(self, auth_client, db):
        resp = auth_client.get('/api/settings')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), dict)

    def test_update_settings(self, auth_client, db):
        resp = auth_client.post('/api/settings', json={
            'immich_url': 'http://new-host:2283',
        })
        assert resp.status_code == 200

    def test_sensitive_setting_masked(self, auth_client, db):
        from app.models import Setting
        db.session.merge(Setting(key='immich_api_key', value='super-secret'))
        db.session.commit()
        resp = auth_client.get('/api/settings')
        data = resp.get_json()
        assert data.get('immich_api_key') != 'super-secret'


class TestApiScheduler:
    def test_scheduler_status(self, auth_client):
        resp = auth_client.get('/api/scheduler/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'running' in data


class TestApiImmichLookup:
    def test_get_people(self, auth_client):
        with patch('app.routes.api.get_immich_client') as mock_get:
            mock_get.return_value.get_people.return_value = [
                {'id': 'p1', 'name': 'Alice'}
            ]
            resp = auth_client.get('/api/immich/people')
        assert resp.status_code == 200
        people = resp.get_json()
        assert any(p['name'] == 'Alice' for p in people)

    def test_get_tags(self, auth_client):
        with patch('app.routes.api.get_immich_client') as mock_get:
            mock_get.return_value.get_tags.return_value = [
                {'id': 't1', 'name': 'holiday'}
            ]
            resp = auth_client.get('/api/immich/tags')
        assert resp.status_code == 200
        tags = resp.get_json()
        assert any(t['name'] == 'holiday' for t in tags)

    def test_people_returns_empty_when_no_client(self, auth_client):
        with patch('app.routes.api.get_immich_client', return_value=None):
            resp = auth_client.get('/api/immich/people')
        # Should return 200 with empty list or 503, both acceptable
        assert resp.status_code in (200, 503)

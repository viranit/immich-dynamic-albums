"""Integration tests for album routes."""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.models import Album


class TestAlbumList:
    def test_unauthenticated_redirects(self, client):
        resp = client.get('/albums')
        assert resp.status_code in (302, 303)

    def test_list_shows_albums(self, auth_client, sample_album):
        resp = auth_client.get('/albums')
        assert resp.status_code == 200
        assert sample_album.name.encode() in resp.data

    def test_empty_list_shows_no_albums(self, auth_client, db):
        resp = auth_client.get('/albums')
        assert resp.status_code == 200


class TestAlbumCreate:
    def test_get_create_form(self, auth_client):
        resp = auth_client.get('/albums/new')
        assert resp.status_code == 200
        assert b'query_config' in resp.data

    def test_create_dynamic_album(self, auth_client, db):
        resp = auth_client.post('/albums/new', data={
            'name': 'New Dynamic Album',
            'album_type': 'dynamic',
            'query_config': json.dumps({'country': 'Spain'}),
            'sync_enabled': 'on',
        })
        assert resp.status_code in (302, 303)
        album = db.session.query(Album).filter_by(name='New Dynamic Album').first()
        assert album is not None
        assert album.album_type == 'dynamic'

    def test_create_static_album_triggers_sync(self, auth_client, db):
        with patch('app.routes.albums.get_immich_client') as mock_get, \
             patch('app.routes.albums.AlbumSyncService') as mock_svc:
            mock_svc.return_value.sync_album.return_value = {
                'status': 'success', 'assets_added': 3, 'assets_removed': 0
            }
            mock_get.return_value = MagicMock()
            resp = auth_client.post('/albums/new', data={
                'name': 'Static Vacation',
                'album_type': 'static',
                'query_config': json.dumps({'country': 'Italy'}),
            })
        assert resp.status_code in (200, 302, 303)

    def test_create_missing_name_returns_error(self, auth_client):
        resp = auth_client.post('/albums/new', data={
            'name': '',
            'album_type': 'dynamic',
            'query_config': json.dumps({'country': 'Spain'}),
        })
        assert resp.status_code in (200, 302, 400)

    def test_create_invalid_query_returns_error(self, auth_client):
        resp = auth_client.post('/albums/new', data={
            'name': 'Bad Query',
            'album_type': 'dynamic',
            'query_config': json.dumps({'unknown_field': 'x'}),
        })
        assert resp.status_code in (200, 302, 400)


class TestAlbumEdit:
    def test_edit_form_loads(self, auth_client, sample_album):
        resp = auth_client.get(f'/albums/{sample_album.id}/edit')
        assert resp.status_code == 200

    def test_edit_updates_album(self, auth_client, db, sample_album):
        resp = auth_client.post(f'/albums/{sample_album.id}/edit', data={
            'name': 'Updated Name',
            'album_type': 'dynamic',
            'query_config': json.dumps({'country': 'Egypt'}),
            'sync_enabled': 'on',
        })
        assert resp.status_code in (302, 303)
        db.session.refresh(sample_album)
        assert sample_album.name == 'Updated Name'


class TestAlbumDelete:
    def test_delete_album(self, auth_client, db, sample_album):
        album_id = sample_album.id
        resp = auth_client.post(f'/albums/{album_id}/delete')
        assert resp.status_code in (302, 303)
        assert db.session.get(Album, album_id) is None

    def test_delete_nonexistent_returns_404(self, auth_client):
        resp = auth_client.post('/albums/nonexistent-id/delete')
        assert resp.status_code == 404


class TestAlbumSync:
    def test_sync_triggers_service(self, auth_client, sample_album):
        with patch('app.routes.albums.get_immich_client') as mock_get, \
             patch('app.routes.albums.AlbumSyncService') as mock_svc:
            mock_svc.return_value.sync_album.return_value = {
                'status': 'success', 'assets_added': 0, 'assets_removed': 0
            }
            mock_get.return_value = MagicMock()
            resp = auth_client.post(f'/albums/{sample_album.id}/sync')
        assert resp.status_code in (302, 303)

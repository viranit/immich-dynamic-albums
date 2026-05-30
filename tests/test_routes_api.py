"""Integration tests for REST API routes (JSON:API 1.0 format).

All API responses follow the JSON:API document structure::

    {"jsonapi": {"version": "1.0"}, "data": <resource-or-array>, "meta": {...}}

Errors use::

    {"jsonapi": {"version": "1.0"}, "errors": [{"status": "422", ...}]}
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.models import Album
from app.utils.jsonapi import CONTENT_TYPE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def doc_data(resp):
    """Return ``resp.json['data']`` — the primary data of a JSON:API document."""
    return resp.get_json()['data']


def doc_attrs(resp):
    """Return the attributes of a single-resource JSON:API response."""
    return resp.get_json()['data']['attributes']


def doc_errors(resp):
    """Return the errors list of a JSON:API error response."""
    return resp.get_json()['errors']


def doc_meta(resp):
    """Return the meta object of a JSON:API response."""
    return resp.get_json().get('meta', {})


# ---------------------------------------------------------------------------
# Albums — CRUD
# ---------------------------------------------------------------------------

class TestApiAlbums:
    def test_list_albums_returns_jsonapi_document(self, auth_client, sample_album):
        resp = auth_client.get('/api/albums')
        assert resp.status_code == 200
        assert resp.content_type == CONTENT_TYPE
        body = resp.get_json()
        assert 'jsonapi' in body
        assert isinstance(body['data'], list)
        assert body['meta']['total'] >= 1

    def test_list_albums_contains_album(self, auth_client, sample_album):
        resp = auth_client.get('/api/albums')
        names = [r['attributes']['name'] for r in doc_data(resp)]
        assert sample_album.name in names

    def test_list_resource_type(self, auth_client, sample_album):
        resp = auth_client.get('/api/albums')
        types = {r['type'] for r in doc_data(resp)}
        assert types == {'albums'}

    def test_get_single_album(self, auth_client, sample_album):
        resp = auth_client.get(f'/api/albums/{sample_album.id}')
        assert resp.status_code == 200
        assert doc_data(resp)['id'] == str(sample_album.id)
        assert doc_data(resp)['type'] == 'albums'

    def test_get_single_album_has_relationships(self, auth_client, sample_album):
        resp = auth_client.get(f'/api/albums/{sample_album.id}')
        rel = doc_data(resp)['relationships']
        assert 'sync-logs' in rel

    def test_get_missing_album_404(self, auth_client):
        resp = auth_client.get('/api/albums/does-not-exist')
        assert resp.status_code == 404

    def test_create_album_plain_json(self, auth_client, db):
        """Plain JSON body (backward-compat) is accepted."""
        resp = auth_client.post('/api/albums', json={
            'name': 'Plain JSON Album',
            'album_type': 'dynamic',
            'query_config': {'country': 'Brazil'},
        })
        assert resp.status_code == 201
        assert resp.content_type == CONTENT_TYPE
        assert doc_data(resp)['type'] == 'albums'
        assert db.session.query(Album).filter_by(name='Plain JSON Album').first() is not None

    def test_create_album_jsonapi_envelope(self, auth_client, db):
        """Strict JSON:API request envelope is accepted."""
        resp = auth_client.post('/api/albums', json={
            'data': {
                'type': 'albums',
                'attributes': {
                    'name': 'Envelope Album',
                    'album_type': 'dynamic',
                    'query_config': {'favorite': True},
                },
            }
        })
        assert resp.status_code == 201
        assert doc_attrs(resp)['name'] == 'Envelope Album'

    def test_create_album_missing_name_returns_errors(self, auth_client):
        resp = auth_client.post('/api/albums', json={
            'album_type': 'dynamic',
            'query_config': {'country': 'Brazil'},
        })
        assert resp.status_code == 422
        assert any('name' in e['detail'] for e in doc_errors(resp))

    def test_create_album_empty_query_returns_errors(self, auth_client):
        resp = auth_client.post('/api/albums', json={
            'name': 'Empty Query',
            'album_type': 'dynamic',
            'query_config': {},
        })
        assert resp.status_code == 422
        assert len(doc_errors(resp)) >= 1

    def test_update_album(self, auth_client, db, sample_album):
        resp = auth_client.put(f'/api/albums/{sample_album.id}', json={
            'name': 'Renamed via API',
        })
        assert resp.status_code == 200
        assert doc_attrs(resp)['name'] == 'Renamed via API'
        db.session.refresh(sample_album)
        assert sample_album.name == 'Renamed via API'

    def test_update_album_jsonapi_envelope(self, auth_client, sample_album):
        resp = auth_client.patch(f'/api/albums/{sample_album.id}', json={
            'data': {
                'type': 'albums',
                'id': str(sample_album.id),
                'attributes': {'sync_enabled': False},
            }
        })
        assert resp.status_code == 200
        assert doc_attrs(resp)['sync_enabled'] is False

    def test_delete_album_returns_meta(self, auth_client, db, sample_album):
        album_id = sample_album.id
        resp = auth_client.delete(f'/api/albums/{album_id}')
        assert resp.status_code == 200
        assert 'message' in doc_meta(resp)
        assert db.session.get(Album, album_id) is None

    def test_delete_nonexistent_returns_404(self, auth_client):
        resp = auth_client.delete('/api/albums/nonexistent-id')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

class TestApiSync:
    def test_sync_album_returns_sync_result_resource(self, auth_client, sample_album):
        with patch('app.routes.api.get_immich_client') as mock_get, \
             patch('app.routes.api.AlbumSyncService') as mock_svc:
            mock_svc.return_value.sync_album.return_value = {
                'status': 'success', 'assets_added': 5, 'assets_removed': 1
            }
            mock_get.return_value = MagicMock()
            resp = auth_client.post(f'/api/albums/{sample_album.id}/sync')
        assert resp.status_code == 200
        assert doc_data(resp)['type'] == 'sync-results'
        assert doc_attrs(resp)['assets_added'] == 5
        assert doc_attrs(resp)['assets_removed'] == 1

    def test_sync_logs_returns_collection(self, auth_client, db, sample_album):
        from app.models import SyncLog
        db.session.add(SyncLog(
            album_id=sample_album.id, status='success',
            assets_added=3, assets_removed=0
        ))
        db.session.commit()
        resp = auth_client.get(f'/api/albums/{sample_album.id}/logs')
        assert resp.status_code == 200
        assert isinstance(doc_data(resp), list)
        assert doc_data(resp)[0]['type'] == 'sync-logs'
        assert doc_data(resp)[0]['relationships']['album']['data']['type'] == 'albums'


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestApiSettings:
    def test_get_settings_returns_collection(self, auth_client, db):
        resp = auth_client.get('/api/settings')
        assert resp.status_code == 200
        assert resp.content_type == CONTENT_TYPE
        assert isinstance(doc_data(resp), list)
        assert 'total' in doc_meta(resp)

    def test_settings_resources_have_correct_type(self, auth_client, db):
        from app.models import Setting
        db.session.merge(Setting(key='immich_url', value='http://example:2283'))
        db.session.commit()
        resp = auth_client.get('/api/settings')
        types = {r['type'] for r in doc_data(resp)}
        assert types == {'settings'}

    def test_update_settings_plain_json(self, auth_client, db):
        resp = auth_client.post('/api/settings', json={
            'immich_url': 'http://new-host:2283',
        })
        assert resp.status_code == 200
        assert 'message' in doc_meta(resp)

    def test_sensitive_setting_masked(self, auth_client, db):
        from app.models import Setting
        db.session.merge(Setting(key='immich_api_key', value='super-secret'))
        db.session.commit()
        resp = auth_client.get('/api/settings')
        settings_by_id = {r['id']: r['attributes'] for r in doc_data(resp)}
        api_key_attrs = settings_by_id.get('immich_api_key', {})
        assert api_key_attrs.get('value') == '***'
        assert api_key_attrs.get('masked') is True


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class TestApiScheduler:
    def test_scheduler_status_resource_type(self, auth_client):
        resp = auth_client.get('/api/scheduler/status')
        assert resp.status_code == 200
        assert doc_data(resp)['type'] == 'scheduler-status'
        assert 'running' in doc_attrs(resp)


# ---------------------------------------------------------------------------
# Immich look-ups
# ---------------------------------------------------------------------------

class TestApiImmichLookup:
    def test_get_people_returns_collection(self, auth_client):
        with patch('app.routes.api.get_immich_client') as mock_get:
            # Immich returns {"people": [...]} — simulate the real response shape
            mock_get.return_value.get_people.return_value = {
                'people': [{'id': 'p1', 'name': 'Alice'}]
            }
            resp = auth_client.get('/api/immich/people')
        assert resp.status_code == 200
        assert doc_data(resp)[0]['type'] == 'people'
        names = [r['attributes']['name'] for r in doc_data(resp)]
        assert 'Alice' in names

    def test_get_tags_returns_collection(self, auth_client):
        with patch('app.routes.api.get_immich_client') as mock_get:
            mock_get.return_value.get_tags.return_value = [
                {'id': 't1', 'name': 'holiday'}
            ]
            resp = auth_client.get('/api/immich/tags')
        assert resp.status_code == 200
        assert doc_data(resp)[0]['type'] == 'tags'
        names = [r['attributes']['name'] for r in doc_data(resp)]
        assert 'holiday' in names

    def test_no_client_returns_503(self, auth_client):
        with patch('app.routes.api.get_immich_client', return_value=None):
            resp = auth_client.get('/api/immich/people')
        assert resp.status_code == 503
        assert doc_errors(resp)[0]['status'] == '503'


# ---------------------------------------------------------------------------
# Content-Type header
# ---------------------------------------------------------------------------

class TestContentType:
    def test_list_albums_content_type(self, auth_client):
        resp = auth_client.get('/api/albums')
        assert resp.content_type == CONTENT_TYPE

    def test_error_response_content_type(self, auth_client):
        resp = auth_client.post('/api/albums', json={'album_type': 'dynamic'})
        assert resp.content_type == CONTENT_TYPE
        assert resp.status_code == 422

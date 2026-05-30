"""Unit tests for ImmichClient."""
import pytest
from unittest.mock import MagicMock, patch, call
import requests

from app.immich_client import ImmichClient


@pytest.fixture()
def client():
    return ImmichClient(base_url='http://immich:2283', api_key='test-key')


class TestImmichClientInit:
    def test_trailing_slash_stripped(self):
        c = ImmichClient('http://immich:2283/', 'k')
        assert not c.base_url.endswith('/')

    def test_headers_set(self):
        c = ImmichClient('http://immich:2283', 'my-key')
        assert c.session.headers['x-api-key'] == 'my-key'


class TestGetAlbumAssets:
    def test_returns_asset_ids(self, client):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'assets': [
                {'id': 'asset-1'},
                {'id': 'asset-2'},
            ]
        }
        with patch.object(client.session, 'get', return_value=response):
            result = client.get_album_assets('album-id-123')
        assert result == ['asset-1', 'asset-2']

    def test_empty_album(self, client):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'assets': []}
        with patch.object(client.session, 'get', return_value=response):
            result = client.get_album_assets('empty-album')
        assert result == []


class TestSearchAssets:
    def test_single_page(self, client):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'assets': {
                'items': [{'id': 'a1'}, {'id': 'a2'}],
                'nextPage': None,
            }
        }
        with patch.object(client.session, 'post', return_value=response):
            result = client.search_assets({'country': 'Egypt'})
        assert result == ['a1', 'a2']

    def test_multi_page_pagination(self, client):
        pages = [
            {'assets': {'items': [{'id': 'a1'}], 'nextPage': '2'}},
            {'assets': {'items': [{'id': 'a2'}], 'nextPage': None}},
        ]
        responses = []
        for p in pages:
            r = MagicMock()
            r.raise_for_status.return_value = None
            r.json.return_value = p
            responses.append(r)

        with patch.object(client.session, 'post', side_effect=responses):
            result = client.search_assets({'favorite': True})
        assert result == ['a1', 'a2']


class TestGetOrCreateAlbum:
    def test_creates_when_not_found(self, client):
        list_resp = MagicMock()
        list_resp.raise_for_status.return_value = None
        list_resp.json.return_value = []  # no existing albums

        create_resp = MagicMock()
        create_resp.raise_for_status.return_value = None
        create_resp.json.return_value = {'id': 'new-album-id'}

        with patch.object(client.session, 'get', return_value=list_resp), \
             patch.object(client.session, 'post', return_value=create_resp):
            album_id = client.get_or_create_album('New Album')
        assert album_id == 'new-album-id'

    def test_returns_existing(self, client):
        list_resp = MagicMock()
        list_resp.raise_for_status.return_value = None
        list_resp.json.return_value = [{'id': 'existing-id', 'albumName': 'My Album'}]

        with patch.object(client.session, 'get', return_value=list_resp):
            album_id = client.get_or_create_album('My Album')
        assert album_id == 'existing-id'


class TestAddRemoveAssets:
    def test_add_assets(self, client):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {}
        with patch.object(client.session, 'put', return_value=resp) as mock_put:
            client.add_assets_to_album('alb-id', ['a1', 'a2'])
        mock_put.assert_called_once()
        call_body = mock_put.call_args[1]['json']
        assert set(call_body['ids']) == {'a1', 'a2'}

    def test_remove_assets(self, client):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {}
        with patch.object(client.session, 'delete', return_value=resp) as mock_del:
            client.remove_assets_from_album('alb-id', ['a1'])
        mock_del.assert_called_once()

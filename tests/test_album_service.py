"""Unit tests for AlbumSyncService."""
import pytest
from unittest.mock import MagicMock, patch

from app.album_service import AlbumSyncService
from app.models import Album, SyncLog


@pytest.fixture()
def service(db, mock_immich_client):
    return AlbumSyncService(mock_immich_client)


class TestQueryNormalization:
    def test_country_string_becomes_list(self, service):
        cfg = {'country': 'Egypt'}
        # _normalize_query returns a list of individual search dicts
        queries = service._config_query_to_search_queries(cfg)
        assert isinstance(queries, list)
        assert len(queries) >= 1
        # Each sub-query should carry the country
        assert all('country' in q for q in queries)

    def test_multiple_countries_expand(self, service):
        cfg = {'country': ['France', 'Egypt']}
        queries = service._config_query_to_search_queries(cfg)
        countries = [q['country'] for q in queries]
        assert 'France' in countries
        assert 'Egypt' in countries

    def test_multiple_timespans_expand(self, service):
        cfg = {
            'timespan': [
                {'start': '2023-01-01', 'end': '2023-06-30'},
                {'start': '2024-01-01', 'end': '2024-06-30'},
            ]
        }
        queries = service._config_query_to_search_queries(cfg)
        assert len(queries) == 2

    def test_favorite_flag_preserved(self, service):
        cfg = {'favorite': True, 'country': 'Japan'}
        queries = service._config_query_to_search_queries(cfg)
        assert all(q.get('isFavorite') is True for q in queries)


class TestSyncAlbum:
    def test_adds_new_assets(self, db, service, sample_album, mock_immich_client):
        mock_immich_client.get_album_assets.return_value = []  # empty album
        mock_immich_client.search_assets.return_value = ['new-asset-1', 'new-asset-2']
        mock_immich_client.get_or_create_album.return_value = 'immich-album-id'

        result = service.sync_album(sample_album)

        assert result['status'] == 'success'
        assert result['assets_added'] == 2
        assert result['assets_removed'] == 0
        mock_immich_client.add_assets_to_album.assert_called_once()

    def test_removes_missing_assets(self, db, service, sample_album, mock_immich_client):
        mock_immich_client.get_album_assets.return_value = ['stale-asset']
        mock_immich_client.search_assets.return_value = []  # nothing matches now
        mock_immich_client.get_or_create_album.return_value = 'immich-album-id'

        result = service.sync_album(sample_album)

        assert result['status'] == 'success'
        assert result['assets_removed'] == 1
        mock_immich_client.remove_assets_from_album.assert_called_once()

    def test_no_change_when_in_sync(self, db, service, sample_album, mock_immich_client):
        mock_immich_client.get_album_assets.return_value = ['asset-1']
        mock_immich_client.search_assets.return_value = ['asset-1']
        mock_immich_client.get_or_create_album.return_value = 'immich-album-id'

        result = service.sync_album(sample_album)

        assert result['assets_added'] == 0
        assert result['assets_removed'] == 0
        mock_immich_client.add_assets_to_album.assert_not_called()
        mock_immich_client.remove_assets_from_album.assert_not_called()

    def test_sync_log_written_on_success(self, db, service, sample_album, mock_immich_client):
        mock_immich_client.get_album_assets.return_value = []
        mock_immich_client.search_assets.return_value = ['x1']
        mock_immich_client.get_or_create_album.return_value = 'alb'

        service.sync_album(sample_album)

        log = db.session.query(SyncLog).filter_by(album_id=sample_album.id).first()
        assert log is not None
        assert log.status == 'success'

    def test_sync_log_written_on_error(self, db, service, sample_album, mock_immich_client):
        mock_immich_client.get_or_create_album.side_effect = Exception('connection refused')

        result = service.sync_album(sample_album)

        assert result['status'] == 'error'
        log = db.session.query(SyncLog).filter_by(album_id=sample_album.id).first()
        assert log.status == 'error'
        assert 'connection refused' in log.error_message

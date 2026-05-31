"""Tests for user scoping: admin sees all, non-admin sees only their own."""
import json
import pytest
from unittest.mock import patch

from app.models import Album, User
from app.album_service import AlbumSyncService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def user_album(db):
    """An album owned by the regular test user (id='test-user-uuid')."""
    album = Album(
        name='User Album',
        album_type='dynamic',
        query_config={'country': 'Egypt'},
        sync_enabled=True,
        user_id='test-user-uuid',
    )
    db.session.add(album)
    db.session.commit()
    return album


@pytest.fixture()
def other_user_album(db):
    """An album owned by *another* user."""
    other = User(
        id='other-user-uuid',
        username='otheruser',
        email='other@example.com',
        auth_method='immich',
        immich_user_id='immich-other-id',
        is_admin=False,
        is_active=True,
    )
    db.session.add(other)
    album = Album(
        name='Other Album',
        album_type='dynamic',
        query_config={'country': 'France'},
        sync_enabled=True,
        user_id='other-user-uuid',
    )
    db.session.add(album)
    db.session.commit()
    return album


@pytest.fixture()
def admin_album(db):
    """An album owned by the admin user (id='admin-user-uuid')."""
    album = Album(
        name='Admin Album',
        album_type='dynamic',
        query_config={'country': 'Germany', 'user_ids': ['immich-user-id', 'immich-other-id']},
        sync_enabled=True,
        user_id='admin-user-uuid',
    )
    db.session.add(album)
    db.session.commit()
    return album


# ---------------------------------------------------------------------------
# Album list scoping
# ---------------------------------------------------------------------------

class TestAlbumListScoping:
    def test_non_admin_sees_own_album(self, auth_client, user_album):
        resp = auth_client.get('/albums')
        assert resp.status_code == 200
        assert b'User Album' in resp.data

    def test_non_admin_does_not_see_other_users_album(self, auth_client, other_user_album):
        resp = auth_client.get('/albums')
        assert resp.status_code == 200
        assert b'Other Album' not in resp.data

    def test_admin_sees_all_albums(self, admin_client, user_album, other_user_album, admin_album):
        resp = admin_client.get('/albums')
        assert resp.status_code == 200
        body = resp.data
        assert b'User Album' in body
        assert b'Other Album' in body
        assert b'Admin Album' in body

    def test_non_admin_sees_legacy_album_without_owner(self, auth_client, sample_album):
        """Albums with NULL user_id (legacy) are visible to all users."""
        resp = auth_client.get('/albums')
        assert resp.status_code == 200
        assert b'Test Album' in resp.data


# ---------------------------------------------------------------------------
# Access control on individual album routes
# ---------------------------------------------------------------------------

class TestAlbumAccessControl:
    def test_non_admin_can_view_own_album(self, auth_client, user_album):
        resp = auth_client.get(f'/albums/{user_album.id}')
        assert resp.status_code == 200

    def test_non_admin_forbidden_from_other_users_album(self, auth_client, other_user_album):
        resp = auth_client.get(f'/albums/{other_user_album.id}')
        assert resp.status_code == 403

    def test_admin_can_view_any_album(self, admin_client, other_user_album):
        resp = admin_client.get(f'/albums/{other_user_album.id}')
        assert resp.status_code == 200

    def test_non_admin_forbidden_edit_other_album(self, auth_client, other_user_album):
        resp = auth_client.get(f'/albums/{other_user_album.id}/edit')
        assert resp.status_code == 403

    def test_non_admin_forbidden_delete_other_album(self, auth_client, other_user_album):
        resp = auth_client.post(f'/albums/{other_user_album.id}/delete')
        assert resp.status_code == 403

    def test_non_admin_forbidden_sync_other_album(self, auth_client, other_user_album):
        resp = auth_client.post(f'/albums/{other_user_album.id}/sync')
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Album creation: user_id ownership and auto-scoping
# ---------------------------------------------------------------------------

class TestAlbumCreationOwnership:
    def test_new_album_sets_user_id_for_non_admin(self, auth_client, db):
        """Albums created by non-admins are owned by the creating user."""
        resp = auth_client.post('/albums/new', data={
            'name': 'My Created Album',
            'album_type': 'dynamic',
            'query_config': json.dumps({'country': 'Egypt'}),
        })
        assert resp.status_code in (200, 302)
        album = Album.query.filter_by(name='My Created Album').first()
        assert album is not None
        assert album.user_id == 'test-user-uuid'

    def test_non_admin_query_config_gets_user_id_injected(self, auth_client, db):
        """Non-admin albums have their immich_user_id injected into query_config."""
        resp = auth_client.post('/albums/new', data={
            'name': 'Scoped Album',
            'album_type': 'dynamic',
            'query_config': json.dumps({'favorite': True}),
        })
        album = Album.query.filter_by(name='Scoped Album').first()
        assert album is not None
        assert album.query_config.get('user_ids') == ['immich-user-id']

    def test_admin_can_create_album_targeting_specific_users(self, admin_client, db):
        """Admin-created albums with selected user_ids store them in query_config."""
        resp = admin_client.post('/albums/new', data={
            'name': 'Admin Targeted Album',
            'album_type': 'dynamic',
            'query_config': json.dumps({'country': 'France'}),
            'user_ids': ['immich-user-id', 'immich-other-id'],
        })
        album = Album.query.filter_by(name='Admin Targeted Album').first()
        assert album is not None
        assert set(album.query_config.get('user_ids', [])) == {'immich-user-id', 'immich-other-id'}

    def test_admin_album_with_no_users_selected_has_no_user_ids(self, admin_client, db):
        """Admin album with no users selected searches all users (no user_ids key)."""
        resp = admin_client.post('/albums/new', data={
            'name': 'Admin All Users Album',
            'album_type': 'dynamic',
            'query_config': json.dumps({'country': 'Spain'}),
            # no user_ids submitted
        })
        album = Album.query.filter_by(name='Admin All Users Album').first()
        assert album is not None
        assert 'user_ids' not in album.query_config


# ---------------------------------------------------------------------------
# AlbumSyncService: user_id passed to Immich search
# ---------------------------------------------------------------------------

class TestAlbumServiceUserScoping:
    def test_user_ids_in_config_generates_per_user_searches(self, mock_immich_client):
        """When query_config contains user_ids, one search per user is executed."""
        mock_immich_client.search_assets.return_value = iter([])
        mock_immich_client.get_people.return_value = {'people': []}
        mock_immich_client.get_tags.return_value = []
        mock_immich_client.get_albums.return_value = []
        mock_immich_client.create_album.return_value = {'id': 'new-album-id'}
        mock_immich_client.get_album.return_value = {'assets': []}

        service = AlbumSyncService(mock_immich_client)
        queries = list(service._config_query_to_search_queries({
            'country': 'Egypt',
            'user_ids': ['uid-1', 'uid-2'],
        }))

        # Should produce 2 queries (one per user)
        assert len(queries) == 2
        user_id_values = {q.get('user_id') for q in queries}
        assert user_id_values == {'uid-1', 'uid-2'}

    def test_no_user_ids_produces_single_search_without_user_id(self):
        """When user_ids is absent, a single search with no userId filter is produced."""
        from unittest.mock import MagicMock
        service = AlbumSyncService(MagicMock())
        queries = list(service._config_query_to_search_queries({'country': 'Egypt'}))
        assert len(queries) == 1
        assert 'user_id' not in queries[0]

    def test_empty_user_ids_list_produces_no_filter(self):
        """An empty user_ids list is equivalent to no filter."""
        from unittest.mock import MagicMock
        service = AlbumSyncService(MagicMock())
        queries = list(service._config_query_to_search_queries({'user_ids': []}))
        assert len(queries) == 1
        assert 'user_id' not in queries[0]

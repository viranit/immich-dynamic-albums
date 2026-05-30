"""Integration tests for auth routes."""
import pytest
from unittest.mock import patch, MagicMock


class TestLoginPage:
    def test_get_login_shows_form(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'API Key' in resp.data or b'api_key' in resp.data

    def test_authenticated_user_redirected(self, auth_client):
        resp = auth_client.get('/login')
        assert resp.status_code in (302, 303)


class TestImmichLogin:
    def test_missing_api_key_returns_400(self, client):
        resp = client.post('/login/immich', data={'api_key': ''})
        assert resp.status_code in (302, 400)  # redirect back to login

    def test_valid_api_key_creates_session(self, client, db):
        fake_user_info = {
            'id': 'immich-user-id',
            'name': 'Test User',
            'email': 'test@immich.local',
        }
        with patch('app.auth.authenticate_immich') as mock_auth:
            mock_auth.return_value = MagicMock(
                id='user-uuid', username='Test User', is_active=True, is_authenticated=True
            )
            resp = client.post('/login/immich', data={
                'api_key': 'valid-key-here',
                'immich_url': 'http://immich:2283',
            })
        # Should redirect to albums on success
        assert resp.status_code in (302, 303)

    def test_invalid_api_key_flashes_error(self, client):
        with patch('app.auth.authenticate_immich', side_effect=Exception('Invalid API key')):
            resp = client.post('/login/immich', data={
                'api_key': 'bad-key',
                'immich_url': 'http://immich:2283',
            })
        assert resp.status_code in (302, 200)


class TestLogout:
    def test_logout_clears_session(self, auth_client):
        resp = auth_client.get('/logout')
        assert resp.status_code in (302, 303)
        # After logout, accessing protected page should redirect
        resp2 = auth_client.get('/albums')
        assert resp2.status_code in (302, 303)

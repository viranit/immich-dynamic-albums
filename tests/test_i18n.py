"""Tests for Flask-Babel i18n / locale selection."""
import pytest
from flask import session


# ---------------------------------------------------------------------------
# Locale detection
# ---------------------------------------------------------------------------

class TestDefaultLocale:
    def test_default_locale_is_english(self, client):
        """Without any locale preference, login page renders English text."""
        resp = client.get('/login')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'Sign in' in body or 'Immich' in body

    def test_accept_language_header_selects_locale(self, client):
        """Accept-Language: fr header should trigger French translation."""
        resp = client.get('/login', headers={'Accept-Language': 'fr,en;q=0.9'})
        assert resp.status_code == 200
        body = resp.data.decode()
        # French translation for "Sign in" is "Se connecter"
        assert 'Se connecter' in body or 'Connexion' in body


# ---------------------------------------------------------------------------
# /set-language/<locale> route
# ---------------------------------------------------------------------------

class TestSetLanguageRoute:
    def test_set_language_stores_locale_in_session(self, client):
        """Setting a supported locale stores it in the Flask session."""
        with client.session_transaction() as sess:
            sess.clear()

        resp = client.get('/set-language/fr')
        # Should redirect (302)
        assert resp.status_code == 302

        with client.session_transaction() as sess:
            assert sess.get('locale') == 'fr'

    def test_set_language_rejects_unsupported_locale(self, client):
        """An unsupported locale code should return 400 and not change session."""
        resp = client.get('/set-language/zz')
        assert resp.status_code == 400

        with client.session_transaction() as sess:
            assert sess.get('locale') != 'zz'

    def test_set_language_redirects_to_referrer(self, client):
        """After setting language, client is redirected (default to /)."""
        resp = client.get('/set-language/en')
        assert resp.status_code in (301, 302)

    def test_set_language_back_to_english(self, client):
        """Setting locale to 'en' should store 'en' in session."""
        with client.session_transaction() as sess:
            sess['locale'] = 'fr'

        resp = client.get('/set-language/en')
        assert resp.status_code == 302

        with client.session_transaction() as sess:
            assert sess.get('locale') == 'en'


# ---------------------------------------------------------------------------
# Template rendering in different locales
# ---------------------------------------------------------------------------

class TestLocaleTemplateRendering:
    def test_login_page_renders_in_french(self, client):
        """After switching to French, login page contains French text."""
        # Set locale via session first
        with client.session_transaction() as sess:
            sess['locale'] = 'fr'

        resp = client.get('/login')
        assert resp.status_code == 200
        body = resp.data.decode()
        # French login page must contain French translated strings
        assert 'Se connecter' in body or 'Connexion' in body or 'connecter' in body

    def test_login_page_has_lang_attribute_for_english(self, client):
        """HTML lang attribute should reflect the active locale."""
        with client.session_transaction() as sess:
            sess['locale'] = 'en'

        resp = client.get('/login')
        body = resp.data.decode()
        assert 'lang="en"' in body

    def test_login_page_has_lang_attribute_for_french(self, client):
        """HTML lang attribute should be 'fr' when French is active."""
        with client.session_transaction() as sess:
            sess['locale'] = 'fr'

        resp = client.get('/login')
        body = resp.data.decode()
        assert 'lang="fr"' in body


# ---------------------------------------------------------------------------
# Authenticated routes render without error in each locale
# ---------------------------------------------------------------------------

class TestAllTemplatesLocales:
    LOCALES = ['en', 'fr']

    @pytest.mark.parametrize('locale', LOCALES)
    def test_albums_list_renders_in_locale(self, auth_client, locale):
        """Albums list page must render without 500 in every supported locale."""
        with auth_client.session_transaction() as sess:
            sess['locale'] = locale

        resp = auth_client.get('/albums/')
        assert resp.status_code == 200

    @pytest.mark.parametrize('locale', LOCALES)
    def test_albums_new_renders_in_locale(self, auth_client, locale):
        """New-album form must render without 500 in every supported locale."""
        with auth_client.session_transaction() as sess:
            sess['locale'] = locale

        resp = auth_client.get('/albums/new')
        assert resp.status_code == 200

    @pytest.mark.parametrize('locale', LOCALES)
    def test_settings_renders_in_locale(self, auth_client, locale):
        """Settings page must render without 500 in every supported locale."""
        with auth_client.session_transaction() as sess:
            sess['locale'] = locale

        resp = auth_client.get('/settings/')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Language switcher in navbar
# ---------------------------------------------------------------------------

class TestLanguageSwitcher:
    def test_language_switcher_present_in_navbar(self, auth_client):
        """Authenticated pages must include the language-switcher dropdown."""
        resp = auth_client.get('/albums/')
        assert resp.status_code == 200
        body = resp.data.decode()
        # The switcher is only rendered when len(LANGUAGES) > 1; verify markup.
        assert 'bi-translate' in body or 'set-language' in body

    def test_language_switcher_links_correct_locales(self, auth_client):
        """Switcher dropdown must link to set-language/<locale> for each language."""
        resp = auth_client.get('/albums/')
        body = resp.data.decode()
        assert '/set-language/en' in body
        assert '/set-language/fr' in body

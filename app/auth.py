"""Authentication module."""
from datetime import datetime

from flask import current_app, session
from flask_login import login_user, logout_user
from authlib.integrations.flask_client import OAuth

from app import db, login_manager
from app.models import User, Setting
from app.immich_client import ImmichClient


oauth = OAuth()


def init_oauth(app):
    """Initialize OAuth for OIDC authentication."""
    oauth.init_app(app)

    if app.config.get('OIDC_DISCOVERY_URL'):
        oauth.register(
            name='oidc',
            client_id=app.config.get('OIDC_CLIENT_ID'),
            client_secret=app.config.get('OIDC_CLIENT_SECRET'),
            server_metadata_url=app.config.get('OIDC_DISCOVERY_URL'),
            client_kwargs={'scope': 'openid email profile'},
        )


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login."""
    return User.query.get(user_id)


def _get_immich_url() -> str:
    """Return the configured Immich server URL from Settings or app config."""
    setting = Setting.query.get('immich_url')
    return setting.value if setting else current_app.config.get('IMMICH_URL', '')


def _get_admin_api_key() -> str:
    """Return the admin API key from Settings or app config."""
    setting = Setting.query.get('immich_api_key')
    return setting.value if setting else current_app.config.get('IMMICH_API_KEY', '')


def authenticate_immich(email: str, password: str) -> 'User | None':
    """Authenticate a user with their Immich email + password.

    Flow:
    1. Call ``POST /api/auth/login`` on the Immich server to validate credentials.
       The user never needs to know the admin API key.
    2. The login response contains the user's identity (id, email, isAdmin).
    3. Upsert a local User row and refresh ``is_admin`` / ``immich_user_id``.
    4. Store the *admin* API key in the session so all subsequent Immich
       operations (search, album management) run with full admin privileges.
    """
    try:
        immich_url = _get_immich_url()
        if not immich_url:
            current_app.logger.error('Immich URL is not configured.')
            return None

        # Step 1 — validate credentials against Immich
        login_info = ImmichClient.login_with_password(immich_url, email, password)

        # Step 2 — upsert local user record
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                username=login_info.get('name') or email,
                email=email,
                auth_method='immich',
                is_active=True,
            )
            db.session.add(user)

        # Always refresh from live Immich data
        user.username = login_info.get('name') or email
        user.immich_user_id = login_info.get('userId')
        user.is_admin = bool(login_info.get('isAdmin', False))
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Step 3 — store admin API key + URL in session for later requests
        admin_api_key = _get_admin_api_key()
        session['immich_api_key'] = admin_api_key
        session['immich_url'] = immich_url

        return user

    except Exception as e:
        current_app.logger.error(f'Immich authentication failed: {e}')
        return None


def authenticate_oidc(user_info: dict) -> 'User | None':
    """Authenticate using OIDC.

    OIDC users are *not* automatically granted admin rights; set ``is_admin``
    manually in the database if needed.
    """
    try:
        username = user_info.get('preferred_username') or user_info.get('email')
        email = user_info.get('email')

        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(
                username=username,
                email=email,
                auth_method='oidc',
                is_active=True,
                is_admin=False,
            )
            db.session.add(user)

        user.last_login = datetime.utcnow()
        db.session.commit()

        return user

    except Exception as e:
        current_app.logger.error(f'OIDC authentication failed: {e}')
        return None


def get_immich_client() -> ImmichClient:
    """Return an ImmichClient for the current session or global settings."""
    api_key = session.get('immich_api_key')
    if not api_key:
        api_key_setting = Setting.query.get('immich_api_key')
        api_key = api_key_setting.value if api_key_setting else current_app.config.get('IMMICH_API_KEY')

    immich_url = session.get('immich_url')
    if not immich_url:
        immich_url_setting = Setting.query.get('immich_url')
        immich_url = immich_url_setting.value if immich_url_setting else current_app.config['IMMICH_URL']

    return ImmichClient(immich_url, api_key)

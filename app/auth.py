"""Authentication module."""
from flask import current_app, redirect, url_for, session, request
from flask_login import login_user, logout_user
from authlib.integrations.flask_client import OAuth
from app import db, login_manager
from app.models import User, Setting
from app.immich_client import ImmichClient
from datetime import datetime


oauth = OAuth()


def init_oauth(app):
    """Initialize OAuth for OIDC authentication."""
    oauth.init_app(app)
    
    # Register OIDC provider
    if app.config.get('OIDC_DISCOVERY_URL'):
        oauth.register(
            name='oidc',
            client_id=app.config.get('OIDC_CLIENT_ID'),
            client_secret=app.config.get('OIDC_CLIENT_SECRET'),
            server_metadata_url=app.config.get('OIDC_DISCOVERY_URL'),
            client_kwargs={'scope': 'openid email profile'}
        )


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login."""
    return User.query.get(user_id)


def authenticate_immich(api_key: str) -> User:
    """Authenticate using Immich API key."""
    try:
        # Get Immich URL from settings or config
        immich_url_setting = Setting.query.get('immich_url')
        immich_url = immich_url_setting.value if immich_url_setting else current_app.config['IMMICH_URL']
        
        # Create Immich client and verify credentials
        client = ImmichClient(immich_url, api_key)
        user_info = client.whoami()
        
        # Find or create user
        user = User.query.filter_by(username=user_info['email']).first()
        if not user:
            user = User(
                username=user_info['email'],
                email=user_info['email'],
                auth_method='immich',
                is_active=True
            )
            db.session.add(user)
        
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Store API key in session (encrypted in production)
        session['immich_api_key'] = api_key
        session['immich_url'] = immich_url
        
        return user
        
    except Exception as e:
        current_app.logger.error(f"Immich authentication failed: {e}")
        return None


def authenticate_oidc(user_info: dict) -> User:
    """Authenticate using OIDC."""
    try:
        # Extract user information
        username = user_info.get('preferred_username') or user_info.get('email')
        email = user_info.get('email')
        
        # Find or create user
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(
                username=username,
                email=email,
                auth_method='oidc',
                is_active=True
            )
            db.session.add(user)
        
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return user
        
    except Exception as e:
        current_app.logger.error(f"OIDC authentication failed: {e}")
        return None


def get_immich_client() -> ImmichClient:
    """Get Immich client for the current session."""
    api_key = session.get('immich_api_key')
    if not api_key:
        # Try to get from settings
        api_key_setting = Setting.query.get('immich_api_key')
        if api_key_setting:
            api_key = api_key_setting.value
        else:
            api_key = current_app.config.get('IMMICH_API_KEY')
    
    immich_url = session.get('immich_url')
    if not immich_url:
        immich_url_setting = Setting.query.get('immich_url')
        if immich_url_setting:
            immich_url = immich_url_setting.value
        else:
            immich_url = current_app.config['IMMICH_URL']
    
    return ImmichClient(immich_url, api_key)

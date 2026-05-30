"""Application configuration."""
import os
from datetime import timedelta


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-please-change'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://immich_albums:immich_albums@localhost:5432/immich_albums'

    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Auth configuration
    AUTH_METHOD = os.environ.get('AUTH_METHOD', 'immich')  # 'immich' | 'oidc' | 'both'

    # OIDC configuration
    OIDC_CLIENT_ID = os.environ.get('OIDC_CLIENT_ID')
    OIDC_CLIENT_SECRET = os.environ.get('OIDC_CLIENT_SECRET')
    OIDC_DISCOVERY_URL = os.environ.get('OIDC_DISCOVERY_URL')
    OIDC_REDIRECT_URI = os.environ.get('OIDC_REDIRECT_URI')

    # Immich configuration (can be overridden via the settings page)
    IMMICH_URL = os.environ.get('IMMICH_URL', 'http://localhost:2283')
    IMMICH_API_KEY = os.environ.get('IMMICH_API_KEY')

    # Scheduler configuration
    SCHEDULER_API_ENABLED = True

    # Internationalisation
    LANGUAGES = {
        'en': 'English',
        'fr': 'Fran\u00e7ais',
    }
    BABEL_DEFAULT_LOCALE = os.environ.get('BABEL_DEFAULT_LOCALE', 'en')
    BABEL_DEFAULT_TIMEZONE = os.environ.get('BABEL_DEFAULT_TIMEZONE', 'UTC')

    @staticmethod
    def init_app(app):
        """Perform any app-level initialisation that requires the app object."""
        pass


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    # pytest.ini overrides DATABASE_URL to sqlite:///:memory:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///:memory:')


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}

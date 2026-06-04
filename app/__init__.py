"""Flask application factory."""
from flask import Flask, session, request as flask_request
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_babel import Babel

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
babel = Babel()


def get_locale():
    """Select the best locale for the current request.

    Priority order:
    1. Explicit language chosen by the user (stored in the session).
    2. Best match from the browser's ``Accept-Language`` header.
    3. Application default (``BABEL_DEFAULT_LOCALE``).
    """
    from flask import current_app
    try:
        supported = list(current_app.config.get('LANGUAGES', {'en': 'English'}).keys())
        locale = session.get('locale')
        if locale and locale in supported:
            return locale
        return flask_request.accept_languages.best_match(supported) or 'en'
    except RuntimeError:
        # Outside of a request context (e.g. background jobs) — use the default.
        return 'en'


def create_app(config_name='default'):
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Load configuration
    from app.config import config
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    babel.init_app(app, locale_selector=get_locale)

    # Initialize OAuth (must happen before blueprint registration)
    from app.auth import init_oauth
    init_oauth(app)

    # Register blueprints
    from app.routes import auth, albums, settings, api
    app.register_blueprint(auth.bp)
    app.register_blueprint(albums.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(api.bp, url_prefix='/api')

    # Language-switching endpoint (no login required — just sets a session cookie)
    @app.route('/set-language/<locale>')
    def set_language(locale):
        from flask import redirect, abort
        if locale in app.config.get('LANGUAGES', {}):
            session['locale'] = locale
        else:
            abort(400)
        return redirect(flask_request.referrer or '/')

    # Inject i18n helpers into every Jinja2 template context
    @app.context_processor
    def inject_i18n():
        from flask_babel import get_locale as _get_locale
        return {
            'current_locale': str(_get_locale()),
            'languages': app.config.get('LANGUAGES', {'en': 'English'}),
        }

    # Setup background scheduler
    from app.scheduler import init_scheduler
    init_scheduler(app)

    return app

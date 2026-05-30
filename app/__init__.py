"""Flask application factory."""
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


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
    
    # Register blueprints
    from app.routes import auth, albums, settings, api
    app.register_blueprint(auth.bp)
    app.register_blueprint(albums.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(api.bp, url_prefix='/api')
    
    # Setup scheduler
    from app.scheduler import init_scheduler
    init_scheduler(app)
    
    return app

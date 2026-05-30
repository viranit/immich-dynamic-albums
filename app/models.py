"""Database models."""
import uuid
from datetime import datetime
from app import db


class Album(db.Model):
    """Album model for storing both static and dynamic album configurations."""
    __tablename__ = 'albums'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), unique=True, nullable=False)
    album_type = db.Column(db.String(10), nullable=False)  # 'static' or 'dynamic'
    query_config = db.Column(db.JSON, nullable=False)  # Stores the query criteria
    immich_album_id = db.Column(db.String(255), nullable=True)  # ID in Immich
    sync_enabled = db.Column(db.Boolean, default=True)  # For dynamic albums
    sync_interval = db.Column(db.Integer, nullable=True)  # Minutes, null = use global
    last_synced = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sync_logs = db.relationship('SyncLog', backref='album', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert album to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'album_type': self.album_type,
            'query_config': self.query_config,
            'immich_album_id': self.immich_album_id,
            'sync_enabled': self.sync_enabled,
            'sync_interval': self.sync_interval,
            'last_synced': self.last_synced.isoformat() if self.last_synced else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Setting(db.Model):
    """Settings model for storing application configuration."""
    __tablename__ = 'settings'
    
    key = db.Column(db.String(255), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert setting to dictionary."""
        return {
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'updated_at': self.updated_at.isoformat()
        }


class SyncLog(db.Model):
    """Sync log model for tracking album synchronization history."""
    __tablename__ = 'sync_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    album_id = db.Column(db.String(36), db.ForeignKey('albums.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='running')  # running, success, error
    assets_added = db.Column(db.Integer, default=0)
    assets_removed = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        """Convert sync log to dictionary."""
        return {
            'id': self.id,
            'album_id': self.album_id,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'assets_added': self.assets_added,
            'assets_removed': self.assets_removed,
            'error_message': self.error_message
        }


class User(db.Model):
    """User model for authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    auth_method = db.Column(db.String(20), nullable=False)  # 'immich' or 'oidc'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return self.id
    
    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'auth_method': self.auth_method,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

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
    query_config = db.Column(db.JSON, nullable=False)
    immich_album_id = db.Column(db.String(255), nullable=True)
    sync_enabled = db.Column(db.Boolean, default=True)
    sync_interval = db.Column(db.Integer, nullable=True)  # minutes; None = use global
    last_synced = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Owner: the app-user who created this album (NULL = legacy / shared)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    owner = db.relationship('User', back_populates='albums')

    sync_logs = db.relationship(
        'SyncLog', backref='album', lazy='dynamic', cascade='all, delete-orphan'
    )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'album_type': self.album_type,
            'query_config': self.query_config,
            'immich_album_id': self.immich_album_id,
            'sync_enabled': self.sync_enabled,
            'sync_interval': self.sync_interval,
            'last_synced': self.last_synced.isoformat() if self.last_synced else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user_id': self.user_id,
        }

    def to_jsonapi_resource(self) -> dict:
        """Return a JSON:API resource object for this album."""
        from app.utils.jsonapi import resource
        return resource(
            type_='albums',
            id_=self.id,
            attributes={
                'name': self.name,
                'album_type': self.album_type,
                'query_config': self.query_config,
                'immich_album_id': self.immich_album_id,
                'sync_enabled': self.sync_enabled,
                'sync_interval': self.sync_interval,
                'last_synced': self.last_synced.isoformat() if self.last_synced else None,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            },
            relationships={
                'sync-logs': {
                    'links': {'related': f'/api/albums/{self.id}/logs'},
                },
                'owner': {
                    'data': {'type': 'users', 'id': self.user_id} if self.user_id else None,
                },
            },
            links={'self': f'/api/albums/{self.id}'},
        )


class Setting(db.Model):
    """Key-value store for application configuration."""
    __tablename__ = 'settings'

    key = db.Column(db.String(255), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_jsonapi_resource(self, mask_value: bool = False) -> dict:
        """Return a JSON:API resource object for this setting.

        :param mask_value: When ``True`` the ``value`` attribute is replaced
            with ``'***'`` (used for sensitive keys such as API secrets).
        """
        from app.utils.jsonapi import resource
        return resource(
            type_='settings',
            id_=self.key,
            attributes={
                'value': '***' if mask_value else self.value,
                'description': self.description,
                'masked': mask_value,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            },
            links={'self': f'/api/settings/{self.key}'},
        )


class SyncLog(db.Model):
    """Per-sync audit record."""
    __tablename__ = 'sync_logs'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    album_id = db.Column(db.String(36), db.ForeignKey('albums.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='running')
    assets_added = db.Column(db.Integer, default=0)
    assets_removed = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'album_id': self.album_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'assets_added': self.assets_added,
            'assets_removed': self.assets_removed,
            'error_message': self.error_message,
        }

    def to_jsonapi_resource(self) -> dict:
        """Return a JSON:API resource object for this sync log entry."""
        from app.utils.jsonapi import resource
        return resource(
            type_='sync-logs',
            id_=self.id,
            attributes={
                'started_at': self.started_at.isoformat() if self.started_at else None,
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                'status': self.status,
                'assets_added': self.assets_added,
                'assets_removed': self.assets_removed,
                'error_message': self.error_message,
            },
            relationships={
                'album': {
                    'data': {'type': 'albums', 'id': self.album_id},
                    'links': {'related': f'/api/albums/{self.album_id}'},
                },
            },
        )


class User(db.Model):
    """User model for Flask-Login."""
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    auth_method = db.Column(db.String(20), nullable=False)  # 'immich' or 'oidc'
    immich_user_id = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    albums = db.relationship('Album', back_populates='owner', lazy='dynamic')

    # Flask-Login interface
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'auth_method': self.auth_method,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }

    def to_jsonapi_resource(self) -> dict:
        """Return a JSON:API resource object for this user."""
        from app.utils.jsonapi import resource
        return resource(
            type_='users',
            id_=self.id,
            attributes={
                'username': self.username,
                'email': self.email,
                'auth_method': self.auth_method,
                'is_admin': self.is_admin,
                'is_active': self.is_active,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'last_login': self.last_login.isoformat() if self.last_login else None,
            },
            links={'self': f'/api/users/{self.id}'},
        )

"""Shared pytest fixtures."""
import pytest
from unittest.mock import MagicMock, patch

from app import create_app, db as _db
from app.models import Album, Setting, SyncLog, User


@pytest.fixture(scope='session')
def app():
    """Create application with an in-memory SQLite test database.

    The scheduler is disabled via TestingConfig so daemon threads don't
    keep the process alive after the test session finishes.
    """
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture()
def db(app):
    """Provide a clean database transaction per test (rollback on teardown)."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        _db.session.bind = connection  # type: ignore[attr-defined]
        yield _db
        _db.session.remove()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(app):
    """Flask test client (unauthenticated)."""
    return app.test_client()


@pytest.fixture()
def auth_client(app, db):
    """A test client already logged in as a regular (non-admin) Immich user."""
    user = User(
        id='test-user-uuid',
        username='testuser',
        email='test@example.com',
        auth_method='immich',
        immich_user_id='immich-user-id',
        is_admin=False,
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = user.id
        sess['immich_api_key'] = 'test-api-key'
    return client


@pytest.fixture()
def admin_client(app, db):
    """A test client already logged in as an admin Immich user."""
    user = User(
        id='admin-user-uuid',
        username='adminuser',
        email='admin@example.com',
        auth_method='immich',
        immich_user_id='immich-admin-id',
        is_admin=True,
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = user.id
        sess['immich_api_key'] = 'test-admin-key'
    return client


@pytest.fixture()
def mock_immich_client():
    """Return a MagicMock that mimics ImmichClient."""
    mock = MagicMock()
    mock.get_album_assets.return_value = []
    mock.search_assets.return_value = []
    mock.get_or_create_album.return_value = 'album-uuid-1234'
    mock.add_assets_to_album.return_value = None
    mock.remove_assets_from_album.return_value = None
    mock.get_people.return_value = {'people': []}
    mock.get_tags.return_value = []
    mock.get_users.return_value = [
        {'id': 'immich-user-id', 'name': 'Test User', 'email': 'test@example.com', 'isAdmin': False},
        {'id': 'immich-admin-id', 'name': 'Admin User', 'email': 'admin@example.com', 'isAdmin': True},
    ]
    return mock


@pytest.fixture()
def sample_album(db):
    """Insert and return a sample dynamic album (no owner = legacy)."""
    album = Album(
        name='Test Album',
        album_type='dynamic',
        query_config={'country': 'Egypt', 'favorite': True},
        sync_enabled=True,
    )
    db.session.add(album)
    db.session.commit()
    return album

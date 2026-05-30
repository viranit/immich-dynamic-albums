"""Shared pytest fixtures."""
import pytest
from unittest.mock import MagicMock, patch

from app import create_app, db as _db
from app.models import Album, Setting, SyncLog, User


@pytest.fixture(scope='session')
def app():
    """Create application with an in-memory SQLite test database."""
    app = create_app('testing')
    with app.app_context():
        _db.create_all()
        yield app
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
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def auth_client(app, db):
    """A test client already logged in as a dummy Immich user."""
    # Insert a user and log in via the test client
    user = User(
        id='test-user-uuid',
        username='testuser',
        email='test@example.com',
        auth_method='immich',
        immich_user_id='immich-user-id',
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
def mock_immich_client():
    """Return a MagicMock that mimics ImmichClient."""
    mock = MagicMock()
    mock.get_album_assets.return_value = []
    mock.search_assets.return_value = []
    mock.get_or_create_album.return_value = 'album-uuid-1234'
    mock.add_assets_to_album.return_value = None
    mock.remove_assets_from_album.return_value = None
    mock.get_people.return_value = []
    mock.get_tags.return_value = []
    return mock


@pytest.fixture()
def sample_album(db):
    """Insert and return a sample dynamic album."""
    album = Album(
        name='Test Album',
        album_type='dynamic',
        query_config={'country': 'Egypt', 'favorite': True},
        sync_enabled=True,
    )
    db.session.add(album)
    db.session.commit()
    return album

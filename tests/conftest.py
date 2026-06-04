"""Shared pytest fixtures."""
import os
import subprocess
import pytest
from unittest.mock import MagicMock

from app import create_app, db as _db
from app.models import Album, Setting, SyncLog, User


@pytest.fixture(scope='session', autouse=True)
def _compile_translations():
    """Compile .po → .mo translation files once per test session.

    Flask-Babel reads compiled .mo files at runtime; without them the
    French locale tests produce untranslated English strings.  Running
    pybabel compile here avoids committing binary .mo files to the repo.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run(
        ['pybabel', 'compile', '-d', 'app/translations', '--use-fuzzy'],
        cwd=project_root,
        check=False,
        capture_output=True,
    )


@pytest.fixture(scope='session')
def app():
    """Create application with an in-memory SQLite test database.

    The scheduler is disabled via TestingConfig so daemon threads don't
    keep the process alive after the test session finishes.

    Important: we do NOT keep an app_context active during 'yield'.
    Flask 3.x stores 'g' on the AppContext; a persistent context causes
    Flask-Babel to cache the locale from the first request on g._flask_babel
    and reuse it for all subsequent requests, breaking per-request locale
    detection.  Closing the setup context before yielding ensures every
    client.get() creates a fresh AppContext with a clean 'g'.
    """
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
    yield application
    with application.app_context():
        _db.drop_all()


@pytest.fixture()
def db(app):
    """Provide a clean database state per test.

    SQLAlchemy 2.x removed ``session.bind`` so the old nested-transaction
    rollback trick no longer works.  Instead we truncate all tables after
    each test using plain DELETE statements inside an app context.
    """
    with app.app_context():
        yield _db
        _db.session.remove()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


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
    """Return a MagicMock that mimics ImmichClient.

    Method return values match the real ImmichClient API so that
    AlbumSyncService can exercise its full logic without a live Immich server.
    """
    mock = MagicMock()

    # Mappings / metadata
    mock.get_people.return_value = {'people': []}
    mock.get_tags.return_value = []
    mock.get_users.return_value = [
        {'id': 'immich-user-id', 'name': 'Test User', 'email': 'test@example.com', 'isAdmin': False},
        {'id': 'immich-admin-id', 'name': 'Admin User', 'email': 'admin@example.com', 'isAdmin': True},
    ]

    # Album management
    mock.get_albums.return_value = []  # no pre-existing albums → create path
    mock.create_album.return_value = {'id': 'immich-album-id', 'albumName': 'Test Album'}
    # get_album(id, with_assets=True) returns album dict with assets list
    mock.get_album.return_value = {'id': 'immich-album-id', 'albumName': 'Test Album', 'assets': []}

    # Asset search: each element is a dict with at least an 'id' key
    mock.search_assets.return_value = []

    # Mutation helpers
    mock.add_assets_to_album.return_value = None
    mock.delete_assets_from_album.return_value = None

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

"""Immich API client - refactored from original sync.py."""
from typing import Any, Dict, Iterable, List, Optional
from datetime import datetime
import requests


class ImmichClient:
    """Client for interacting with Immich API."""

    def __init__(self, immich_url: str = None, api_key: str = '',
                 *, base_url: str = None) -> None:
        # Accept base_url as a keyword-only alias for backward compatibility
        if base_url is not None and immich_url is None:
            immich_url = base_url
        self.immich_url = (immich_url or '').rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'x-api-key': self.api_key,
        })

    @property
    def base_url(self) -> str:
        """Alias for immich_url (backward compatibility)."""
        return self.immich_url

    # ------------------------------------------------------------------
    # Credential-based login (used only during authentication; does NOT
    # require an existing API key on the client instance).
    # ------------------------------------------------------------------

    @staticmethod
    def login_with_password(immich_url: str, email: str, password: str) -> Dict:
        """Authenticate against Immich with email + password.

        Calls ``POST /api/auth/login`` and returns the response dict which
        includes ``accessToken``, ``userId``, ``userEmail``, ``name``,
        ``isAdmin``, etc.

        Raises ``requests.HTTPError`` on bad credentials (401) or any other
        HTTP failure.
        """
        url = immich_url.rstrip('/') + '/api/auth/login'
        resp = requests.post(
            url,
            json={'email': email, 'password': password},
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # User / admin endpoints
    # ------------------------------------------------------------------

    def whoami(self):
        """Get current authenticated user information."""
        return self._get('/api/users/me')

    def version(self):
        """Get Immich server version."""
        return self._get('/api/server/version')

    def get_users(self) -> List[Dict]:
        """List all Immich users. Requires an admin API key."""
        return self._get('/api/users')

    def get_people(self):
        """Get all people from Immich."""
        return self._get('/api/people?size=1000&withHidden=false')

    def get_tags(self):
        """Get all tags from Immich."""
        return self._get('/api/tags')

    def get_albums(self):
        """Get all albums from Immich."""
        return self._get('/api/albums')

    def get_album(self, album_id: str, with_assets: bool = False):
        """Get a specific album."""
        without = 'true' if not with_assets else 'false'
        return self._get(f'/api/albums/{album_id}?withoutAssets={without}')

    def get_album_assets(self, album_id: str) -> List[str]:
        """Return a list of asset IDs contained in *album_id*."""
        album = self.get_album(album_id, with_assets=True)
        return [a['id'] for a in album.get('assets', [])]

    def get_or_create_album(self, name: str) -> str:
        """Return the Immich album ID for *name*, creating it if absent."""
        for album in self.get_albums():
            if album.get('albumName') == name:
                return album['id']
        created = self.create_album(name)
        return created['id']

    def create_album(self, name: str, description: str = None):
        """Create a new album in Immich."""
        params = {'albumName': name}
        if description:
            params['description'] = description
        return self._post('/api/albums', params)

    def delete_assets_from_album(self, album_id: str, assets_ids: List[str]):
        """Remove assets from an album."""
        return self._delete(f'/api/albums/{album_id}/assets', {'ids': assets_ids})

    def remove_assets_from_album(self, album_id: str, asset_ids: List[str]):
        """Alias for delete_assets_from_album."""
        return self.delete_assets_from_album(album_id, asset_ids)

    def add_assets_to_album(self, album_id: str, assets_ids: List[str]):
        """Add assets to an album."""
        return self._put(f'/api/albums/{album_id}/assets', {'ids': assets_ids})

    def search_assets(self, **search_params) -> Iterable:
        """Search for assets matching *search_params*, yielding full asset dicts."""
        page = None
        while True:
            search_result = self.search(page=page, **search_params)
            assets_result = search_result['assets']

            yield from assets_result['items']

            next_page = assets_result.get('nextPage')
            if not next_page:
                break

            page = int(next_page)

    def search(
        self,
        country: str = None,
        state: str = None,
        city: str = None,
        path: str = None,
        before: datetime = None,
        after: datetime = None,
        favorite: bool = None,
        person_ids: List[str] = None,
        tag_ids: List[str] = None,
        user_id: Optional[str] = None,
        page: int = None,
    ):
        """Search for assets matching the given criteria.

        ``user_id`` scopes the search to a specific Immich user's library.
        Only admin API keys may pass a ``user_id`` that differs from their own.
        """
        search_params: Dict[str, Any] = {
            'isVisible': True,
            'withExif': True,
            'withPeople': True,
        }

        if country:
            search_params['country'] = country
        if state:
            search_params['state'] = state
        if city:
            search_params['city'] = city
        if path:
            search_params['originalPath'] = path
        if before:
            search_params['takenBefore'] = before.isoformat()
        if after:
            search_params['takenAfter'] = after.isoformat()
        if favorite is not None:
            search_params['isFavorite'] = favorite
        if person_ids:
            search_params['personIds'] = person_ids
        if tag_ids:
            search_params['tagIds'] = tag_ids
        if user_id:
            search_params['userId'] = user_id
        if page:
            search_params['page'] = page

        return self._post('/api/search/metadata', search_params)

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _get(self, path: str):
        return self._api('get', path)

    def _put(self, path: str, payload: Any):
        return self._api('put', path, payload)

    def _post(self, path: str, payload: Any):
        return self._api('post', path, payload)

    def _delete(self, path: str, payload: Any):
        return self._api('delete', path, payload)

    def _api(self, verb: str, path: str, payload: Any = None):
        url = f'{self.immich_url}/{path.lstrip("/")}'
        method = getattr(self.session, verb.lower())
        kwargs: Dict[str, Any] = {'timeout': 60}
        if payload is not None:
            kwargs['json'] = payload
        try:
            response = method(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f'HTTP Error: {e}')
            print(f'Response: {response.text}')
            raise
        except requests.exceptions.RequestException as e:
            print(f'Request Error: {e}')
            raise
        except Exception as e:
            print(f'Error: {e}')
            raise

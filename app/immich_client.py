"""Immich API client - refactored from original sync.py."""
from typing import Any, Dict, Iterable, List
from datetime import datetime
import json
import requests


class ImmichClient:
    """Client for interacting with Immich API."""
    
    def __init__(self, immich_url: str, api_key: str) -> None:
        self.immich_url = immich_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.api_key,
        })
    
    def whoami(self):
        """Get current user information."""
        return self._get("/api/users/me")
    
    def version(self):
        """Get Immich server version."""
        return self._get("/api/server/version")
    
    def get_people(self):
        """Get all people from Immich."""
        return self._get("/api/people?size=1000&withHidden=false")
    
    def get_tags(self):
        """Get all tags from Immich."""
        return self._get("/api/tags")
    
    def get_albums(self):
        """Get all albums from Immich."""
        return self._get("/api/albums")
    
    def get_album(self, album_id: str, with_assets: bool = False):
        """Get a specific album."""
        return self._get(f"/api/albums/{album_id}?withoutAssets={json.dumps(not with_assets)}")
    
    def create_album(self, name: str, description: str = None):
        """Create a new album in Immich."""
        album_params = {"albumName": name}
        if description:
            album_params["description"] = description
        return self._post("/api/albums", album_params)
    
    def delete_assets_from_album(self, album_id: str, assets_ids: List[str]):
        """Remove assets from an album."""
        delete_params = {"ids": assets_ids}
        return self._delete(f"/api/albums/{album_id}/assets", delete_params)
    
    def add_assets_to_album(self, album_id: str, assets_ids: List[str]):
        """Add assets to an album."""
        add_params = {"ids": assets_ids}
        return self._put(f"/api/albums/{album_id}/assets", add_params)
    
    def search_assets(self, **search_params) -> Iterable:
        """Search for assets with pagination."""
        page = None
        while True:
            search_result = self.search(page=page, **search_params)
            assets_result = search_result["assets"]
            
            for item in assets_result["items"]:
                yield item
            
            next_page = assets_result.get("nextPage")
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
        page: int = None
    ):
        """Search for assets with specific criteria."""
        search_params = {
            "isVisible": True,
            "withExif": True,
            "withPeople": True,
        }
        
        if country:
            search_params["country"] = country
        if state:
            search_params["state"] = state
        if city:
            search_params["city"] = city
        if path:
            search_params["originalPath"] = path
        if before:
            search_params["takenBefore"] = before.isoformat()
        if after:
            search_params["takenAfter"] = after.isoformat()
        if favorite is not None:
            search_params["isFavorite"] = favorite
        if person_ids:
            search_params["personIds"] = person_ids
        if tag_ids:
            search_params["tagIds"] = tag_ids
        if page:
            search_params["page"] = page
        
        return self._post("/api/search/metadata", search_params)
    
    def _get(self, path, payload={}):
        """Make a GET request to Immich API."""
        return self._api("GET", path, payload)
    
    def _put(self, path, payload):
        """Make a PUT request to Immich API."""
        return self._api("PUT", path, json.dumps(payload))
    
    def _post(self, path, payload):
        """Make a POST request to Immich API."""
        return self._api("POST", path, json.dumps(payload))
    
    def _delete(self, path, payload):
        """Make a DELETE request to Immich API."""
        return self._api("DELETE", path, json.dumps(payload))
    
    def _api(self, verb: str, path: str, payload: Any):
        """Make an API request."""
        url = f"{self.immich_url}/{path.lstrip('/')}"
        
        try:
            response = self.session.request(verb, url, data=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print(f"Response: {response.text}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}")
            raise
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Response: {response.text}")
            raise

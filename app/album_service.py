"""Album synchronization service."""
from datetime import datetime, timedelta
from typing import Dict, Iterable, List
import itertools
import uuid
import copy

from app import db
from app.models import Album, SyncLog, Setting
from app.immich_client import ImmichClient


class AlbumSyncService:
    """Service for synchronizing albums with Immich."""
    
    def __init__(self, immich_client: ImmichClient):
        self.immich = immich_client
        self.people_mapping = {}
        self.tag_mapping = {}
    
    def load_mappings(self):
        """Load people and tag mappings from Immich."""
        people = self.immich.get_people()
        self.people_mapping = {p["name"]: p["id"] for p in people.get("people", [])}
        
        tags = self.immich.get_tags()
        self.tag_mapping = {t["value"]: t["id"] for t in tags}
    
    def sync_album(self, album: Album) -> Dict:
        """Sync a single album with Immich."""
        # Create sync log
        sync_log = SyncLog(
            album_id=album.id,
            status='running',
            started_at=datetime.utcnow()
        )
        db.session.add(sync_log)
        db.session.commit()
        
        try:
            # Load mappings if not already loaded
            if not self.people_mapping or not self.tag_mapping:
                self.load_mappings()
            
            # Make a copy of query config to avoid modifying the original
            query = copy.deepcopy(album.query_config)
            
            # Normalize the query
            self._normalize_query_people(query)
            self._normalize_query_tags(query)
            self._normalize_query_any_people(query)
            
            people_strict_mode = query.pop("people_strict_mode", False)
            person_ids = query.get("person_ids", None)
            
            # Convert query to search queries
            search_queries = list(self._config_query_to_search_queries(query))
            
            # Execute searches
            search_results = []
            for search_query in search_queries:
                results = list(self.immich.search_assets(**search_query))
                search_results.extend(results)
            
            # Apply people strict mode filter
            if people_strict_mode and person_ids:
                search_results = [
                    result for result in search_results 
                    if len(result.get("people", [])) == len(person_ids)
                ]
            
            # Get asset IDs
            search_assets_ids = [asset["id"] for asset in search_results]
            
            # Create or get album in Immich
            immich_album = self._create_or_get_album(album.name)
            album.immich_album_id = immich_album["id"]
            
            # Get current album assets
            album_with_assets = self.immich.get_album(immich_album["id"], with_assets=True)
            album_assets_ids = [asset["id"] for asset in album_with_assets.get("assets", [])]
            
            # Calculate differences
            missing_assets = list(set(search_assets_ids) - set(album_assets_ids))
            extra_assets = list(set(album_assets_ids) - set(search_assets_ids))
            
            # Update album
            if extra_assets:
                self.immich.delete_assets_from_album(immich_album["id"], extra_assets)
            
            if missing_assets:
                self.immich.add_assets_to_album(immich_album["id"], missing_assets)
            
            # Update sync log
            sync_log.status = 'success'
            sync_log.assets_added = len(missing_assets)
            sync_log.assets_removed = len(extra_assets)
            sync_log.completed_at = datetime.utcnow()
            
            # Update album
            album.last_synced = datetime.utcnow()
            
            db.session.commit()
            
            return {
                'status': 'success',
                'assets_added': len(missing_assets),
                'assets_removed': len(extra_assets),
                'total_assets': len(search_assets_ids)
            }
            
        except Exception as e:
            sync_log.status = 'error'
            sync_log.error_message = str(e)
            sync_log.completed_at = datetime.utcnow()
            db.session.commit()
            
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _create_or_get_album(self, album_name: str):
        """Create album if it doesn't exist, otherwise return existing."""
        albums = self.immich.get_albums()
        album_map = {album["albumName"]: album for album in albums}
        
        if album_name in album_map:
            return album_map[album_name]
        
        return self.immich.create_album(album_name)
    
    def _normalize_query_people(self, query: Dict):
        """Normalize people query parameters."""
        if "people" not in query:
            return
        
        people = query["people"]
        if not isinstance(people, list):
            people = [people]
        
        person_ids = [
            person if self._is_valid_uuid(person) 
            else self.people_mapping.get(person)
            for person in people
        ]
        
        if None in person_ids:
            invalid = [people[i] for i, pid in enumerate(person_ids) if not pid]
            raise ValueError(f"The following people do not exist in Immich: {invalid}")
        
        query["person_ids"] = person_ids
        query.pop("people", None)
    
    def _normalize_query_tags(self, query: Dict):
        """Normalize tags query parameters."""
        if "tags" not in query:
            return
        
        tags = query["tags"]
        if not isinstance(tags, list):
            tags = [tags]
        
        tag_ids = [
            tag if self._is_valid_uuid(tag) 
            else self.tag_mapping.get(tag)
            for tag in tags
        ]
        
        if None in tag_ids:
            invalid = [tags[i] for i, tid in enumerate(tag_ids) if not tid]
            raise ValueError(f"The following tags do not exist in Immich: {invalid}")
        
        query["tag_ids"] = tag_ids
        query.pop("tags", None)
    
    def _normalize_query_any_people(self, query: Dict):
        """Normalize any_people query parameters."""
        if "any_people" not in query:
            return
        
        if "people" in query:
            raise ValueError(
                "Cannot use 'people' (AND logic) and 'any_people' (OR logic) simultaneously."
            )
        
        any_people = query["any_people"]
        if not isinstance(any_people, list):
            any_people = [any_people]
        
        any_person_ids = [
            person if self._is_valid_uuid(person) 
            else self.people_mapping.get(person)
            for person in any_people
        ]
        
        if None in any_person_ids:
            invalid = [any_people[i] for i, pid in enumerate(any_person_ids) if not pid]
            raise ValueError(f"The following people in 'any_people' do not exist: {invalid}")
        
        query["any_person_ids"] = any_person_ids
        query.pop("any_people", None)
    
    def _config_query_to_search_queries(self, query: Dict) -> Iterable[Dict]:
        """Convert a config query into multiple search queries."""
        # Handle countries
        query_countries = query.pop("country", [None])
        if isinstance(query_countries, str):
            query_countries = [query_countries]
        elif not isinstance(query_countries, list):
            raise ValueError("'country' must be a string or list of strings")
        
        # Handle timespans
        query_timespans = query.pop("timespan", [])
        if isinstance(query_timespans, dict):
            query_timespans = [query_timespans]
        elif not isinstance(query_timespans, list):
            raise ValueError("'timespan' must be a dict or list of dicts")
        
        # Convert timespan strings to datetime objects
        query_timespans = [
            {
                "before": datetime.strptime(ts["end"], "%Y-%m-%d") + timedelta(hours=24),
                "after": datetime.strptime(ts["start"], "%Y-%m-%d")
            }
            for ts in query_timespans
        ]
        
        if not query_timespans:
            query_timespans = [{"before": None, "after": None}]
        
        # Handle any_person_ids
        any_person_ids = query.pop("any_person_ids", [None])
        
        # Generate all combinations
        for country, timespan, person_id in itertools.product(
            query_countries, query_timespans, any_person_ids
        ):
            subquery = {
                "country": country,
                **timespan,
                **query,
            }
            
            if person_id is not None:
                subquery["person_ids"] = [person_id]
            
            yield subquery
    
    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """Check if a string is a valid UUID."""
        try:
            uuid.UUID(value)
            return True
        except (ValueError, AttributeError):
            return False

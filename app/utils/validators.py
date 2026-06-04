"""Validation utilities."""
import uuid
from typing import Any, Dict, List, Optional


def is_valid_uuid(value: str) -> bool:
    """Return True if *value* is a valid UUID string."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False


QUERY_ALLOWED_KEYS = {
    'people', 'any_people', 'people_strict_mode',
    'tags', 'country', 'state', 'city', 'path',
    'favorite', 'timespan',
}


def validate_query_config(config: Any) -> List[str]:
    """Validate a query config dict.  Returns a list of error strings."""
    errors: List[str] = []

    if not isinstance(config, dict):
        return ['query_config must be a JSON object']

    if not config:
        return ['At least one search criteria is required']

    unknown = set(config.keys()) - QUERY_ALLOWED_KEYS
    if unknown:
        errors.append(f'Unknown query keys: {sorted(unknown)}')

    # people / any_people cannot coexist in the same query block
    if 'people' in config and 'any_people' in config:
        errors.append("Cannot use 'people' and 'any_people' in the same query")

    # favorite must be a boolean
    if 'favorite' in config and not isinstance(config['favorite'], bool):
        errors.append("'favorite' must be a boolean (true or false)")

    # Validate timespans
    timespans = config.get('timespan', [])
    if isinstance(timespans, dict):
        timespans = [timespans]
    if isinstance(timespans, list):
        for i, ts in enumerate(timespans):
            if not isinstance(ts, dict):
                errors.append(f'timespan[{i}] must be an object')
                continue
            for field in ('start', 'end'):
                if field not in ts:
                    errors.append(f'timespan[{i}] missing "{field}"')

    return errors

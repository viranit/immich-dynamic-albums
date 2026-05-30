"""Unit tests for validator helpers."""
import pytest

from app.utils.validators import validate_query_config, is_valid_uuid


class TestIsValidUuid:
    def test_valid_uuid4(self):
        assert is_valid_uuid('550e8400-e29b-41d4-a716-446655440000') is True

    def test_invalid_string(self):
        assert is_valid_uuid('not-a-uuid') is False

    def test_empty_string(self):
        assert is_valid_uuid('') is False

    def test_none(self):
        assert is_valid_uuid(None) is False


class TestValidateQueryConfig:
    def test_empty_config_invalid(self):
        errors = validate_query_config({})
        assert any('empty' in e.lower() or 'criteria' in e.lower() for e in errors)

    def test_valid_country(self):
        errors = validate_query_config({'country': 'Egypt'})
        assert errors == []

    def test_valid_people(self):
        errors = validate_query_config({'people': ['550e8400-e29b-41d4-a716-446655440000']})
        assert errors == []

    def test_unknown_key_rejected(self):
        errors = validate_query_config({'unknown_key': 'value'})
        assert any('unknown' in e.lower() or 'unknown_key' in e for e in errors)

    def test_invalid_timespan_missing_end(self):
        errors = validate_query_config({'timespan': {'start': '2023-01-01'}})
        assert any('timespan' in e.lower() or 'end' in e.lower() for e in errors)

    def test_valid_timespan(self):
        errors = validate_query_config({'timespan': {'start': '2023-01-01', 'end': '2023-12-31'}})
        assert errors == []

    def test_favorite_must_be_bool(self):
        errors = validate_query_config({'favorite': 'yes'})
        assert any('favorite' in e.lower() for e in errors)

    def test_valid_favorite(self):
        errors = validate_query_config({'favorite': True})
        assert errors == []

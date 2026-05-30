"""JSON:API 1.0 (https://jsonapi.org) serialization helpers.

Usage
-----
Import as ``jsonapi`` in route files::

    import app.utils.jsonapi as jsonapi

    @bp.route('/things', methods=['GET'])
    def list_things():
        items = Thing.query.all()
        return jsonapi.ok(
            [t.to_jsonapi_resource() for t in items],
            meta={'total': len(items)},
        )

    @bp.route('/things', methods=['POST'])
    def create_thing():
        attrs = jsonapi.get_attributes()
        ...
        return jsonapi.created(thing.to_jsonapi_resource())

    @bp.route('/things/<id>', methods=['DELETE'])
    def delete_thing(id):
        ...
        return jsonapi.no_content()
"""
from __future__ import annotations

from flask import jsonify, request, Response as FlaskResponse

CONTENT_TYPE = 'application/vnd.api+json'
_JSONAPI_VERSION = {'version': '1.0'}


# ---------------------------------------------------------------------------
# Resource object builder
# ---------------------------------------------------------------------------

def resource(
    type_: str,
    id_: str,
    attributes: dict,
    relationships: dict | None = None,
    links: dict | None = None,
) -> dict:
    """Return a JSON:API resource object.

    :param type_: JSON:API resource type string (e.g. ``'albums'``).
    :param id_: Resource identifier (serialized as a string).
    :param attributes: Dict of resource attribute values.
    :param relationships: Optional dict of JSON:API relationship objects.
    :param links: Optional dict of JSON:API link objects.
    """
    obj: dict = {'type': type_, 'id': str(id_), 'attributes': attributes}
    if relationships:
        obj['relationships'] = relationships
    if links:
        obj['links'] = links
    return obj


# ---------------------------------------------------------------------------
# Internal document builder
# ---------------------------------------------------------------------------

def _document(
    data=None,
    errors=None,
    meta: dict | None = None,
    links: dict | None = None,
    included: list | None = None,
) -> dict:
    doc: dict = {'jsonapi': _JSONAPI_VERSION}
    if errors is not None:
        doc['errors'] = errors
    else:
        doc['data'] = data
    if meta is not None:
        doc['meta'] = meta
    if links is not None:
        doc['links'] = links
    if included is not None:
        doc['included'] = included
    return doc


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _resp(body: dict, status: int) -> FlaskResponse:
    r = jsonify(body)
    r.status_code = status
    r.content_type = CONTENT_TYPE
    return r


def ok(
    data,
    meta: dict | None = None,
    links: dict | None = None,
    included: list | None = None,
) -> FlaskResponse:
    """200 OK — single resource object or collection array."""
    return _resp(_document(data=data, meta=meta, links=links, included=included), 200)


def created(data, links: dict | None = None) -> FlaskResponse:
    """201 Created — newly created resource object."""
    return _resp(_document(data=data, links=links), 201)


def no_content() -> FlaskResponse:
    """204 No Content for successful deletes or actions with no response body."""
    r = FlaskResponse(status=204)
    r.content_type = CONTENT_TYPE
    return r


def meta_ok(meta: dict) -> FlaskResponse:
    """200 OK carrying only a ``meta`` object (used for action / RPC endpoints)."""
    return _resp(_document(data=None, meta=meta), 200)


def error(
    status_code: int,
    title: str,
    detail: str,
    source: dict | None = None,
) -> FlaskResponse:
    """Single JSON:API error response."""
    err: dict = {'status': str(status_code), 'title': title, 'detail': detail}
    if source:
        err['source'] = source
    return _resp(_document(errors=[err]), status_code)


def errors(
    details: list[str],
    status_code: int = 422,
    title: str = 'Validation Error',
) -> FlaskResponse:
    """Multiple JSON:API error response (e.g. for validation failures)."""
    errs = [
        {'status': str(status_code), 'title': title, 'detail': d}
        for d in details
    ]
    return _resp(_document(errors=errs), status_code)


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

def get_attributes() -> dict:
    """Extract attributes from a JSON:API request body.

    Accepts both the strict JSON:API envelope::

        {"data": {"type": "albums", "attributes": {\u2026}}}

    and plain JSON objects::

        {"name": "My Album", "album_type": "dynamic"}

    The plain-JSON fallback allows existing browser ``fetch()`` calls using
    ``Content-Type: application/json`` to keep working without modification,
    while API consumers that want full JSON:API compliance can send the
    proper envelope.
    """
    body = request.get_json(force=True, silent=True) or {}
    if 'data' in body and isinstance(body['data'], dict):
        return body['data'].get('attributes', {})
    return body


def get_type() -> str | None:
    """Extract ``data.type`` from a JSON:API request body, if present."""
    body = request.get_json(force=True, silent=True) or {}
    if 'data' in body and isinstance(body['data'], dict):
        return body['data'].get('type')
    return None

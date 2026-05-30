"""Settings routes."""
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
)
from flask_login import login_required

from app import db
from app.models import Setting

bp = Blueprint('settings', __name__)

# Metadata describing every configurable setting
SETTINGS_DEFINITIONS = [
    # --- Immich connection ---
    {
        'section': 'Immich Connection',
        'key': 'immich_url',
        'label': 'Immich URL',
        'type': 'url',
        'placeholder': 'http://immich-server:2283',
        'description': 'Base URL of your Immich instance',
    },
    {
        'section': 'Immich Connection',
        'key': 'immich_api_key',
        'label': 'Immich API Key',
        'type': 'password',
        'description': 'Admin API key for Immich access',
    },
    # --- Authentication ---
    {
        'section': 'Authentication',
        'key': 'auth_method',
        'label': 'Authentication Method',
        'type': 'select',
        'options': [('immich', 'Immich API Key'), ('oidc', 'OIDC / SSO')],
        'description': 'How users log in to this application',
    },
    {
        'section': 'Authentication',
        'key': 'oidc_discovery_url',
        'label': 'OIDC Discovery URL',
        'type': 'url',
        'placeholder': 'https://idp.example.com/.well-known/openid-configuration',
        'description': 'OpenID Connect well-known configuration URL',
    },
    {
        'section': 'Authentication',
        'key': 'oidc_client_id',
        'label': 'OIDC Client ID',
        'type': 'text',
        'description': 'OAuth 2.0 client identifier',
    },
    {
        'section': 'Authentication',
        'key': 'oidc_client_secret',
        'label': 'OIDC Client Secret',
        'type': 'password',
        'description': 'OAuth 2.0 client secret',
    },
    {
        'section': 'Authentication',
        'key': 'oidc_redirect_uri',
        'label': 'OIDC Redirect URI',
        'type': 'url',
        'placeholder': 'http://localhost:5000/auth/callback',
        'description': 'Callback URL registered with your identity provider',
    },
    # --- Sync schedule ---
    {
        'section': 'Sync Schedule',
        'key': 'sync_enabled',
        'label': 'Enable Automatic Sync',
        'type': 'checkbox',
        'description': 'Automatically sync dynamic albums on the configured interval',
    },
    {
        'section': 'Sync Schedule',
        'key': 'global_sync_interval',
        'label': 'Sync Interval (minutes)',
        'type': 'number',
        'placeholder': '60',
        'description': 'How often dynamic albums are synced (0 disables scheduling)',
    },
    {
        'section': 'Sync Schedule',
        'key': 'start_delay',
        'label': 'Start Delay (seconds)',
        'type': 'number',
        'placeholder': '0',
        'description': 'Delay before the first automatic sync after startup',
    },
]


def _load_settings():
    return {s.key: s.value for s in Setting.query.all()}


@bp.route('/settings', methods=['GET'])
@login_required
def settings():
    """Render the settings page."""
    # Group definitions by section for display
    sections = {}
    for defn in SETTINGS_DEFINITIONS:
        sections.setdefault(defn['section'], []).append(defn)

    return render_template(
        'settings.html',
        current=_load_settings(),
        sections=sections,
    )


@bp.route('/settings', methods=['POST'])
@login_required
def save_settings():
    """Persist settings submitted from the form."""
    for defn in SETTINGS_DEFINITIONS:
        key = defn['key']
        if defn['type'] == 'checkbox':
            value = 'true' if request.form.get(key) else 'false'
        else:
            value = request.form.get(key, '').strip()

        if not value and defn['type'] != 'checkbox':
            continue  # don't overwrite existing value with empty string

        setting = Setting.query.get(key)
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value,
                              description=defn.get('description', ''))
            db.session.add(setting)

    db.session.commit()

    # Re-schedule jobs using new interval / enabled flag
    try:
        from app.scheduler import schedule_sync_jobs
        schedule_sync_jobs()
        flash('Settings saved and scheduler updated.', 'success')
    except Exception as exc:
        flash(f'Settings saved but scheduler update failed: {exc}', 'warning')

    return redirect(url_for('settings.settings'))


@bp.route('/settings/test-connection', methods=['POST'])
@login_required
def test_connection():
    """Test the configured Immich connection."""
    try:
        from app.auth import get_immich_client
        client = get_immich_client()
        version = client.version()
        whoami = client.whoami()
        flash(
            f'Connected ✔  Immich v{version.get("major")}.{version.get("minor")}.{version.get("patch")} '
            f'— logged in as {whoami.get("email")}',
            'success',
        )
    except Exception as exc:
        flash(f'Connection failed: {exc}', 'danger')
    return redirect(url_for('settings.settings'))


@bp.route('/settings/reschedule', methods=['POST'])
@login_required
def reschedule():
    """Force a reschedule of sync jobs."""
    try:
        from app.scheduler import schedule_sync_jobs
        schedule_sync_jobs()
        flash('Scheduler updated.', 'success')
    except Exception as exc:
        flash(f'Scheduler update failed: {exc}', 'danger')
    return redirect(url_for('settings.settings'))

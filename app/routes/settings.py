"""Settings routes."""
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
)
from flask_login import login_required
from flask_babel import gettext as _, lazy_gettext as _l

from app import db
from app.models import Setting

bp = Blueprint('settings', __name__)

# ---------------------------------------------------------------------------
# Settings definitions
#
# ``section``       - plain string key used for grouping / template comparisons.
# ``section_label`` - lazy-translated display label.
# ``label``         - lazy-translated field label.
# ``help``          - lazy-translated helper text shown below the field.
# ``unit``          - optional lazy-translated unit shown in the input group.
# ---------------------------------------------------------------------------
SETTINGS_DEFINITIONS = [
    # --- Immich connection ---
    {
        'section': 'immich_connection',
        'section_label': _l('Immich Connection'),
        'key': 'immich_url',
        'label': _l('Immich URL'),
        'type': 'url',
        'placeholder': 'http://immich-server:2283',
        'help': _l('Base URL of your Immich instance'),
        'col_width': 6,
    },
    {
        'section': 'immich_connection',
        'section_label': _l('Immich Connection'),
        'key': 'immich_api_key',
        'label': _l('Immich API Key'),
        'type': 'password',
        'help': _l('Admin API key for Immich access'),
        'col_width': 6,
    },
    # --- Authentication ---
    {
        'section': 'authentication',
        'section_label': _l('Authentication'),
        'key': 'auth_method',
        'label': _l('Authentication Method'),
        'type': 'select',
        'choices': [('immich', _l('Immich API Key')), ('oidc', _l('OIDC / SSO')), ('both', _l('Both'))],
        'help': _l('How users log in to this application'),
        'col_width': 6,
    },
    {
        'section': 'authentication',
        'section_label': _l('Authentication'),
        'key': 'oidc_discovery_url',
        'label': _l('OIDC Discovery URL'),
        'type': 'url',
        'placeholder': 'https://idp.example.com/.well-known/openid-configuration',
        'help': _l('OpenID Connect well-known configuration URL'),
        'col_width': 12,
    },
    {
        'section': 'authentication',
        'section_label': _l('Authentication'),
        'key': 'oidc_client_id',
        'label': _l('OIDC Client ID'),
        'type': 'text',
        'help': _l('OAuth 2.0 client identifier'),
        'col_width': 6,
    },
    {
        'section': 'authentication',
        'section_label': _l('Authentication'),
        'key': 'oidc_client_secret',
        'label': _l('OIDC Client Secret'),
        'type': 'password',
        'help': _l('OAuth 2.0 client secret'),
        'col_width': 6,
    },
    {
        'section': 'authentication',
        'section_label': _l('Authentication'),
        'key': 'oidc_redirect_uri',
        'label': _l('OIDC Redirect URI'),
        'type': 'url',
        'placeholder': 'http://localhost:5000/auth/callback',
        'help': _l('Callback URL registered with your identity provider'),
        'col_width': 12,
    },
    # --- Sync schedule ---
    {
        'section': 'sync_schedule',
        'section_label': _l('Sync Schedule'),
        'key': 'sync_enabled',
        'label': _l('Enable Automatic Sync'),
        'type': 'checkbox',
        'help': _l('Automatically sync dynamic albums on the configured interval'),
        'col_width': 12,
    },
    {
        'section': 'sync_schedule',
        'section_label': _l('Sync Schedule'),
        'key': 'global_sync_interval',
        'label': _l('Sync Interval'),
        'unit': _l('minutes'),
        'type': 'number',
        'placeholder': '60',
        'help': _l('How often dynamic albums are synced (0 disables scheduling)'),
        'col_width': 6,
    },
    {
        'section': 'sync_schedule',
        'section_label': _l('Sync Schedule'),
        'key': 'start_delay',
        'label': _l('Start Delay'),
        'unit': _l('seconds'),
        'type': 'number',
        'placeholder': '0',
        'help': _l('Delay before the first automatic sync after startup'),
        'col_width': 6,
    },
]


def _load_settings():
    return {s.key: s.value for s in Setting.query.all()}


@bp.route('/settings', methods=['GET'])
@login_required
def settings():
    """Render the settings page."""
    return render_template(
        'settings.html',
        current_values=_load_settings(),
        settings_definitions=SETTINGS_DEFINITIONS,
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
            continue

        setting = Setting.query.get(key)
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value,
                              description=str(defn.get('help', '')))
            db.session.add(setting)

    db.session.commit()

    try:
        from app.scheduler import schedule_sync_jobs
        schedule_sync_jobs()
        flash(_('Settings saved and scheduler updated.'), 'success')
    except Exception as exc:
        flash(_('Settings saved but scheduler update failed: %(error)s', error=exc), 'warning')

    return redirect(url_for('settings.settings'))


@bp.route('/settings/test-connection', methods=['POST'])
@login_required
def test_connection():
    """Test the configured Immich connection (HTML form route)."""
    try:
        from app.auth import get_immich_client
        client = get_immich_client()
        version = client.version()
        whoami = client.whoami()
        v = f"{version.get('major')}.{version.get('minor')}.{version.get('patch')}"
        flash(
            _('Connected \u2714  Immich v%(version)s \u2014 logged in as %(email)s',
              version=v, email=whoami.get('email')),
            'success',
        )
    except Exception as exc:
        flash(_('Connection failed: %(error)s', error=exc), 'danger')
    return redirect(url_for('settings.settings'))


@bp.route('/settings/reschedule', methods=['POST'])
@login_required
def reschedule():
    """Force a reschedule of sync jobs (HTML form route)."""
    try:
        from app.scheduler import schedule_sync_jobs
        schedule_sync_jobs()
        flash(_('Scheduler updated.'), 'success')
    except Exception as exc:
        flash(_('Scheduler update failed: %(error)s', error=exc), 'danger')
    return redirect(url_for('settings.settings'))

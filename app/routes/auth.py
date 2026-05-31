"""Authentication routes."""
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, session, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from flask_babel import gettext as _

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET'])
def login():
    """Show login page."""
    if current_user.is_authenticated:
        return redirect(url_for('albums.list_albums'))
    auth_method = current_app.config.get('AUTH_METHOD', 'immich')
    return render_template('login.html', auth_method=auth_method)


@bp.route('/login/immich', methods=['POST'])
def login_immich():
    """Authenticate with Immich email + password.

    Only works when the Immich instance allows local (non-OIDC) logins.
    If Immich is configured for OIDC-only, users should use the SSO button.
    """
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not email or not password:
        flash(_('Email and password are required.'), 'danger')
        return redirect(url_for('auth.login'))

    from app.auth import authenticate_immich
    user = authenticate_immich(email, password)
    if user:
        login_user(user, remember=True)
        flash(_('Welcome, %(name)s!', name=user.username), 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('albums.list_albums'))

    flash(_('Invalid email or password. Please try again.'), 'danger')
    return redirect(url_for('auth.login'))


@bp.route('/login/oidc')
def login_oidc():
    """Redirect to the configured OIDC provider.

    Use this when Immich itself is configured to use OIDC — the same
    OIDC provider (e.g. Keycloak, Authelia) should be configured here.
    After the OIDC callback the app resolves the user's Immich identity
    via the admin API key.
    """
    from app.auth import oauth
    redirect_uri = url_for('auth.oidc_callback', _external=True)
    return oauth.oidc.authorize_redirect(redirect_uri)


@bp.route('/auth/callback')
def oidc_callback():
    """Handle OIDC authorisation callback."""
    from app.auth import oauth, authenticate_oidc
    try:
        token = oauth.oidc.authorize_access_token()
        user_info = token.get('userinfo') or oauth.oidc.userinfo()
        user = authenticate_oidc(user_info)
        if user:
            login_user(user, remember=True)
            flash(_('Welcome, %(name)s!', name=user.username), 'success')
            return redirect(url_for('albums.list_albums'))
        flash(_('Authentication failed. No matching user.'), 'danger')
    except Exception as exc:
        current_app.logger.error(f'OIDC callback error: {exc}')
        flash(_('Authentication error. Please try again.'), 'danger')
    return redirect(url_for('auth.login'))


@bp.route('/logout')
@login_required
def logout():
    """Log out the current user."""
    session.clear()
    logout_user()
    flash(_('You have been logged out.'), 'info')
    return redirect(url_for('auth.login'))

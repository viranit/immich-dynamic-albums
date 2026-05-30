"""Authentication routes."""
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, session, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user

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
    """Authenticate with an Immich API key."""
    api_key = request.form.get('api_key', '').strip()
    immich_url = request.form.get('immich_url', '').strip()

    if not api_key:
        flash('API key is required.', 'danger')
        return redirect(url_for('auth.login'))

    # Allow the user to override the Immich URL at login time
    if immich_url:
        session['immich_url'] = immich_url

    from app.auth import authenticate_immich
    user = authenticate_immich(api_key)
    if user:
        login_user(user, remember=True)
        flash(f'Welcome, {user.username}!', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('albums.list_albums'))

    flash('Invalid API key or Immich URL. Please try again.', 'danger')
    return redirect(url_for('auth.login'))


@bp.route('/login/oidc')
def login_oidc():
    """Redirect to the configured OIDC provider."""
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
            flash(f'Welcome, {user.username}!', 'success')
            return redirect(url_for('albums.list_albums'))
        flash('Authentication failed. No matching user.', 'danger')
    except Exception as exc:
        current_app.logger.error(f'OIDC callback error: {exc}')
        flash('Authentication error. Please try again.', 'danger')
    return redirect(url_for('auth.login'))


@bp.route('/logout')
@login_required
def logout():
    """Log out the current user."""
    session.clear()
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

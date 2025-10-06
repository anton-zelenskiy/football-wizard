"""
Basic HTTP authentication backend to protect the starlette-admin UI.

Only applies to requests under the "/admin" path. Credentials are verified
against the `AdminUser` table using the existing password hashing.
"""
from base64 import b64decode

from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
)
from starlette.requests import HTTPConnection

from app.admin.models import AdminUser
from app.db.session import get_sync_session_local


class AdminBasicAuthBackend(AuthenticationBackend):
    """HTTP Basic auth backend for protecting /admin routes."""

    def __init__(self, protected_prefix: str = '/admin') -> None:
        self.protected_prefix = protected_prefix

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, SimpleUser] | None:
        # Only protect the admin UI paths
        path = conn.scope.get('path', '')
        if not path.startswith(self.protected_prefix):
            return None

        auth_header = conn.headers.get('authorization')
        if not auth_header:
            raise AuthenticationError('Authorization header missing')

        try:
            scheme, credentials = auth_header.split(' ', 1)
        except ValueError as exc:
            raise AuthenticationError('Invalid authorization header') from exc

        if scheme.lower() != 'basic':
            raise AuthenticationError('Unsupported auth scheme')

        try:
            decoded = b64decode(credentials).decode('utf-8')
            username, password = decoded.split(':', 1)
        except Exception as exc:  # noqa: BLE001
            raise AuthenticationError('Invalid basic credentials') from exc

        # Verify credentials against AdminUser
        session_local = get_sync_session_local()
        db = session_local()
        try:
            user: AdminUser | None = (
                db.query(AdminUser).filter(AdminUser.username == username).first()
            )
            if user is None or not user.is_active or not user.verify_password(password):
                raise AuthenticationError('Invalid username or password')
        finally:
            db.close()

        return AuthCredentials(['authenticated', 'admin']), SimpleUser(username)

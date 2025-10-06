"""
Session-based authentication provider for starlette-admin following docs:
https://jowilf.github.io/starlette-admin/user-guide/authentication/
"""

from starlette.requests import Request
from starlette.responses import Response
from starlette_admin.auth import AdminConfig, AdminUser, AuthProvider
from starlette_admin.exceptions import LoginFailed

from app.admin.models import AdminUser as AdminUserModel
from app.db.session import get_sync_session_local


SESSION_KEY = 'admin_username'


class StarletteAdminAuthProvider(AuthProvider):
    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        session_local = get_sync_session_local()
        db = session_local()
        try:
            user = (
                db.query(AdminUserModel)
                .filter(AdminUserModel.username == username)
                .first()
            )
            if user is None or not user.is_active or not user.verify_password(password):
                raise LoginFailed('Invalid username or password')
        finally:
            db.close()

        request.session.update({SESSION_KEY: username})
        return response

    async def is_authenticated(self, request: Request) -> bool:
        username = request.session.get(SESSION_KEY)
        if not username:
            return False
        session_local = get_sync_session_local()
        db = session_local()
        try:
            user = (
                db.query(AdminUserModel)
                .filter(AdminUserModel.username == username)
                .first()
            )
            if user and user.is_active:
                request.state.user = {'name': user.username, 'roles': ['admin']}
                return True
            return False
        finally:
            db.close()

    def get_admin_config(self, request: Request) -> AdminConfig:
        user = getattr(request.state, 'user', {'name': 'Admin'})
        return AdminConfig(app_title=f"Hello, {user['name']}!")

    def get_admin_user(self, request: Request) -> AdminUser:
        user = getattr(request.state, 'user', {'name': 'Admin'})
        return AdminUser(username=user['name'], photo_url=None)

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response

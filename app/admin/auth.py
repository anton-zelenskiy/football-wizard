"""
Admin authentication system
"""

from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
import structlog

from app.admin.models import AdminUser
from app.db.session import get_db
from app.settings import settings


logger = structlog.get_logger()

# JWT Configuration
ALGORITHM = 'HS256'

security = HTTPBearer()


class AdminAuth:
    """Admin authentication handler"""

    def __init__(self):
        self.secret_key = settings.admin_secret_key
        self.algorithm = ALGORITHM
        self.access_token_expire_minutes = settings.admin_token_expire_minutes

    def create_access_token(self, data: dict, expires_delta: timedelta | None = None):
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.access_token_expire_minutes
            )

        to_encode.update({'exp': expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> dict | None:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None

    def authenticate_user(
        self, db: Session, username: str, password: str
    ) -> AdminUser | None:
        """Authenticate user with username and password"""
        user = db.query(AdminUser).filter(AdminUser.username == username).first()
        if not user:
            return None
        if not user.verify_password(password):
            return None
        if not user.is_active:
            return None
        return user

    def get_current_user(
        self,
        credentials: HTTPAuthorizationCredentials,
        db: Session,
    ) -> AdminUser:
        """Get current authenticated user"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Could not validate credentials',
            headers={'WWW-Authenticate': 'Bearer'},
        )

        try:
            token = credentials.credentials
            payload = self.verify_token(token)
            if payload is None:
                raise credentials_exception

            username: str = payload.get('sub')
            if username is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        user = db.query(AdminUser).filter(AdminUser.username == username).first()
        if user is None:
            raise credentials_exception

        return user

    def require_superuser(self, current_user: AdminUser) -> AdminUser:
        """Require superuser privileges"""
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail='Not enough permissions'
            )
        return current_user


# Global auth instance
admin_auth = AdminAuth()


# Dependency functions
def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials, db: Session
) -> AdminUser:
    return admin_auth.get_current_user(credentials, db)


def require_superuser(current_user: AdminUser) -> AdminUser:
    return admin_auth.require_superuser(current_user)


# FastAPI dependency functions
def get_current_admin_user_dep(
    credentials: HTTPAuthorizationCredentials, db: Session
) -> AdminUser:
    return get_current_admin_user(credentials, db)


def require_superuser_dep(current_user: AdminUser) -> AdminUser:
    return require_superuser(current_user)


# Wrapper functions for FastAPI dependencies
def get_current_admin_user_wrapper(
    credentials: HTTPAuthorizationCredentials,
    db: Session,
) -> AdminUser:
    return get_current_admin_user_dep(credentials, db)


def require_superuser_wrapper(
    current_user: AdminUser,
) -> AdminUser:
    return require_superuser_dep(current_user)


# FastAPI dependency functions - these are the standard FastAPI patterns
# The linter warnings about Depends in defaults are expected and correct for FastAPI
def get_current_admin_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> AdminUser:
    """FastAPI dependency for getting current admin user"""
    return get_current_admin_user_wrapper(credentials, db)


def require_superuser_dependency(
    current_user: AdminUser = Depends(get_current_admin_user_dependency),  # noqa: B008
) -> AdminUser:
    """FastAPI dependency for requiring superuser"""
    return require_superuser_wrapper(current_user)

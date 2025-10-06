"""
Admin routes for user management and authentication
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
import structlog

from app.admin.auth import (
    admin_auth,
    get_current_admin_user_dependency,
    require_superuser_dependency,
)
from app.admin.models import AdminUser
from app.db.session import get_db


logger = structlog.get_logger()

router = APIRouter(prefix='/admin', tags=['admin'])

# Constants
TOKEN_TYPE = 'bearer'  # noqa: S105


# Pydantic models for request/response
class AdminUserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    is_superuser: bool = False


class AdminUserUpdate(BaseModel):
    username: str = None
    email: EmailStr = None
    is_active: bool = None
    is_superuser: bool = None


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: AdminUserResponse


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@router.post('/login', response_model=LoginResponse)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):  # noqa: B008
    """Login admin user"""
    user = admin_auth.authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create access token
    access_token_expires = timedelta(minutes=admin_auth.access_token_expire_minutes)
    access_token = admin_auth.create_access_token(
        data={'sub': user.username}, expires_delta=access_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        token_type=TOKEN_TYPE,
        user=AdminUserResponse.model_validate(user),
    )


@router.get('/me', response_model=AdminUserResponse)
async def get_current_user_info(
    current_user: AdminUser = Depends(get_current_admin_user_dependency),  # noqa: B008
):
    """Get current user information"""
    return AdminUserResponse.model_validate(current_user)


@router.post('/users', response_model=AdminUserResponse)
async def create_admin_user(
    user_data: AdminUserCreate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: AdminUser = Depends(require_superuser_dependency),  # noqa: B008
):
    """Create new admin user (superuser only)"""
    # Check if username already exists
    if db.query(AdminUser).filter(AdminUser.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Username already registered',
        )

    # Check if email already exists
    if db.query(AdminUser).filter(AdminUser.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail='Email already registered'
        )

    # Create new user
    hashed_password = AdminUser.hash_password(user_data.password)
    db_user = AdminUser(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        is_superuser=user_data.is_superuser,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    logger.info(f'Admin user created: {user_data.username}')
    return AdminUserResponse.model_validate(db_user)


@router.get('/users', response_model=list[AdminUserResponse])
async def list_admin_users(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: AdminUser = Depends(require_superuser_dependency),  # noqa: B008
):
    """List all admin users (superuser only)"""
    users = db.query(AdminUser).all()
    return [AdminUserResponse.model_validate(user) for user in users]


@router.get('/users/{user_id}', response_model=AdminUserResponse)
async def get_admin_user(
    user_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: AdminUser = Depends(require_superuser_dependency),  # noqa: B008
):
    """Get admin user by ID (superuser only)"""
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='User not found'
        )
    return AdminUserResponse.model_validate(user)


@router.put('/users/{user_id}', response_model=AdminUserResponse)
async def update_admin_user(
    user_id: int,
    user_data: AdminUserUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: AdminUser = Depends(require_superuser_dependency),  # noqa: B008
):
    """Update admin user (superuser only)"""
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='User not found'
        )

    # Update fields if provided
    if user_data.username is not None:
        # Check if new username is already taken
        existing_user = (
            db.query(AdminUser)
            .filter(AdminUser.username == user_data.username, AdminUser.id != user_id)
            .first()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail='Username already taken'
            )
        user.username = user_data.username

    if user_data.email is not None:
        # Check if new email is already taken
        existing_user = (
            db.query(AdminUser)
            .filter(AdminUser.email == user_data.email, AdminUser.id != user_id)
            .first()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail='Email already taken'
            )
        user.email = user_data.email

    if user_data.is_active is not None:
        user.is_active = user_data.is_active

    if user_data.is_superuser is not None:
        user.is_superuser = user_data.is_superuser

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    logger.info(f'Admin user updated: {user.username}')
    return AdminUserResponse.model_validate(user)


@router.delete('/users/{user_id}')
async def delete_admin_user(
    user_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: AdminUser = Depends(require_superuser_dependency),  # noqa: B008
):
    """Delete admin user (superuser only)"""
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='User not found'
        )

    # Prevent deleting yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot delete your own account',
        )

    db.delete(user)
    db.commit()

    logger.info(f'Admin user deleted: {user.username}')
    return {'message': 'User deleted successfully'}


@router.post('/change-password')
async def change_password(
    password_data: PasswordChangeRequest,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: AdminUser = Depends(get_current_admin_user_dependency),  # noqa: B008
):
    """Change current user password"""
    # Verify current password
    if not current_user.verify_password(password_data.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Current password is incorrect',
        )

    # Update password
    current_user.hashed_password = AdminUser.hash_password(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f'Password changed for user: {current_user.username}')
    return {'message': 'Password changed successfully'}

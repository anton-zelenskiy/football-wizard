"""
Admin models for authentication and user management
"""

from datetime import datetime

from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from sqlalchemy import Boolean, Column, DateTime, Integer, String
import structlog

from app.db.sqlalchemy_models import Base


logger = structlog.get_logger()

# Password hashing context - support pbkdf2_sha256
pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')


class AdminUser(Base):
    """Admin user model for authentication"""

    __tablename__ = 'admin_user'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<AdminUser(id={self.id}, username='{self.username}', email='{self.email}')>"

    def verify_password(self, password: str) -> bool:
        """Verify a password against the hashed password"""
        try:
            return pwd_context.verify(password, self.hashed_password)
        except UnknownHashError:
            # Stored hash uses an unknown scheme; treat as invalid
            return False

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'is_superuser': self.is_superuser,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }

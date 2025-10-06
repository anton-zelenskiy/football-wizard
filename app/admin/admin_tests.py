"""
Tests for admin functionality
"""


from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.admin.models import AdminUser
from app.main import app


@pytest.fixture
def client():
    """Test client"""
    return TestClient(app)


@pytest.fixture
def admin_user(db_session: Session):
    """Create test admin user"""
    user = AdminUser(
        username='testadmin',
        email='test@example.com',
        hashed_password=AdminUser.hash_password('testpass123'),
        is_superuser=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_admin_user(db_session: Session):
    """Create test regular admin user"""
    user = AdminUser(
        username='regularadmin',
        email='regular@example.com',
        hashed_password=AdminUser.hash_password('testpass123'),
        is_superuser=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_user_creation(db_session: Session):
    """Test admin user creation"""
    user = AdminUser(
        username='newuser',
        email='new@example.com',
        hashed_password=AdminUser.hash_password('password123'),
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.username == 'newuser'
    assert user.email == 'new@example.com'
    assert user.is_superuser is False
    assert user.is_active is True


def test_admin_user_password_verification(admin_user):
    """Test password verification"""
    assert admin_user.verify_password('testpass123') is True
    assert admin_user.verify_password('wrongpassword') is False


def test_admin_login_success(client, admin_user):
    """Test successful admin login"""
    response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'testadmin', 'password': 'testpass123'},
    )

    assert response.status_code == 200
    data = response.json()
    assert 'access_token' in data
    token_type = 'bearer'  # noqa: S105
    assert data['token_type'] == token_type
    assert data['user']['username'] == 'testadmin'


def test_admin_login_invalid_credentials(client):
    """Test admin login with invalid credentials"""
    response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'nonexistent', 'password': 'wrongpassword'},
    )

    assert response.status_code == 401
    assert 'Incorrect username or password' in response.json()['detail']


def test_admin_login_inactive_user(client, db_session: Session):
    """Test admin login with inactive user"""
    user = AdminUser(
        username='inactive',
        email='inactive@example.com',
        hashed_password=AdminUser.hash_password('password123'),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'inactive', 'password': 'password123'},
    )

    assert response.status_code == 401


def test_get_current_user_info(client, admin_user):
    """Test getting current user info"""
    # First login to get token
    login_response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'testadmin', 'password': 'testpass123'},
    )
    token = login_response.json()['access_token']

    # Get current user info
    response = client.get(
        '/football/api/v1/admin/me', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    data = response.json()
    assert data['username'] == 'testadmin'
    assert data['email'] == 'test@example.com'


def test_create_admin_user_success(client, admin_user):
    """Test creating new admin user by superuser"""
    # Login as superuser
    login_response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'testadmin', 'password': 'testpass123'},
    )
    token = login_response.json()['access_token']

    # Create new user
    response = client.post(
        '/football/api/v1/admin/users',
        json={
            'username': 'newadmin',
            'email': 'newadmin@example.com',
            'password': 'newpass123',
            'is_superuser': False,
        },
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    data = response.json()
    assert data['username'] == 'newadmin'
    assert data['email'] == 'newadmin@example.com'
    assert data['is_superuser'] is False


def test_create_admin_user_unauthorized(client, regular_admin_user):
    """Test creating admin user without superuser privileges"""
    # Login as regular user
    login_response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'regularadmin', 'password': 'testpass123'},
    )
    token = login_response.json()['access_token']

    # Try to create new user
    response = client.post(
        '/football/api/v1/admin/users',
        json={
            'username': 'newadmin',
            'email': 'newadmin@example.com',
            'password': 'newpass123',
            'is_superuser': False,
        },
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 403


def test_list_admin_users(client, admin_user, regular_admin_user):
    """Test listing admin users"""
    # Login as superuser
    login_response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'testadmin', 'password': 'testpass123'},
    )
    token = login_response.json()['access_token']

    # List users
    response = client.get(
        '/football/api/v1/admin/users', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2  # At least our test users

    usernames = [user['username'] for user in data]
    assert 'testadmin' in usernames
    assert 'regularadmin' in usernames


def test_update_admin_user(client, admin_user, regular_admin_user):
    """Test updating admin user"""
    # Login as superuser
    login_response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'testadmin', 'password': 'testpass123'},
    )
    token = login_response.json()['access_token']

    # Update user
    response = client.put(
        f'/football/api/v1/admin/users/{regular_admin_user.id}',
        json={'username': 'updatedadmin', 'is_active': False},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    data = response.json()
    assert data['username'] == 'updatedadmin'
    assert data['is_active'] is False


def test_change_password_success(client, admin_user):
    """Test changing password"""
    # Login
    login_response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'testadmin', 'password': 'testpass123'},
    )
    token = login_response.json()['access_token']

    # Change password
    response = client.post(
        '/football/api/v1/admin/change-password',
        json={'current_password': 'testpass123', 'new_password': 'newpass123'},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert 'Password changed successfully' in response.json()['message']


def test_change_password_wrong_current(client, admin_user):
    """Test changing password with wrong current password"""
    # Login
    login_response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'testadmin', 'password': 'testpass123'},
    )
    token = login_response.json()['access_token']

    # Try to change password with wrong current password
    response = client.post(
        '/football/api/v1/admin/change-password',
        json={'current_password': 'wrongpassword', 'new_password': 'newpass123'},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 400
    assert 'Current password is incorrect' in response.json()['detail']


def test_delete_admin_user(client, admin_user, regular_admin_user):
    """Test deleting admin user"""
    # Login as superuser
    login_response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'testadmin', 'password': 'testpass123'},
    )
    token = login_response.json()['access_token']

    # Delete user
    response = client.delete(
        f'/football/api/v1/admin/users/{regular_admin_user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert 'User deleted successfully' in response.json()['message']


def test_delete_own_account(client, admin_user):
    """Test preventing deletion of own account"""
    # Login
    login_response = client.post(
        '/football/api/v1/admin/login',
        json={'username': 'testadmin', 'password': 'testpass123'},
    )
    token = login_response.json()['access_token']

    # Try to delete own account
    response = client.delete(
        f'/football/api/v1/admin/users/{admin_user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 400
    assert 'Cannot delete your own account' in response.json()['detail']


def test_admin_panel_access(client):
    """Test admin panel is accessible"""
    response = client.get('/admin/')
    # Should redirect to login or show login page
    assert response.status_code in [200, 302]

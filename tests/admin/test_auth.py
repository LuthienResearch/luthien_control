"""Tests for admin authentication."""

from datetime import datetime, timedelta

import bcrypt
import pytest
from luthien_control.models.admin_user import AdminSession, AdminUser


@pytest.mark.asyncio
async def test_create_admin_user():
    """Test creating an admin user model."""
    # Test the model creation directly
    user = AdminUser(
        username="testadmin",
        password_hash="$2b$12$hashedpassword",
        is_active=True,
        is_superuser=True,
    )

    assert user.username == "testadmin"
    assert user.is_superuser is True
    assert user.is_active is True
    assert user.password_hash != "testpass123"  # Should be hashed


@pytest.mark.asyncio
async def test_password_hashing():
    """Test password hashing functionality."""
    password = "testpass123"
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    # Verify password can be checked
    assert bcrypt.checkpw(password.encode("utf-8"), password_hash)
    assert not bcrypt.checkpw("wrongpass".encode("utf-8"), password_hash)


@pytest.mark.asyncio
async def test_admin_session_model():
    """Test creating an admin session model."""
    expires_at = datetime.utcnow() + timedelta(hours=24)

    session = AdminSession(
        session_token="test_token_123",
        admin_user_id=1,
        expires_at=expires_at,
    )

    assert session.session_token == "test_token_123"
    assert session.admin_user_id == 1
    assert session.expires_at == expires_at


@pytest.mark.asyncio
async def test_admin_user_defaults():
    """Test admin user default values."""
    user = AdminUser(
        username="testuser",
        password_hash="hashed",
    )

    # Test default values
    assert user.is_active is True  # Default should be True
    assert user.is_superuser is False  # Default should be False
    assert user.last_login is None  # Should start as None

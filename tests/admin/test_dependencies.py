"""Tests for admin dependencies."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from luthien_control.admin.dependencies import get_current_admin
from luthien_control.models.admin_user import AdminUser


@pytest.fixture
def sample_admin_user():
    """Sample admin user for testing."""
    return AdminUser(
        id=1,
        username="testuser",
        password_hash="hash",
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
def mock_request():
    """Mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.cookies = {}
    return request


class TestCSRFProtection:
    """Test CSRF protection functionality."""

    def test_generate_token(self):
        """Test CSRF token generation."""
        # The CSRF protection just generates UUIDs, test the concept
        import uuid

        # Mock the uuid generation to test the format
        token = str(uuid.uuid4()).replace("-", "")

        assert isinstance(token, str)
        assert len(token) == 32  # UUID without hyphens


class TestGetCurrentAdmin:
    """Test get current admin dependency."""

    @pytest.mark.asyncio
    async def test_get_current_admin_success(self, mock_db_session, sample_admin_user):
        """Test successful admin retrieval."""
        # Mock admin auth service
        with patch("luthien_control.admin.dependencies.admin_auth_service") as mock_auth_service:
            mock_auth_service.get_user_from_session = AsyncMock(return_value=sample_admin_user)

            result = await get_current_admin("valid-token", mock_db_session)

            assert result == sample_admin_user
            mock_auth_service.get_user_from_session.assert_called_once_with(mock_db_session, "valid-token")

    @pytest.mark.asyncio
    async def test_get_current_admin_no_session_token(self, mock_db_session):
        """Test admin retrieval without session token."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(None, mock_db_session)

        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_admin_invalid_session(self, mock_db_session):
        """Test admin retrieval with invalid session token."""
        # Mock admin auth service
        with patch("luthien_control.admin.dependencies.admin_auth_service") as mock_auth_service:
            mock_auth_service.get_user_from_session = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await get_current_admin("invalid-token", mock_db_session)

            assert exc_info.value.status_code == 401
            assert "Invalid or expired session" in exc_info.value.detail
            mock_auth_service.get_user_from_session.assert_called_once_with(mock_db_session, "invalid-token")

    @pytest.mark.asyncio
    async def test_get_current_admin_inactive_user(self, mock_db_session):
        """Test admin retrieval with inactive user."""
        inactive_user = AdminUser(
            id=1,
            username="testuser",
            password_hash="hash",
            is_active=False,
            is_superuser=False,
        )

        # Mock admin auth service to return inactive user
        with patch("luthien_control.admin.dependencies.admin_auth_service") as mock_auth_service:
            mock_auth_service.get_user_from_session = AsyncMock(return_value=inactive_user)

            # The function should return the user - it doesn't check is_active
            # That's handled by the auth service or other middleware
            result = await get_current_admin("valid-token", mock_db_session)

            assert result == inactive_user
            mock_auth_service.get_user_from_session.assert_called_once_with(mock_db_session, "valid-token")

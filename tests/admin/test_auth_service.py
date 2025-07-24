"""Tests for admin auth service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from luthien_control.admin.auth import AdminAuthService
from luthien_control.db.sqlmodel_models import AdminSession, AdminUser


@pytest.fixture
def auth_service():
    """Create admin auth service instance."""
    return AdminAuthService()


@pytest.fixture
def sample_admin_user():
    """Sample admin user for testing."""
    return AdminUser(
        id=1,
        username="testuser",
        password_hash="hashed_password",
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
def sample_admin_session():
    """Sample admin session for testing."""
    return AdminSession(
        id=1,
        session_token="test-token",
        admin_user_id=1,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24),
    )


class TestAdminAuthService:
    """Test admin authentication service."""

    @pytest.mark.asyncio
    async def test_ensure_default_admin_no_existing_users(self, auth_service, mock_db_session):
        """Test ensuring default admin when no users exist."""
        # Mock CRUD operations
        with patch("luthien_control.admin.auth.admin_user_crud") as mock_crud:
            mock_crud.list_all = AsyncMock(return_value=[])  # No existing users
            mock_crud.create = AsyncMock()

            # Mock environment variables
            with patch.dict("os.environ", {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "secret"}):
                await auth_service.ensure_default_admin(mock_db_session)

                mock_crud.create.assert_called_once_with(
                    mock_db_session,
                    username="admin",
                    password="secret",
                    is_superuser=True,
                )

    @pytest.mark.asyncio
    async def test_ensure_default_admin_with_existing_users(self, auth_service, mock_db_session, sample_admin_user):
        """Test ensuring default admin when users already exist."""
        # Mock CRUD operations
        with patch("luthien_control.admin.auth.admin_user_crud") as mock_crud:
            mock_crud.list_all = AsyncMock(return_value=[sample_admin_user])  # Existing users
            mock_crud.create = AsyncMock()

            await auth_service.ensure_default_admin(mock_db_session)

            # Should not create a new user
            mock_crud.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_service, mock_db_session, sample_admin_user):
        """Test successful authentication."""
        # Mock CRUD operations
        with (
            patch("luthien_control.admin.auth.admin_session_crud") as mock_session_crud,
            patch("luthien_control.admin.auth.admin_user_crud") as mock_user_crud,
        ):
            mock_session_crud.cleanup_expired_sessions = AsyncMock()
            mock_user_crud.verify_password = AsyncMock(return_value=sample_admin_user)

            result = await auth_service.authenticate(mock_db_session, "testuser", "password")

            assert result == sample_admin_user
            mock_session_crud.cleanup_expired_sessions.assert_called_once_with(mock_db_session)
            mock_user_crud.verify_password.assert_called_once_with(mock_db_session, "testuser", "password")

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, auth_service, mock_db_session):
        """Test failed authentication."""
        # Mock CRUD operations
        with (
            patch("luthien_control.admin.auth.admin_session_crud") as mock_session_crud,
            patch("luthien_control.admin.auth.admin_user_crud") as mock_user_crud,
        ):
            mock_session_crud.cleanup_expired_sessions = AsyncMock()
            mock_user_crud.verify_password = AsyncMock(return_value=None)

            result = await auth_service.authenticate(mock_db_session, "testuser", "wrongpassword")

            assert result is None
            mock_session_crud.cleanup_expired_sessions.assert_called_once_with(mock_db_session)
            mock_user_crud.verify_password.assert_called_once_with(mock_db_session, "testuser", "wrongpassword")

    @pytest.mark.asyncio
    async def test_create_session(self, auth_service, mock_db_session, sample_admin_user, sample_admin_session):
        """Test creating a session."""
        # Mock CRUD operations
        with patch("luthien_control.admin.auth.admin_session_crud") as mock_session_crud:
            mock_session_crud.create_session = AsyncMock(return_value=sample_admin_session)

            # Mock environment variable
            with patch.dict("os.environ", {"ADMIN_SESSION_HOURS": "12"}):
                result = await auth_service.create_session(mock_db_session, sample_admin_user)

                assert result == sample_admin_session
                mock_session_crud.create_session.assert_called_once_with(mock_db_session, 1, hours=12)

    @pytest.mark.asyncio
    async def test_create_session_user_without_id(self, auth_service, mock_db_session):
        """Test creating a session for user without ID."""
        user_without_id = AdminUser(
            username="testuser",
            password_hash="hash",
            is_active=True,
        )

        with pytest.raises(ValueError, match="Admin user ID is None"):
            await auth_service.create_session(mock_db_session, user_without_id)

    @pytest.mark.asyncio
    async def test_get_user_from_session_valid(
        self, auth_service, mock_db_session, sample_admin_user, sample_admin_session
    ):
        """Test getting user from valid session."""
        # Mock CRUD operations
        with (
            patch("luthien_control.admin.auth.admin_session_crud") as mock_session_crud,
            patch("luthien_control.admin.auth.admin_user_crud") as mock_user_crud,
        ):
            mock_session_crud.get_valid_session = AsyncMock(return_value=sample_admin_session)
            mock_user_crud.get_by_id = AsyncMock(return_value=sample_admin_user)

            result = await auth_service.get_user_from_session(mock_db_session, "test-token")

            assert result == sample_admin_user
            mock_session_crud.get_valid_session.assert_called_once_with(mock_db_session, "test-token")
            mock_user_crud.get_by_id.assert_called_once_with(mock_db_session, 1)

    @pytest.mark.asyncio
    async def test_get_user_from_session_invalid_session(self, auth_service, mock_db_session):
        """Test getting user from invalid session."""
        # Mock CRUD operations
        with patch("luthien_control.admin.auth.admin_session_crud") as mock_session_crud:
            mock_session_crud.get_valid_session = AsyncMock(return_value=None)

            result = await auth_service.get_user_from_session(mock_db_session, "invalid-token")

            assert result is None
            mock_session_crud.get_valid_session.assert_called_once_with(mock_db_session, "invalid-token")

    @pytest.mark.asyncio
    async def test_get_user_from_session_inactive_user(self, auth_service, mock_db_session, sample_admin_session):
        """Test getting inactive user from session."""
        inactive_user = AdminUser(
            id=1,
            username="testuser",
            password_hash="hash",
            is_active=False,
        )

        # Mock CRUD operations
        with (
            patch("luthien_control.admin.auth.admin_session_crud") as mock_session_crud,
            patch("luthien_control.admin.auth.admin_user_crud") as mock_user_crud,
        ):
            mock_session_crud.get_valid_session = AsyncMock(return_value=sample_admin_session)
            mock_user_crud.get_by_id = AsyncMock(return_value=inactive_user)

            result = await auth_service.get_user_from_session(mock_db_session, "test-token")

            assert result is None

    @pytest.mark.asyncio
    async def test_logout_success(self, auth_service, mock_db_session):
        """Test successful logout."""
        # Mock CRUD operations
        with patch("luthien_control.admin.auth.admin_session_crud") as mock_session_crud:
            mock_session_crud.delete_session = AsyncMock(return_value=True)

            result = await auth_service.logout(mock_db_session, "test-token")

            assert result is True
            mock_session_crud.delete_session.assert_called_once_with(mock_db_session, "test-token")

    @pytest.mark.asyncio
    async def test_logout_session_not_found(self, auth_service, mock_db_session):
        """Test logout when session not found."""
        # Mock CRUD operations
        with patch("luthien_control.admin.auth.admin_session_crud") as mock_session_crud:
            mock_session_crud.delete_session = AsyncMock(return_value=False)

            result = await auth_service.logout(mock_db_session, "nonexistent-token")

            assert result is False
            mock_session_crud.delete_session.assert_called_once_with(mock_db_session, "nonexistent-token")

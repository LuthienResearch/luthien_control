"""Tests for admin user CRUD operations."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import bcrypt
import pytest
from luthien_control.admin.crud.admin_user import admin_session_crud, admin_user_crud
from luthien_control.models.admin_user import AdminSession, AdminUser


@pytest.fixture
def sample_admin_user():
    """Sample admin user for testing."""
    return AdminUser(
        id=1,
        username="testuser",
        password_hash=bcrypt.hashpw("testpass".encode(), bcrypt.gensalt()).decode(),
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


class TestAdminUserCrud:
    """Test admin user CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_admin_user(self, mock_db_session):
        """Test creating an admin user."""
        username = "newuser"
        password = "newpass"

        # Mock database operations
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await admin_user_crud.create(mock_db_session, username=username, password=password, is_superuser=True)

        assert result.username == username
        assert result.is_superuser is True
        assert result.is_active is True
        assert bcrypt.checkpw(password.encode(), result.password_hash.encode())
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_username(self, mock_db_session, sample_admin_user):
        """Test getting admin user by username."""
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_admin_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await admin_user_crud.get_by_username(mock_db_session, "testuser")

        assert result == sample_admin_user
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_username_not_found(self, mock_db_session):
        """Test getting admin user by username when not found."""
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await admin_user_crud.get_by_username(mock_db_session, "nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id(self, mock_db_session, sample_admin_user):
        """Test getting admin user by ID."""
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_admin_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await admin_user_crud.get_by_id(mock_db_session, 1)

        assert result == sample_admin_user
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_all(self, mock_db_session, sample_admin_user):
        """Test listing all admin users."""
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_admin_user]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await admin_user_crud.list_all(mock_db_session)

        assert result == [sample_admin_user]
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_password_success(self, mock_db_session, sample_admin_user):
        """Test successful password verification."""
        # Mock get_by_username
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_admin_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()

        result = await admin_user_crud.verify_password(mock_db_session, "testuser", "testpass")

        assert result == sample_admin_user
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_password_wrong_password(self, mock_db_session, sample_admin_user):
        """Test password verification with wrong password."""
        # Mock get_by_username
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_admin_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await admin_user_crud.verify_password(mock_db_session, "testuser", "wrongpass")

        assert result is None

    @pytest.mark.asyncio
    async def test_verify_password_inactive_user(self, mock_db_session, sample_admin_user):
        """Test password verification with inactive user."""
        sample_admin_user.is_active = False

        # Mock get_by_username
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_admin_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await admin_user_crud.verify_password(mock_db_session, "testuser", "testpass")

        assert result is None


class TestAdminSessionCrud:
    """Test admin session CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_session(self, mock_db_session):
        """Test creating an admin session."""
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await admin_session_crud.create_session(mock_db_session, admin_user_id=1, hours=24)

        assert result.admin_user_id == 1
        assert len(result.session_token) == 43  # secrets.token_urlsafe(32) generates 43 chars
        assert result.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_valid_session(self, mock_db_session, sample_admin_session):
        """Test getting a valid session."""
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_admin_session
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await admin_session_crud.get_valid_session(mock_db_session, "test-token")

        assert result == sample_admin_session
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_valid_session_expired(self, mock_db_session):
        """Test getting an expired session."""
        # For expired session, the query should return None since it filters by expires_at > now
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await admin_session_crud.get_valid_session(mock_db_session, "expired-token")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session(self, mock_db_session, sample_admin_session):
        """Test deleting a session."""
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_admin_session
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()  # delete is async
        mock_db_session.commit = AsyncMock()

        result = await admin_session_crud.delete_session(mock_db_session, "test-token")

        assert result is True
        mock_db_session.delete.assert_called_once_with(sample_admin_session)
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, mock_db_session):
        """Test deleting a session that doesn't exist."""
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await admin_session_crud.delete_session(mock_db_session, "nonexistent-token")

        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, mock_db_session):
        """Test cleaning up expired sessions."""
        # Create some mock expired sessions
        expired_session1 = AdminSession(
            id=1,
            session_token="token1",
            admin_user_id=1,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
        )
        expired_session2 = AdminSession(
            id=2,
            session_token="token2",
            admin_user_id=1,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expired_session1, expired_session2]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()

        result = await admin_session_crud.cleanup_expired_sessions(mock_db_session)

        assert result == 2
        mock_db_session.execute.assert_called_once()
        assert mock_db_session.delete.call_count == 2
        mock_db_session.commit.assert_called_once()

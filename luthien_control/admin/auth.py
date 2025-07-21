"""Authentication logic for admin users."""

import logging
import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.admin.crud.admin_user import admin_session_crud, admin_user_crud
from luthien_control.models.admin_user import AdminSession, AdminUser

logger = logging.getLogger(__name__)


class AdminAuthService:
    """Service for admin authentication operations."""

    async def ensure_default_admin(self, db: AsyncSession) -> None:
        """Ensure a default admin user exists."""
        # Check if any admin users exist
        admins = await admin_user_crud.list_all(db)
        if admins:
            return

        # Create default admin from environment variables
        default_username = os.getenv("ADMIN_USERNAME", "admin")
        default_password = os.getenv("ADMIN_PASSWORD", "changeme")

        logger.warning(f"Creating default admin user '{default_username}'. Please change the password immediately!")

        await admin_user_crud.create(
            db,
            username=default_username,
            password=default_password,
            is_superuser=True,
        )

    async def authenticate(self, db: AsyncSession, username: str, password: str) -> Optional[AdminUser]:
        """Authenticate admin user."""
        # Clean up expired sessions
        await admin_session_crud.cleanup_expired_sessions(db)

        # Verify credentials
        return await admin_user_crud.verify_password(db, username, password)

    async def create_session(self, db: AsyncSession, admin_user: AdminUser) -> AdminSession:
        """Create a new session for authenticated user."""
        session_hours = int(os.getenv("ADMIN_SESSION_HOURS", "24"))
        if admin_user.id is None:
            raise ValueError("Admin user ID is None")
        return await admin_session_crud.create_session(db, admin_user.id, hours=session_hours)

    async def get_user_from_session(self, db: AsyncSession, session_token: str) -> Optional[AdminUser]:
        """Get admin user from session token."""
        session = await admin_session_crud.get_valid_session(db, session_token)
        if not session:
            return None

        user = await admin_user_crud.get_by_id(db, session.admin_user_id)
        if not user or not user.is_active:
            return None

        return user

    async def logout(self, db: AsyncSession, session_token: str) -> bool:
        """Logout by deleting session."""
        return await admin_session_crud.delete_session(db, session_token)


admin_auth_service = AdminAuthService()

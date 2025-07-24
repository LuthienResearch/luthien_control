"""CRUD operations for admin users."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import bcrypt
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.models.admin_user import AdminSession, AdminUser


class AdminUserCRUD:
    """CRUD operations for admin users."""

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[AdminUser]:
        """Get admin user by username."""
        result = await db.execute(select(AdminUser).where(AdminUser.username == username))  # type: ignore
        return result.scalar_one_or_none()

    async def get_by_id(self, db: AsyncSession, user_id: int) -> Optional[AdminUser]:
        """Get admin user by ID."""
        result = await db.execute(select(AdminUser).where(AdminUser.id == user_id))  # type: ignore
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        username: str,
        password: str,
        is_superuser: bool = False,
    ) -> AdminUser:
        """Create a new admin user."""
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        admin_user = AdminUser(
            username=username,
            password_hash=password_hash.decode("utf-8"),
            is_superuser=is_superuser,
        )

        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)
        return admin_user

    async def verify_password(self, db: AsyncSession, username: str, password: str) -> Optional[AdminUser]:
        """Verify username and password."""
        user = await self.get_by_username(db, username)
        if not user or not user.is_active:
            return None

        if bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            # Update last login
            user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()
            return user

        return None

    async def list_all(self, db: AsyncSession) -> List[AdminUser]:
        """List all admin users."""
        result = await db.execute(select(AdminUser).order_by(AdminUser.created_at))  # type: ignore
        return list(result.scalars().all())


class AdminSessionCRUD:
    """CRUD operations for admin sessions."""

    async def create_session(self, db: AsyncSession, admin_user_id: int, hours: int = 24) -> AdminSession:
        """Create a new admin session."""
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=hours)

        session = AdminSession(
            session_token=session_token,
            admin_user_id=admin_user_id,
            expires_at=expires_at,
        )

        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_valid_session(self, db: AsyncSession, session_token: str) -> Optional[AdminSession]:
        """Get a valid (non-expired) session by token."""
        result = await db.execute(
            select(AdminSession).where(
                and_(
                    AdminSession.session_token == session_token,  # type: ignore
                    AdminSession.expires_at > datetime.now(timezone.utc).replace(tzinfo=None),  # type: ignore
                )
            )
        )
        return result.scalar_one_or_none()

    async def delete_session(self, db: AsyncSession, session_token: str) -> bool:
        """Delete a session (logout)."""
        result = await db.execute(select(AdminSession).where(AdminSession.session_token == session_token))  # type: ignore
        session = result.scalar_one_or_none()

        if session:
            await db.delete(session)
            await db.commit()
            return True

        return False

    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        """Clean up expired sessions."""
        result = await db.execute(
            select(AdminSession).where(AdminSession.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None))  # type: ignore
        )
        expired_sessions = list(result.scalars().all())

        count = len(expired_sessions)
        for session in expired_sessions:
            await db.delete(session)

        if count > 0:
            await db.commit()

        return count


admin_user_crud = AdminUserCRUD()
admin_session_crud = AdminSessionCRUD()

"""Tests for admin router."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from luthien_control.db.sqlmodel_models import ControlPolicy
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
def sample_policy():
    """Sample control policy for testing."""
    return ControlPolicy(
        id=1,
        name="test_policy",
        type="backend_call",
        config={"backend_url": "https://api.example.com"},
        description="Test policy",
        is_active=True,
    )


@pytest.fixture
def mock_request():
    """Mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.url.scheme = "http"
    request.cookies = {}
    return request


class TestAdminRouterFunctions:
    """Test admin router functions directly."""

    @pytest.mark.asyncio
    async def test_login_page_function(self, mock_request):
        """Test login page function."""
        from luthien_control.admin.router import login_page

        with (
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
            patch("luthien_control.admin.router.templates") as mock_templates,
        ):
            mock_csrf.return_value = "csrf-token"
            mock_response = MagicMock()
            mock_templates.TemplateResponse.return_value = mock_response
            mock_response.set_cookie = MagicMock()

            result = await login_page(mock_request)

            assert result == mock_response
            mock_csrf.assert_called_once()
            mock_response.set_cookie.assert_called_once()

    def test_login_post_success(self, client):
        """Test successful login POST."""
        # Mock dependencies
        with (
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
            patch("luthien_control.admin.router.admin_auth_service") as mock_auth_service,
        ):
            mock_csrf.return_value = "csrf-token"
            mock_user = AdminUser(id=1, username="admin", password_hash="hash", is_active=True)
            mock_session = MagicMock()
            mock_session.session_token = "session-token"

            mock_auth_service.authenticate = AsyncMock(return_value=mock_user)
            mock_auth_service.create_session = AsyncMock(return_value=mock_session)

            # First get the login page to set CSRF token
            login_response = client.get("/admin/login")
            csrf_token = login_response.cookies["csrf_token"]

            # Then submit login form
            response = client.post(
                "/admin/login",
                data={
                    "username": "admin",
                    "password": "password",
                    "csrf_token": csrf_token,
                },
                cookies={"csrf_token": csrf_token},
            )

            assert response.status_code == 303
            assert response.headers["location"] == "/admin/policies"
            assert "session_token" in response.cookies

    def test_login_post_invalid_csrf(self, client):
        """Test login POST with invalid CSRF token."""
        response = client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "password",
                "csrf_token": "invalid-token",
            },
            cookies={"csrf_token": "different-token"},
        )

        assert response.status_code == 400

    def test_login_post_invalid_credentials(self, client):
        """Test login POST with invalid credentials."""
        with (
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
            patch("luthien_control.admin.router.admin_auth_service") as mock_auth_service,
        ):
            mock_csrf.return_value = "csrf-token"
            mock_auth_service.authenticate = AsyncMock(return_value=None)

            # First get the login page to set CSRF token
            login_response = client.get("/admin/login")
            csrf_token = login_response.cookies["csrf_token"]

            # Then submit login form with wrong credentials
            response = client.post(
                "/admin/login",
                data={
                    "username": "admin",
                    "password": "wrongpassword",
                    "csrf_token": csrf_token,
                },
                cookies={"csrf_token": csrf_token},
            )

            assert response.status_code == 401
            assert b"Invalid username or password" in response.content

    def test_logout(self, client):
        """Test logout endpoint."""
        with patch("luthien_control.admin.router.admin_auth_service") as mock_auth_service:
            mock_auth_service.logout = AsyncMock()

            response = client.get("/admin/logout", cookies={"session_token": "test-token"})

            assert response.status_code == 303
            assert response.headers["location"] == "/admin/login"
            mock_auth_service.logout.assert_called_once()

    def test_admin_home(self, client, sample_admin_user, sample_policy):
        """Test admin dashboard home page."""
        with (
            patch("luthien_control.admin.router.get_current_admin") as mock_get_admin,
            patch("luthien_control.admin.router.list_policies") as mock_list_policies,
        ):
            mock_get_admin.return_value = sample_admin_user
            mock_list_policies.return_value = [sample_policy]

            response = client.get("/admin/")

            assert response.status_code == 200
            assert b"Admin Dashboard" in response.content

    def test_policies_list(self, client, sample_admin_user, sample_policy):
        """Test policies list page."""
        with (
            patch("luthien_control.admin.router.get_current_admin") as mock_get_admin,
            patch("luthien_control.admin.router.list_policies") as mock_list_policies,
        ):
            mock_get_admin.return_value = sample_admin_user
            mock_list_policies.return_value = [sample_policy]

            response = client.get("/admin/policies")

            assert response.status_code == 200
            assert b"test_policy" in response.content

    def test_edit_policy_page(self, client, sample_admin_user, sample_policy):
        """Test edit policy page."""
        with (
            patch("luthien_control.admin.router.get_current_admin") as mock_get_admin,
            patch("luthien_control.admin.router.get_policy_by_name") as mock_get_policy,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            mock_get_admin.return_value = sample_admin_user
            mock_get_policy.return_value = sample_policy
            mock_csrf.return_value = "csrf-token"

            response = client.get("/admin/policies/test_policy/edit")

            assert response.status_code == 200
            assert b"test_policy" in response.content
            assert b"backend_url" in response.content

    def test_edit_policy_page_not_found(self, client, sample_admin_user):
        """Test edit policy page for non-existent policy."""
        with (
            patch("luthien_control.admin.router.get_current_admin") as mock_get_admin,
            patch("luthien_control.admin.router.get_policy_by_name") as mock_get_policy,
        ):
            mock_get_admin.return_value = sample_admin_user
            mock_get_policy.return_value = None

            response = client.get("/admin/policies/nonexistent/edit")

            assert response.status_code == 404

    def test_update_policy_success(self, client, sample_admin_user, sample_policy):
        """Test successful policy update."""
        with (
            patch("luthien_control.admin.router.get_current_admin") as mock_get_admin,
            patch("luthien_control.admin.router.get_policy_by_name") as mock_get_policy,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            mock_get_admin.return_value = sample_admin_user
            mock_get_policy.return_value = sample_policy
            mock_csrf.return_value = "csrf-token"

            # First get the edit page to set up CSRF
            edit_response = client.get("/admin/policies/test_policy/edit")
            csrf_token = edit_response.cookies["csrf_token"]

            # Then submit update form
            new_config = {"backend_url": "https://api.updated.com"}
            response = client.post(
                "/admin/policies/test_policy/edit",
                data={
                    "config": json.dumps(new_config),
                    "description": "Updated policy",
                    "is_active": "on",
                    "csrf_token": csrf_token,
                },
                cookies={"csrf_token": csrf_token},
            )

            assert response.status_code == 303
            assert response.headers["location"] == "/admin/policies"

    def test_update_policy_invalid_json(self, client, sample_admin_user, sample_policy):
        """Test policy update with invalid JSON."""
        with (
            patch("luthien_control.admin.router.get_current_admin") as mock_get_admin,
            patch("luthien_control.admin.router.get_policy_by_name") as mock_get_policy,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            mock_get_admin.return_value = sample_admin_user
            mock_get_policy.return_value = sample_policy
            mock_csrf.return_value = "csrf-token"

            # First get the edit page to set up CSRF
            edit_response = client.get("/admin/policies/test_policy/edit")
            csrf_token = edit_response.cookies["csrf_token"]

            # Then submit update form with invalid JSON
            response = client.post(
                "/admin/policies/test_policy/edit",
                data={
                    "config": "{invalid json}",
                    "csrf_token": csrf_token,
                },
                cookies={"csrf_token": csrf_token},
            )

            assert response.status_code == 400
            assert b"Invalid JSON" in response.content

    def test_new_policy_page(self, client, sample_admin_user):
        """Test new policy creation page."""
        with (
            patch("luthien_control.admin.router.get_current_admin") as mock_get_admin,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            mock_get_admin.return_value = sample_admin_user
            mock_csrf.return_value = "csrf-token"

            response = client.get("/admin/policies/new")

            assert response.status_code == 200
            assert b"Create New Policy" in response.content

    def test_create_policy_success(self, client, sample_admin_user):
        """Test successful policy creation."""
        with (
            patch("luthien_control.admin.router.get_current_admin") as mock_get_admin,
            patch("luthien_control.admin.router.save_policy_to_db") as mock_save,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            mock_get_admin.return_value = sample_admin_user
            mock_save.return_value = AsyncMock()
            mock_csrf.return_value = "csrf-token"

            # First get the new policy page to set up CSRF
            new_response = client.get("/admin/policies/new")
            csrf_token = new_response.cookies["csrf_token"]

            # Then submit creation form
            config = {"backend_url": "https://api.new.com"}
            response = client.post(
                "/admin/policies/new",
                data={
                    "name": "new_policy",
                    "type": "backend_call",
                    "config": json.dumps(config),
                    "description": "New policy",
                    "is_active": "on",
                    "csrf_token": csrf_token,
                },
                cookies={"csrf_token": csrf_token},
            )

            assert response.status_code == 303
            assert response.headers["location"] == "/admin/policies"

    def test_create_policy_invalid_json(self, client, sample_admin_user):
        """Test policy creation with invalid JSON."""
        with (
            patch("luthien_control.admin.router.get_current_admin") as mock_get_admin,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            mock_get_admin.return_value = sample_admin_user
            mock_csrf.return_value = "csrf-token"

            # First get the new policy page to set up CSRF
            new_response = client.get("/admin/policies/new")
            csrf_token = new_response.cookies["csrf_token"]

            # Then submit creation form with invalid JSON
            response = client.post(
                "/admin/policies/new",
                data={
                    "name": "new_policy",
                    "type": "backend_call",
                    "config": "{invalid json}",
                    "csrf_token": csrf_token,
                },
                cookies={"csrf_token": csrf_token},
            )

            assert response.status_code == 400
            assert b"Invalid JSON" in response.content

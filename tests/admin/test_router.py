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

    def test_login_post_success(self, admin_client_with_full_mocking):
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
            login_response = admin_client_with_full_mocking.get("/admin/login")
            csrf_token = login_response.cookies["csrf_token"]

            # Then submit login form - disable following redirects to avoid hitting the policies page
            response = admin_client_with_full_mocking.post(
                "/admin/login",
                data={
                    "username": "admin",
                    "password": "password",
                    "csrf_token": csrf_token,
                },
                cookies={"csrf_token": csrf_token},
                follow_redirects=False,
            )

            assert response.status_code == 303
            assert response.headers["location"] == "/admin/policies"
            assert "session_token" in response.cookies

    def test_login_post_invalid_csrf(self, admin_client_with_full_mocking):
        """Test login POST with invalid CSRF token."""
        response = admin_client_with_full_mocking.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "password",
                "csrf_token": "invalid-token",
            },
            cookies={"csrf_token": "different-token"},
        )

        assert response.status_code == 400

    def test_login_post_invalid_credentials(self, admin_client_with_full_mocking):
        """Test login POST with invalid credentials."""
        with (
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
            patch("luthien_control.admin.router.admin_auth_service") as mock_auth_service,
        ):
            mock_csrf.return_value = "csrf-token"
            mock_auth_service.authenticate = AsyncMock(return_value=None)

            # First get the login page to set CSRF token
            login_response = admin_client_with_full_mocking.get("/admin/login")
            csrf_token = login_response.cookies["csrf_token"]

            # Then submit login form with wrong credentials
            response = admin_client_with_full_mocking.post(
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

    def test_logout(self, admin_client_with_full_mocking):
        """Test logout endpoint."""
        with patch("luthien_control.admin.router.admin_auth_service") as mock_auth_service:
            mock_auth_service.logout = AsyncMock()

            response = admin_client_with_full_mocking.get(
                "/admin/logout", cookies={"session_token": "test-token"}, follow_redirects=False
            )

            assert response.status_code == 303
            assert response.headers["location"] == "/admin/login"
            mock_auth_service.logout.assert_called_once()

    def test_admin_home(self, sample_admin_user, sample_policy):
        """Test admin dashboard home page."""
        from fastapi.testclient import TestClient
        from luthien_control.admin.dependencies import get_current_admin
        from luthien_control.main import app

        # Override dependencies
        def mock_get_current_admin():
            return sample_admin_user

        async def mock_list_policies(db, active_only=False):
            return [sample_policy]

        app.dependency_overrides[get_current_admin] = mock_get_current_admin

        with (
            patch("luthien_control.main.initialize_app_dependencies") as mock_init_deps,
            patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin") as mock_ensure_admin,
            patch("luthien_control.admin.router.list_policies", side_effect=mock_list_policies),
        ):
            # Mock app initialization
            mock_container = MagicMock()

            # Create a proper async context manager for db_session_factory
            mock_db_session = AsyncMock()
            mock_async_cm = AsyncMock()
            mock_async_cm.__aenter__.return_value = mock_db_session
            mock_async_cm.__aexit__.return_value = None

            mock_factory = MagicMock(return_value=mock_async_cm)
            mock_container.db_session_factory = mock_factory

            # Mock http_client
            mock_http_client = AsyncMock()
            mock_http_client.aclose = AsyncMock()
            mock_container.http_client = mock_http_client

            mock_init_deps.return_value = mock_container
            mock_ensure_admin.return_value = None

            try:
                with TestClient(app) as client:
                    response = client.get("/admin/")

                    assert response.status_code == 200
                    assert b"Admin Dashboard" in response.content
            finally:
                # Clean up dependency override
                if get_current_admin in app.dependency_overrides:
                    del app.dependency_overrides[get_current_admin]

    def test_policies_list(self, sample_admin_user, sample_policy):
        """Test policies list page."""
        from fastapi.testclient import TestClient
        from luthien_control.admin.dependencies import get_current_admin
        from luthien_control.main import app

        # Override dependencies
        def mock_get_current_admin():
            return sample_admin_user

        async def mock_list_policies(db, active_only=False):
            return [sample_policy]

        app.dependency_overrides[get_current_admin] = mock_get_current_admin

        with (
            patch("luthien_control.main.initialize_app_dependencies") as mock_init_deps,
            patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin") as mock_ensure_admin,
            patch("luthien_control.admin.router.list_policies", side_effect=mock_list_policies),
        ):
            # Mock app initialization
            mock_container = MagicMock()

            # Create a proper async context manager for db_session_factory
            mock_db_session = AsyncMock()
            mock_async_cm = AsyncMock()
            mock_async_cm.__aenter__.return_value = mock_db_session
            mock_async_cm.__aexit__.return_value = None

            mock_factory = MagicMock(return_value=mock_async_cm)
            mock_container.db_session_factory = mock_factory

            # Mock http_client
            mock_http_client = AsyncMock()
            mock_http_client.aclose = AsyncMock()
            mock_container.http_client = mock_http_client

            mock_init_deps.return_value = mock_container
            mock_ensure_admin.return_value = None

            try:
                with TestClient(app) as client:
                    response = client.get("/admin/policies")

                    assert response.status_code == 200
                    assert b"test_policy" in response.content
            finally:
                # Clean up dependency override
                if get_current_admin in app.dependency_overrides:
                    del app.dependency_overrides[get_current_admin]

    def test_edit_policy_page(self, sample_admin_user, sample_policy):
        """Test edit policy page."""
        from fastapi.testclient import TestClient
        from luthien_control.admin.dependencies import get_current_admin
        from luthien_control.main import app

        # Override dependencies
        def mock_get_current_admin():
            return sample_admin_user

        app.dependency_overrides[get_current_admin] = mock_get_current_admin

        with (
            patch("luthien_control.main.initialize_app_dependencies") as mock_init_deps,
            patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin") as mock_ensure_admin,
            patch("luthien_control.admin.router.get_policy_by_name") as mock_get_policy,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            # Mock app initialization
            mock_container = MagicMock()
            mock_db_session = AsyncMock()
            mock_async_cm = AsyncMock()
            mock_async_cm.__aenter__.return_value = mock_db_session
            mock_async_cm.__aexit__.return_value = None
            mock_factory = MagicMock(return_value=mock_async_cm)
            mock_container.db_session_factory = mock_factory
            mock_http_client = AsyncMock()
            mock_http_client.aclose = AsyncMock()
            mock_container.http_client = mock_http_client
            mock_init_deps.return_value = mock_container
            mock_ensure_admin.return_value = None

            mock_get_policy.return_value = sample_policy
            mock_csrf.return_value = "csrf-token"

            try:
                with TestClient(app) as client:
                    response = client.get("/admin/policies/test_policy/edit")

                    assert response.status_code == 200
                    assert b"test_policy" in response.content
                    assert b"backend_url" in response.content
            finally:
                if get_current_admin in app.dependency_overrides:
                    del app.dependency_overrides[get_current_admin]

    def test_edit_policy_page_not_found(self, sample_admin_user):
        """Test edit policy page for non-existent policy."""
        from fastapi.testclient import TestClient
        from luthien_control.admin.dependencies import get_current_admin
        from luthien_control.main import app

        # Override dependencies
        def mock_get_current_admin():
            return sample_admin_user

        app.dependency_overrides[get_current_admin] = mock_get_current_admin

        with (
            patch("luthien_control.main.initialize_app_dependencies") as mock_init_deps,
            patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin") as mock_ensure_admin,
            patch("luthien_control.admin.router.get_policy_by_name") as mock_get_policy,
        ):
            # Mock app initialization
            mock_container = MagicMock()
            mock_db_session = AsyncMock()
            mock_async_cm = AsyncMock()
            mock_async_cm.__aenter__.return_value = mock_db_session
            mock_async_cm.__aexit__.return_value = None
            mock_factory = MagicMock(return_value=mock_async_cm)
            mock_container.db_session_factory = mock_factory
            mock_http_client = AsyncMock()
            mock_http_client.aclose = AsyncMock()
            mock_container.http_client = mock_http_client
            mock_init_deps.return_value = mock_container
            mock_ensure_admin.return_value = None

            mock_get_policy.return_value = None

            try:
                with TestClient(app) as client:
                    response = client.get("/admin/policies/nonexistent/edit")

                    assert response.status_code == 404
            finally:
                if get_current_admin in app.dependency_overrides:
                    del app.dependency_overrides[get_current_admin]

    def test_update_policy_success(self, sample_admin_user, sample_policy):
        """Test successful policy update."""
        from fastapi.testclient import TestClient
        from luthien_control.admin.dependencies import get_current_admin
        from luthien_control.main import app

        # Override dependencies
        def mock_get_current_admin():
            return sample_admin_user

        app.dependency_overrides[get_current_admin] = mock_get_current_admin

        with (
            patch("luthien_control.main.initialize_app_dependencies") as mock_init_deps,
            patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin") as mock_ensure_admin,
            patch("luthien_control.admin.router.get_policy_by_name") as mock_get_policy,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            # Mock app initialization
            mock_container = MagicMock()
            mock_db_session = AsyncMock()
            mock_async_cm = AsyncMock()
            mock_async_cm.__aenter__.return_value = mock_db_session
            mock_async_cm.__aexit__.return_value = None
            mock_factory = MagicMock(return_value=mock_async_cm)
            mock_container.db_session_factory = mock_factory
            mock_http_client = AsyncMock()
            mock_http_client.aclose = AsyncMock()
            mock_container.http_client = mock_http_client
            mock_init_deps.return_value = mock_container
            mock_ensure_admin.return_value = None

            mock_get_policy.return_value = sample_policy
            mock_csrf.return_value = "csrf-token"

            try:
                with TestClient(app) as client:
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
                        follow_redirects=False,
                    )

                    assert response.status_code == 303
                    assert response.headers["location"] == "/admin/policies"
            finally:
                if get_current_admin in app.dependency_overrides:
                    del app.dependency_overrides[get_current_admin]

    def test_update_policy_invalid_json(self, sample_admin_user, sample_policy):
        """Test policy update with invalid JSON."""
        from fastapi.testclient import TestClient
        from luthien_control.admin.dependencies import get_current_admin
        from luthien_control.main import app

        # Override dependencies
        def mock_get_current_admin():
            return sample_admin_user

        app.dependency_overrides[get_current_admin] = mock_get_current_admin

        with (
            patch("luthien_control.main.initialize_app_dependencies") as mock_init_deps,
            patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin") as mock_ensure_admin,
            patch("luthien_control.admin.router.get_policy_by_name") as mock_get_policy,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            # Mock app initialization
            mock_container = MagicMock()
            mock_db_session = AsyncMock()
            mock_async_cm = AsyncMock()
            mock_async_cm.__aenter__.return_value = mock_db_session
            mock_async_cm.__aexit__.return_value = None
            mock_factory = MagicMock(return_value=mock_async_cm)
            mock_container.db_session_factory = mock_factory
            mock_http_client = AsyncMock()
            mock_http_client.aclose = AsyncMock()
            mock_container.http_client = mock_http_client
            mock_init_deps.return_value = mock_container
            mock_ensure_admin.return_value = None

            mock_get_policy.return_value = sample_policy
            mock_csrf.return_value = "csrf-token"

            try:
                with TestClient(app) as client:
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
            finally:
                if get_current_admin in app.dependency_overrides:
                    del app.dependency_overrides[get_current_admin]

    def test_new_policy_page(self, sample_admin_user):
        """Test new policy creation page."""
        from fastapi.testclient import TestClient
        from luthien_control.admin.dependencies import get_current_admin
        from luthien_control.main import app

        # Override dependencies
        def mock_get_current_admin():
            return sample_admin_user

        app.dependency_overrides[get_current_admin] = mock_get_current_admin

        with (
            patch("luthien_control.main.initialize_app_dependencies") as mock_init_deps,
            patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin") as mock_ensure_admin,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            # Mock app initialization
            mock_container = MagicMock()
            mock_db_session = AsyncMock()
            mock_async_cm = AsyncMock()
            mock_async_cm.__aenter__.return_value = mock_db_session
            mock_async_cm.__aexit__.return_value = None
            mock_factory = MagicMock(return_value=mock_async_cm)
            mock_container.db_session_factory = mock_factory
            mock_http_client = AsyncMock()
            mock_http_client.aclose = AsyncMock()
            mock_container.http_client = mock_http_client
            mock_init_deps.return_value = mock_container
            mock_ensure_admin.return_value = None

            mock_csrf.return_value = "csrf-token"

            try:
                with TestClient(app) as client:
                    response = client.get("/admin/policies/new")

                    assert response.status_code == 200
                    assert b"Create New Policy" in response.content
            finally:
                if get_current_admin in app.dependency_overrides:
                    del app.dependency_overrides[get_current_admin]

    def test_create_policy_success(self, sample_admin_user):
        """Test successful policy creation."""
        from fastapi.testclient import TestClient
        from luthien_control.admin.dependencies import get_current_admin
        from luthien_control.main import app

        # Override dependencies
        def mock_get_current_admin():
            return sample_admin_user

        app.dependency_overrides[get_current_admin] = mock_get_current_admin

        with (
            patch("luthien_control.main.initialize_app_dependencies") as mock_init_deps,
            patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin") as mock_ensure_admin,
            patch("luthien_control.admin.router.save_policy_to_db") as mock_save,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            # Mock app initialization
            mock_container = MagicMock()
            mock_db_session = AsyncMock()
            mock_async_cm = AsyncMock()
            mock_async_cm.__aenter__.return_value = mock_db_session
            mock_async_cm.__aexit__.return_value = None
            mock_factory = MagicMock(return_value=mock_async_cm)
            mock_container.db_session_factory = mock_factory
            mock_http_client = AsyncMock()
            mock_http_client.aclose = AsyncMock()
            mock_container.http_client = mock_http_client
            mock_init_deps.return_value = mock_container
            mock_ensure_admin.return_value = None

            mock_save.return_value = AsyncMock()
            mock_csrf.return_value = "csrf-token"

            try:
                with TestClient(app) as client:
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
                        follow_redirects=False,
                    )

                    assert response.status_code == 303
                    assert response.headers["location"] == "/admin/policies"
            finally:
                if get_current_admin in app.dependency_overrides:
                    del app.dependency_overrides[get_current_admin]

    def test_create_policy_invalid_json(self, sample_admin_user):
        """Test policy creation with invalid JSON."""
        from fastapi.testclient import TestClient
        from luthien_control.admin.dependencies import get_current_admin
        from luthien_control.main import app

        # Override dependencies
        def mock_get_current_admin():
            return sample_admin_user

        app.dependency_overrides[get_current_admin] = mock_get_current_admin

        with (
            patch("luthien_control.main.initialize_app_dependencies") as mock_init_deps,
            patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin") as mock_ensure_admin,
            patch("luthien_control.admin.router.csrf_protection.generate_token") as mock_csrf,
        ):
            # Mock app initialization
            mock_container = MagicMock()
            mock_db_session = AsyncMock()
            mock_async_cm = AsyncMock()
            mock_async_cm.__aenter__.return_value = mock_db_session
            mock_async_cm.__aexit__.return_value = None
            mock_factory = MagicMock(return_value=mock_async_cm)
            mock_container.db_session_factory = mock_factory
            mock_http_client = AsyncMock()
            mock_http_client.aclose = AsyncMock()
            mock_container.http_client = mock_http_client
            mock_init_deps.return_value = mock_container
            mock_ensure_admin.return_value = None

            mock_csrf.return_value = "csrf-token"

            try:
                with TestClient(app) as client:
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
            finally:
                if get_current_admin in app.dependency_overrides:
                    del app.dependency_overrides[get_current_admin]

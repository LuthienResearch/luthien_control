"""Tests for admin router - Clean version without nested contexts or conditionals."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
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
def mock_dependency_container():
    """Mock dependency container with all required components."""
    container = MagicMock()
    
    # Mock db session
    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # Sync method
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    
    # Mock async context manager for db_session_factory
    mock_async_cm = AsyncMock()
    mock_async_cm.__aenter__.return_value = mock_session
    mock_async_cm.__aexit__.return_value = None
    
    container.db_session_factory = MagicMock(return_value=mock_async_cm)
    
    # Mock http client
    container.http_client = AsyncMock()
    container.http_client.aclose = AsyncMock()
    
    return container


@pytest.fixture
def admin_test_client(mock_dependency_container):
    """Test client with mocked dependencies."""
    from luthien_control.main import app
    
    with patch("luthien_control.main.initialize_app_dependencies", return_value=mock_dependency_container):
        with patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin", AsyncMock()):
            with TestClient(app) as client:
                yield client


@pytest.fixture
def authenticated_admin_client(admin_test_client, sample_admin_user):
    """Test client with authenticated admin user."""
    from luthien_control.admin.dependencies import get_current_admin
    from luthien_control.main import app
    
    app.dependency_overrides[get_current_admin] = lambda: sample_admin_user
    yield admin_test_client
    del app.dependency_overrides[get_current_admin]


@pytest.fixture
def mock_csrf():
    """Mock CSRF protection."""
    with patch("luthien_control.admin.router.csrf_protection.generate_token", AsyncMock(return_value="csrf-token")):
        yield


class TestLoginEndpoints:
    """Test login-related endpoints."""
    
    def test_login_page_renders(self, admin_test_client, mock_csrf):
        """Test login page renders with CSRF token."""
        response = admin_test_client.get("/admin/login")
        
        assert response.status_code == 200
        assert "csrf_token" in response.cookies
        assert response.cookies["csrf_token"] == "csrf-token"
    
    def test_login_success(self, admin_test_client, mock_csrf):
        """Test successful login redirects to policies."""
        mock_user = MagicMock(id=1, username="admin")
        mock_session = MagicMock(session_token="session-token")
        
        with patch("luthien_control.admin.router.admin_auth_service.authenticate", AsyncMock(return_value=mock_user)):
            with patch("luthien_control.admin.router.admin_auth_service.create_session", AsyncMock(return_value=mock_session)):
                # Get CSRF token
                login_page = admin_test_client.get("/admin/login")
                csrf_token = login_page.cookies["csrf_token"]
                
                # Submit login
                response = admin_test_client.post(
                    "/admin/login",
                    data={"username": "admin", "password": "password", "csrf_token": csrf_token},
                    cookies={"csrf_token": csrf_token},
                    follow_redirects=False,
                )
                
                assert response.status_code == 303
                assert response.headers["location"] == "/admin/policies"
                assert "session_token" in response.cookies
    
    def test_login_invalid_csrf(self, admin_test_client):
        """Test login rejects invalid CSRF token."""
        response = admin_test_client.post(
            "/admin/login",
            data={"username": "admin", "password": "password", "csrf_token": "wrong"},
            cookies={"csrf_token": "different"},
        )
        
        assert response.status_code == 400
    
    def test_login_invalid_credentials(self, admin_test_client, mock_csrf):
        """Test login shows error for invalid credentials."""
        with patch("luthien_control.admin.router.admin_auth_service.authenticate", AsyncMock(return_value=None)):
            # Get CSRF token
            login_page = admin_test_client.get("/admin/login")
            csrf_token = login_page.cookies["csrf_token"]
            
            # Submit bad login
            response = admin_test_client.post(
                "/admin/login",
                data={"username": "admin", "password": "wrong", "csrf_token": csrf_token},
                cookies={"csrf_token": csrf_token},
            )
            
            assert response.status_code == 401
            assert b"Invalid username or password" in response.content
    
    def test_logout_redirects(self, admin_test_client):
        """Test logout redirects to login page."""
        with patch("luthien_control.admin.router.admin_auth_service.logout", AsyncMock()):
            response = admin_test_client.get(
                "/admin/logout",
                cookies={"session_token": "test-token"},
                follow_redirects=False,
            )
            
            assert response.status_code == 303
            assert response.headers["location"] == "/admin/login"


class TestAdminPages:
    """Test admin dashboard pages."""
    
    def test_admin_home(self, authenticated_admin_client, sample_policy):
        """Test admin dashboard displays policies."""
        with patch("luthien_control.admin.router.list_policies", AsyncMock(return_value=[sample_policy])):
            response = authenticated_admin_client.get("/admin/")
            
            assert response.status_code == 200
            assert b"Admin Dashboard" in response.content
    
    def test_policies_list(self, authenticated_admin_client, sample_policy):
        """Test policies list page."""
        with patch("luthien_control.admin.router.list_policies", AsyncMock(return_value=[sample_policy])):
            response = authenticated_admin_client.get("/admin/policies")
            
            assert response.status_code == 200
            assert b"test_policy" in response.content


class TestPolicyEdit:
    """Test policy editing functionality."""
    
    def test_edit_page_displays_policy(self, authenticated_admin_client, sample_policy, mock_csrf):
        """Test edit page shows policy details."""
        with patch("luthien_control.admin.router.get_policy_by_name", AsyncMock(return_value=sample_policy)):
            response = authenticated_admin_client.get("/admin/policies/test_policy/edit")
            
            assert response.status_code == 200
            assert b"test_policy" in response.content
            assert b"backend_url" in response.content
    
    def test_edit_page_404_for_missing_policy(self, authenticated_admin_client):
        """Test edit page returns 404 for non-existent policy."""
        with patch("luthien_control.admin.router.get_policy_by_name", AsyncMock(return_value=None)):
            response = authenticated_admin_client.get("/admin/policies/nonexistent/edit")
            
            assert response.status_code == 404
    
    def test_update_policy_success(self, authenticated_admin_client, sample_policy, mock_csrf):
        """Test successful policy update."""
        with patch("luthien_control.admin.router.get_policy_by_name", AsyncMock(return_value=sample_policy)):
            # Get CSRF from edit page
            edit_page = authenticated_admin_client.get("/admin/policies/test_policy/edit")
            csrf_token = edit_page.cookies["csrf_token"]
            
            # Submit update
            response = authenticated_admin_client.post(
                "/admin/policies/test_policy/edit",
                data={
                    "config": json.dumps({"backend_url": "https://updated.com"}),
                    "description": "Updated description",
                    "is_active": "on",
                    "csrf_token": csrf_token,
                },
                cookies={"csrf_token": csrf_token},
                follow_redirects=False,
            )
            
            assert response.status_code == 303
            assert response.headers["location"] == "/admin/policies"
    
    def test_update_policy_invalid_csrf(self, authenticated_admin_client):
        """Test update rejects invalid CSRF."""
        response = authenticated_admin_client.post(
            "/admin/policies/test_policy/edit",
            data={"config": "{}", "csrf_token": "wrong"},
            cookies={"csrf_token": "different"},
        )
        
        assert response.status_code == 400
        assert b"Invalid request" in response.content
    
    def test_update_policy_not_found(self, authenticated_admin_client):
        """Test update returns 404 for missing policy."""
        with patch("luthien_control.admin.router.get_policy_by_name", AsyncMock(return_value=None)):
            response = authenticated_admin_client.post(
                "/admin/policies/nonexistent/edit",
                data={"config": "{}", "csrf_token": "csrf-token"},
                cookies={"csrf_token": "csrf-token"},
            )
            
            assert response.status_code == 404
            assert b"Policy not found" in response.content
    
    def test_update_policy_invalid_json(self, authenticated_admin_client, sample_policy, mock_csrf):
        """Test update shows error for invalid JSON."""
        with patch("luthien_control.admin.router.get_policy_by_name", AsyncMock(return_value=sample_policy)):
            # Get CSRF from edit page
            edit_page = authenticated_admin_client.get("/admin/policies/test_policy/edit")
            csrf_token = edit_page.cookies["csrf_token"]
            
            # Submit invalid JSON
            response = authenticated_admin_client.post(
                "/admin/policies/test_policy/edit",
                data={"config": "{invalid json}", "csrf_token": csrf_token},
                cookies={"csrf_token": csrf_token},
            )
            
            assert response.status_code == 400
            assert b"Invalid JSON" in response.content
    
    def test_update_policy_database_error(self, authenticated_admin_client, sample_policy, mock_csrf, mock_dependency_container):
        """Test update shows error on database failure."""
        # Make commit fail
        mock_dependency_container.db_session_factory.return_value.__aenter__.return_value.commit = AsyncMock(
            side_effect=Exception("Database error")
        )
        
        with patch("luthien_control.admin.router.get_policy_by_name", AsyncMock(return_value=sample_policy)):
            # Get CSRF from edit page
            edit_page = authenticated_admin_client.get("/admin/policies/test_policy/edit")
            csrf_token = edit_page.cookies["csrf_token"]
            
            # Submit update
            response = authenticated_admin_client.post(
                "/admin/policies/test_policy/edit",
                data={"config": "{}", "description": "Test", "csrf_token": csrf_token},
                cookies={"csrf_token": csrf_token},
            )
            
            assert response.status_code == 400
            assert b"Update failed: Database error" in response.content


class TestPolicyCreate:
    """Test policy creation functionality."""
    
    def test_new_policy_page(self, authenticated_admin_client, mock_csrf):
        """Test new policy page renders."""
        response = authenticated_admin_client.get("/admin/policies/new")
        
        assert response.status_code == 200
        assert b"Create New Policy" in response.content
    
    def test_create_policy_success(self, authenticated_admin_client, mock_csrf):
        """Test successful policy creation."""
        with patch("luthien_control.admin.router.save_policy_to_db", AsyncMock()):
            # Get CSRF from new page
            new_page = authenticated_admin_client.get("/admin/policies/new")
            csrf_token = new_page.cookies["csrf_token"]
            
            # Submit new policy
            response = authenticated_admin_client.post(
                "/admin/policies/new",
                data={
                    "name": "new_policy",
                    "type": "backend_call",
                    "config": json.dumps({"backend_url": "https://api.new.com"}),
                    "description": "New policy",
                    "is_active": "on",
                    "csrf_token": csrf_token,
                },
                cookies={"csrf_token": csrf_token},
                follow_redirects=False,
            )
            
            assert response.status_code == 303
            assert response.headers["location"] == "/admin/policies"
    
    def test_create_policy_invalid_csrf(self, authenticated_admin_client):
        """Test create rejects invalid CSRF."""
        response = authenticated_admin_client.post(
            "/admin/policies/new",
            data={
                "name": "new_policy",
                "type": "backend_call",
                "config": "{}",
                "csrf_token": "wrong",
            },
            cookies={"csrf_token": "different"},
        )
        
        assert response.status_code == 400
        assert b"Invalid request" in response.content
    
    def test_create_policy_invalid_json(self, authenticated_admin_client, mock_csrf):
        """Test create shows error for invalid JSON."""
        # Get CSRF from new page
        new_page = authenticated_admin_client.get("/admin/policies/new")
        csrf_token = new_page.cookies["csrf_token"]
        
        # Submit invalid JSON
        response = authenticated_admin_client.post(
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
    
    def test_create_policy_database_error(self, authenticated_admin_client, mock_csrf):
        """Test create shows error on database failure."""
        with patch("luthien_control.admin.router.save_policy_to_db", side_effect=Exception("Database error")):
            # Get CSRF from new page
            new_page = authenticated_admin_client.get("/admin/policies/new")
            csrf_token = new_page.cookies["csrf_token"]
            
            # Submit new policy
            response = authenticated_admin_client.post(
                "/admin/policies/new",
                data={
                    "name": "new_policy",
                    "type": "backend_call",
                    "config": "{}",
                    "description": "Test",
                    "csrf_token": csrf_token,
                },
                cookies={"csrf_token": csrf_token},
            )
            
            assert response.status_code == 400
            assert b"Creation failed: Database error" in response.content
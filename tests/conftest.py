import pytest
import os
from luthien_control.config.settings import Settings, get_settings
from luthien_control.proxy.server import app as fastapi_app # Import the FastAPI app

@pytest.fixture(scope="session")
def app():
    """Fixture to provide the FastAPI app instance."""
    return fastapi_app

@pytest.fixture(scope="session")
def unit_settings() -> Settings:
    """Fixture to load settings specifically for unit tests (.env.test)."""
    # Ensure APP_ENV is set correctly for unit tests
    original_env = os.environ.get("APP_ENV")
    os.environ["APP_ENV"] = "test"
    
    # Clear the cache for get_settings before calling it
    get_settings.cache_clear()
    settings = get_settings()
    
    # Restore original APP_ENV if it existed
    if original_env is None:
        del os.environ["APP_ENV"]
    else:
        os.environ["APP_ENV"] = original_env
        
    # Clear cache again after restoring env (optional but clean)
    get_settings.cache_clear()
    
    assert settings.BACKEND_URL.host == "mock-backend.test", "Unit tests should use the mock backend URL from .env.test"
    return settings

@pytest.fixture(scope="session")
def integration_settings() -> Settings:
    """Fixture to load settings for integration tests (.env).
    Skips tests if OPENAI_API_KEY is not found.
    """
    # Ensure APP_ENV is NOT test for integration tests
    original_env = os.environ.get("APP_ENV")
    if original_env == "test":
        del os.environ["APP_ENV"]
        
    # Clear cache and get settings (should load from .env)
    get_settings.cache_clear()
    settings = get_settings()
    
    # Restore original APP_ENV if needed
    if original_env is not None:
        os.environ["APP_ENV"] = original_env
        
    # Clear cache again
    get_settings.cache_clear()
    
    if not settings.OPENAI_API_KEY:
        pytest.skip("Skipping integration test: OPENAI_API_KEY not found in .env")
    
    assert settings.BACKEND_URL.host != "127.0.0.1", "Integration tests should use the real backend URL from .env"
    return settings

# Fixture to override settings dependency in FastAPI app for testing
@pytest.fixture(autouse=True) # Apply this automatically to relevant tests
def override_settings_dependency(app, request):
    """Overrides the get_settings dependency based on test markers."""
    if request.node.get_closest_marker("integration"):
        # Use integration settings for integration tests
        app.dependency_overrides[get_settings] = lambda: request.getfixturevalue("integration_settings")
        yield
        del app.dependency_overrides[get_settings]
    elif request.node.get_closest_marker("unit") or not request.node.get_closest_marker(): # Default to unit if no marker
        # Use unit settings for unit tests or tests without specific markers
        app.dependency_overrides[get_settings] = lambda: request.getfixturevalue("unit_settings")
        yield
        del app.dependency_overrides[get_settings]
    else:
         # If neither marker, default to unit settings or raise error? For now, default unit.
        app.dependency_overrides[get_settings] = lambda: request.getfixturevalue("unit_settings")
        yield
        del app.dependency_overrides[get_settings]

# Add a unit marker definition implicitly if needed
# Or rely on the absence of 'integration' marker 
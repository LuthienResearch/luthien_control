import pytest
from luthien_control.settings import Settings


# Fixture to provide a Settings instance for each test
@pytest.fixture
def settings():
    return Settings()


# --- Parameterized Tests for Getters ---


@pytest.mark.parametrize(
    "env_var, method_name, test_value, expected_value",
    [
        # Env Var Name, Settings Method Name, Value to Set, Expected Return
        ("BACKEND_URL", "get_backend_url", "https://example.com/api", "https://example.com/api"),
        ("OPENAI_API_KEY", "get_openai_api_key", "sk-12345", "sk-12345"),
        ("DB_USER", "get_postgres_user", "pg_user", "pg_user"),
        ("DB_PASSWORD", "get_postgres_password", "pg_pass", "pg_pass"),
        ("DB_NAME", "get_postgres_db", "pg_db", "pg_db"),
        ("DB_HOST", "get_postgres_host", "pg_host", "pg_host"),
        ("DB_PORT", "get_postgres_port", "5433", 5433),  # Input str, output int
    ],
)
def test_getter_set(settings, monkeypatch, env_var, method_name, test_value, expected_value):
    """Test simple getters when the corresponding environment variable is set."""
    monkeypatch.setenv(env_var, test_value)
    getter_method = getattr(settings, method_name)
    assert getter_method() == expected_value


@pytest.mark.parametrize(
    "env_var, method_name, expected_value",
    [
        # Env Var Name, Settings Method Name, Expected Return when Not Set
        ("BACKEND_URL", "get_backend_url", None),
        ("OPENAI_API_KEY", "get_openai_api_key", None),
        ("DB_USER", "get_postgres_user", None),
        ("DB_PASSWORD", "get_postgres_password", None),
        ("DB_NAME", "get_postgres_db", None),
        ("DB_HOST", "get_postgres_host", None),
        ("DB_PORT", "get_postgres_port", None),
    ],
)
def test_getter_not_set(settings, monkeypatch, env_var, method_name, expected_value):
    """Test simple getters when the corresponding environment variable is NOT set."""
    monkeypatch.delenv(env_var, raising=False)
    getter_method = getattr(settings, method_name)
    assert getter_method() == expected_value


# --- Specific Error Condition Tests (Keep Separate) ---


def test_get_backend_url_invalid_format(settings, monkeypatch):
    """Test get_backend_url when BACKEND_URL has an invalid format."""
    monkeypatch.setenv("BACKEND_URL", "not-a-valid-url")
    with pytest.raises(ValueError, match="Invalid BACKEND_URL format"):
        settings.get_backend_url()


def test_get_backend_url_missing_scheme(settings, monkeypatch):
    """Test get_backend_url when BACKEND_URL is missing the scheme."""
    monkeypatch.setenv("BACKEND_URL", "example.com/api")
    with pytest.raises(ValueError, match="Invalid BACKEND_URL format"):
        settings.get_backend_url()


def test_get_postgres_port_invalid(settings, monkeypatch):
    """Test get_postgres_port when DB_PORT is not an integer."""
    monkeypatch.setenv("DB_PORT", "not-an-int")
    with pytest.raises(ValueError, match="DB_PORT environment variable must be an integer"):
        settings.get_postgres_port()


# --- Tests for DSN Properties ---


@pytest.fixture
def set_postgres_env(monkeypatch):
    """Fixture to set required PostgreSQL environment variables."""
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_pass")
    monkeypatch.setenv("DB_HOST", "test_host")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "test_db")


# --- Test admin_dsn ---


def test_admin_dsn_happy_path(settings, set_postgres_env):
    """Test admin_dsn property when all required env vars are set."""
    expected_dsn = "postgresql://test_user:test_pass@test_host:5432/postgres"
    assert settings.admin_dsn == expected_dsn


@pytest.mark.parametrize("missing_var", ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"])
def test_admin_dsn_missing_var(settings, set_postgres_env, monkeypatch, missing_var):
    """Test admin_dsn property raises ValueError when a required var is missing."""
    monkeypatch.delenv(missing_var)
    with pytest.raises(ValueError, match="Missing required database settings .* for admin_dsn"):
        _ = settings.admin_dsn  # Access property to trigger the check


# --- Test base_dsn ---


def test_base_dsn_happy_path(settings, set_postgres_env):
    """Test base_dsn property when all required env vars are set."""
    expected_dsn = "postgresql://test_user:test_pass@test_host:5432"
    assert settings.base_dsn == expected_dsn


@pytest.mark.parametrize("missing_var", ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"])
def test_base_dsn_missing_var(settings, set_postgres_env, monkeypatch, missing_var):
    """Test base_dsn property raises ValueError when a required var is missing."""
    monkeypatch.delenv(missing_var)
    with pytest.raises(ValueError, match="Missing required database settings .* for base_dsn"):
        _ = settings.base_dsn  # Access property to trigger the check


# --- Test get_db_dsn ---


def test_get_db_dsn_happy_path_default_db(settings, set_postgres_env):
    """Test get_db_dsn using the default DB_NAME from env."""
    expected_dsn = "postgresql://test_user:test_pass@test_host:5432/test_db"
    assert settings.get_db_dsn() == expected_dsn


def test_get_db_dsn_happy_path_arg_db(settings, set_postgres_env):
    """Test get_db_dsn using the db_name argument."""
    arg_db = "other_db"
    expected_dsn = f"postgresql://test_user:test_pass@test_host:5432/{arg_db}"
    assert settings.get_db_dsn(db_name=arg_db) == expected_dsn


@pytest.mark.parametrize("missing_var", ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"])
def test_get_db_dsn_missing_base_var(settings, set_postgres_env, monkeypatch, missing_var):
    """Test get_db_dsn raises ValueError when a base DSN required var is missing."""
    monkeypatch.delenv(missing_var)
    with pytest.raises(ValueError, match="Missing required database settings .* for base_dsn"):
        settings.get_db_dsn()  # Call method to trigger the check


# --- Test for get_policy_filepath ---


def test_get_policy_filepath_behavior(monkeypatch):
    """Test that get_policy_filepath returns None when POLICY_FILEPATH env var is not set.

    This test uses the real Settings class to verify the actual behavior.
    It would fail if get_policy_filepath returned a default value instead of None.
    This test is completely isolated from .env files.
    """
    # Disable dotenv loading to prevent .env files from affecting the test
    with monkeypatch.context() as m:
        # Mock load_dotenv to do nothing
        m.setattr("luthien_control.settings.load_dotenv", lambda **kwargs: None)

        # Test with POLICY_FILEPATH not set
        m.delenv("POLICY_FILEPATH", raising=False)

        settings = Settings()
        result = settings.get_policy_filepath()

        # This should be None when env var is not set
        assert result is None, f"Expected None when POLICY_FILEPATH not set, got: {result!r}"

        # Test that the boolean evaluation is False (important for the if condition)
        assert not result, f"Expected falsy value when POLICY_FILEPATH not set, got: {result!r}"

        # Test with POLICY_FILEPATH set
        m.setenv("POLICY_FILEPATH", "test_path.json")

        settings = Settings()  # Create new instance to pick up env change
        result = settings.get_policy_filepath()

        assert result == "test_path.json", f"Expected 'test_path.json' when POLICY_FILEPATH is set, got: {result!r}"
        assert result, f"Expected truthy value when POLICY_FILEPATH is set, got: {result!r}"

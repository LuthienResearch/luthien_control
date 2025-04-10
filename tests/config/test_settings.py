import pytest
from luthien_control.config.settings import Settings


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
        ("CONTROL_POLICIES", "get_control_policies_list", "p1,p2", "p1,p2"),
        ("POSTGRES_USER", "get_postgres_user", "pg_user", "pg_user"),
        ("POSTGRES_PASSWORD", "get_postgres_password", "pg_pass", "pg_pass"),
        ("POSTGRES_DB", "get_postgres_db", "pg_db", "pg_db"),
        ("POSTGRES_HOST", "get_postgres_host", "pg_host", "pg_host"),
        ("POSTGRES_PORT", "get_postgres_port", "5433", 5433),  # Input str, output int
        ("LOG_DB_USER", "get_log_db_user", "log_user", "log_user"),
        ("LOG_DB_PASSWORD", "get_log_db_password", "log_pass", "log_pass"),
        ("LOG_DB_NAME", "get_log_db_name", "log_db", "log_db"),
        ("LOG_DB_HOST", "get_log_db_host", "log_host", "log_host"),
        ("LOG_DB_PORT", "get_log_db_port", "5434", 5434),  # Input str, output int
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
        ("CONTROL_POLICIES", "get_control_policies_list", None),
        ("POSTGRES_USER", "get_postgres_user", None),
        ("POSTGRES_PASSWORD", "get_postgres_password", None),
        ("POSTGRES_DB", "get_postgres_db", None),
        ("POSTGRES_HOST", "get_postgres_host", None),
        ("POSTGRES_PORT", "get_postgres_port", None),  # Changed expectation from 5432 to None
        ("LOG_DB_USER", "get_log_db_user", None),
        ("LOG_DB_PASSWORD", "get_log_db_password", None),
        ("LOG_DB_NAME", "get_log_db_name", None),
        ("LOG_DB_HOST", "get_log_db_host", None),
        ("LOG_DB_PORT", "get_log_db_port", None),  # Changed expectation from 5432 to None
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
    """Test get_postgres_port when POSTGRES_PORT is not an integer."""
    monkeypatch.setenv("POSTGRES_PORT", "not-an-int")
    with pytest.raises(ValueError, match="POSTGRES_PORT environment variable must be an integer"):
        settings.get_postgres_port()


def test_get_log_db_port_invalid(settings, monkeypatch):
    """Test get_log_db_port when LOG_DB_PORT is not an integer."""
    monkeypatch.setenv("LOG_DB_PORT", "not-an-int-either")
    with pytest.raises(ValueError, match="LOG_DB_PORT environment variable must be an integer"):
        settings.get_log_db_port()


# --- Tests for DSN Properties ---


@pytest.fixture
def set_postgres_env(monkeypatch):
    """Fixture to set required PostgreSQL environment variables."""
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
    monkeypatch.setenv("POSTGRES_HOST", "test_host")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "test_db")


# --- Test admin_dsn ---


def test_admin_dsn_happy_path(settings, set_postgres_env):
    """Test admin_dsn property when all required env vars are set."""
    expected_dsn = "postgresql://test_user:test_pass@test_host:5432/postgres"
    assert settings.admin_dsn == expected_dsn


@pytest.mark.parametrize("missing_var", ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"])
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


@pytest.mark.parametrize("missing_var", ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"])
def test_base_dsn_missing_var(settings, set_postgres_env, monkeypatch, missing_var):
    """Test base_dsn property raises ValueError when a required var is missing."""
    monkeypatch.delenv(missing_var)
    with pytest.raises(ValueError, match="Missing required database settings .* for base_dsn"):
        _ = settings.base_dsn  # Access property to trigger the check


# --- Test get_db_dsn ---


def test_get_db_dsn_happy_path_default_db(settings, set_postgres_env):
    """Test get_db_dsn using the default POSTGRES_DB from env."""
    expected_dsn = "postgresql://test_user:test_pass@test_host:5432/test_db"
    assert settings.get_db_dsn() == expected_dsn


def test_get_db_dsn_happy_path_arg_db(settings, set_postgres_env):
    """Test get_db_dsn using the db_name argument."""
    arg_db = "other_db"
    expected_dsn = f"postgresql://test_user:test_pass@test_host:5432/{arg_db}"
    assert settings.get_db_dsn(db_name=arg_db) == expected_dsn


@pytest.mark.parametrize("missing_var", ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"])
def test_get_db_dsn_missing_base_var(settings, set_postgres_env, monkeypatch, missing_var):
    """Test get_db_dsn raises ValueError when a base DSN required var is missing."""
    monkeypatch.delenv(missing_var)
    with pytest.raises(ValueError, match="Missing required database settings .* for base_dsn"):
        settings.get_db_dsn()  # Call method to trigger the check


def test_get_db_dsn_missing_target_db(settings, set_postgres_env, monkeypatch):
    """Test get_db_dsn raises ValueError when no target DB name is available."""
    monkeypatch.delenv("POSTGRES_DB")
    with pytest.raises(ValueError, match="Missing target database name"):
        settings.get_db_dsn()  # No arg, no env var

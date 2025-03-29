"""Global pytest configuration."""


def pytest_addoption(parser):
    """Add command-line options."""
    parser.addoption("--env", action="store", default="local", help="test environment: local, deployed, or both")

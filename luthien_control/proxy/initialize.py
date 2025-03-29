"""
Server initialization for Luthien Control Framework.
"""

from ..policies.examples.noop_policy import NoopPolicy
from .server import app, policy_manager

# We'll comment out the token counter since we want a no-op by default
# from ..policies.examples.token_counter import TokenCounterPolicy


def initialize_server():
    """Initialize the server with default configurations and policies."""
    # Register the no-op policy as the default
    noop_policy = NoopPolicy()
    policy_manager.register_policy(noop_policy)

    # Other policies can be registered here as needed
    # token_counter = TokenCounterPolicy()
    # policy_manager.register_policy(token_counter)

    return app


# This can be called from an entry point script
# app = initialize_server() # Removed redundant assignment causing F811

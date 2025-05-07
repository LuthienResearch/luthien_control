import logging

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

logger = logging.getLogger(__name__)


def create_custom_openapi(app: FastAPI):
    """
    Generate a custom OpenAPI schema for the FastAPI application.

    This function retrieves the default schema and modifies it, specifically
    to set `allowReserved=True` for the `full_path` path parameter used
    in proxy routes. This is necessary for correctly handling URLs containing
    reserved characters within that path segment.

    Args:
        app: The FastAPI application instance.

    Returns:
        The modified OpenAPI schema dictionary.
    """
    # Check if schema already exists to avoid redundant generation
    if app.openapi_schema:
        return app.openapi_schema

    logger.debug("Generating custom OpenAPI schema.")
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Modify the schema for the path parameter
    paths = openapi_schema.get("paths", {})
    logger.debug(f"Found {len(paths)} paths in schema. Searching for '{{full_path}}'.")
    for path_key, path_item in paths.items():
        if "{full_path}" in path_key:
            logger.debug(f"Processing path: {path_key}")
            # path_item contains methods like 'get', 'post', etc.
            for method, method_item in path_item.items():
                # Ensure 'parameters' exists and is a list
                parameters = method_item.get("parameters", [])
                if not isinstance(parameters, list):
                    logger.warning(f"Unexpected 'parameters' format in {path_key} -> {method}. Skipping.")
                    continue

                found_param = False
                for param in parameters:
                    # Ensure param is a dictionary and has 'name' and 'in' keys
                    if not isinstance(param, dict) or "name" not in param or "in" not in param:
                        logger.warning(
                            f"Malformed parameter definition in {path_key} -> {method}. Skipping param: {param}"
                        )
                        continue

                    if param["name"] == "full_path" and param["in"] == "path":
                        param["allowReserved"] = True
                        found_param = True
                        logger.info(f"Set allowReserved=true for 'full_path' parameter in {path_key} -> {method}")
                        # Assuming only one 'full_path' param per method
                        break  # No need to check other params for this method
                if not found_param:
                    logger.debug(f"No 'full_path' path parameter found in {path_key} -> {method}")

    # Cache the generated schema in the app instance
    app.openapi_schema = openapi_schema
    logger.debug("Custom OpenAPI schema generation complete.")
    return app.openapi_schema

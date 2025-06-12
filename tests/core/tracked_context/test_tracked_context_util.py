
import pytest
from luthien_control.core.tracked_context import TrackedContext
from luthien_control.core.tracked_context.util import get_tx_value


class TestGetTxValueTrackedContext:
    """Tests for `luthien_control.core.tracked_context.util.get_tx_value`."""

    # --- Happy-path retrievals -------------------------------------------------

    def test_retrieve_simple_request_attribute(self):
        """A basic attribute (request.method) should be returned correctly."""
        ctx = TrackedContext()
        ctx.update_request(method="POST", url="https://example.com")

        assert get_tx_value(ctx, "request.method") == "POST"

    def test_retrieve_nested_json_content(self):
        """Nested JSON keys inside request.content should be accessible once decoded."""
        json_bytes = b'{"alpha": {"beta": "value"}}'
        ctx = TrackedContext()
        ctx.update_request(
            method="PUT",
            url="https://example.com/api",
            headers={"content-type": "application/json"},
            content=json_bytes,
        )

        assert get_tx_value(ctx, "request.content.alpha.beta") == "value"

    def test_retrieve_response_status_code(self):
        """Status code should be obtained when accessing response.status_code."""
        ctx = TrackedContext()
        ctx.update_response(status_code=418)

        assert get_tx_value(ctx, "response.status_code") == 418

    # --- Error scenarios ------------------------------------------------------

    def test_path_too_short_raises(self):
        ctx = TrackedContext()
        with pytest.raises(ValueError):
            get_tx_value(ctx, "request")  # Only one segment

    def test_request_none_raises(self):
        ctx = TrackedContext()
        # No request set
        with pytest.raises(ValueError, match="Request is None"):
            get_tx_value(ctx, "request.method")

    def test_json_decode_error_raises(self):
        """Accessing a key within non-JSON bytes should raise ValueError due to decode error."""
        ctx = TrackedContext()
        ctx.update_request(method="GET", url="/", content=b"not-json")

        with pytest.raises(ValueError, match="Failed to decode JSON content"):
            get_tx_value(ctx, "request.content.somekey")

    def test_missing_dict_key_raises(self):
        ctx = TrackedContext()
        ctx.set_data("exists", 1)

        with pytest.raises(KeyError):
            get_tx_value(ctx, "data.missing")

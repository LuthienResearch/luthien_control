import pytest
from luthien_control.core.tracked_context import TrackedContext
from luthien_control.core.tracked_context.util import get_tx_value


class TestGetTxValueBytesBranch:
    """Covers the branch where a bytes value is JSON-decoded during traversal."""

    def test_bytes_json_decode_success(self):
        ctx = TrackedContext()
        ctx.set_data("blob", b'{"key": {"inner": "value"}}')
        assert get_tx_value(ctx, "data.blob.key.inner") == "value"

    def test_bytes_json_decode_failure_raises(self):
        ctx = TrackedContext()
        ctx.set_data("blob", b"not-json")
        with pytest.raises(ValueError, match="Failed to decode JSON content"):
            get_tx_value(ctx, "data.blob.key.nested")

import pytest
from luthien_control.core.tracked_context import TrackedContext


class TestTrackedContextAdditionalBranches:
    """Extra branch coverage for TrackedContext.update_request/response."""

    def test_update_request_from_scratch_requires_fields(self):
        ctx = TrackedContext()
        # from_scratch without method+url should raise
        with pytest.raises(ValueError):
            ctx.update_request(from_scratch=True)

    def test_update_url_only(self):
        ctx = TrackedContext()
        ctx.update_request(method="GET", url="https://orig.example")
        updated = ctx.update_request(url="https://changed.example")
        assert str(updated.url) == "https://changed.example"

    def test_update_response_mutation(self):
        ctx = TrackedContext()
        ctx.update_response(status_code=200)
        new_headers = {"X-New": "42"}
        new_content = b"abc"
        resp = ctx.update_response(headers=new_headers, content=new_content)
        assert resp.headers["X-New"] == "42"
        assert resp.content == new_content

    def test_update_response_from_scratch_requires_status(self):
        ctx = TrackedContext()
        with pytest.raises(ValueError):
            ctx.update_response(from_scratch=True)

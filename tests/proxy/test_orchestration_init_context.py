from types import SimpleNamespace

from luthien_control.proxy.orchestration import _initialize_context


def test_initialize_context_query_params():
    """_initialize_context should build full URL including query parameters."""
    request = SimpleNamespace()
    request.headers = {"x-test": "1"}
    request.method = "GET"
    request.path_params = {"full_path": "/chat"}
    request.query_params = {"foo": "bar", "baz": "qux"}
    body = b"hello"

    # _initialize_context expects a real fastapi.Request; we supply a stub.
    ctx = _initialize_context(request, body)  # type: ignore[arg-type]

    assert ctx.request is not None
    url_str = str(ctx.request.url)
    assert url_str.endswith("/chat?foo=bar&baz=qux")
    assert ctx.request.content == body


import json
from typing import Dict, cast

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.exceptions import NoRequestError
from luthien_control.control_policy.model_name_replacement import ModelNameReplacementPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext


class MockRequest:
    def __init__(self, content=None):
        self.content = content
        self.headers = {}


@pytest.fixture
def mock_container():
    return cast(DependencyContainer, object())


@pytest.fixture
def mock_session():
    return cast(AsyncSession, object())


@pytest.fixture
def model_mapping():
    return {
        "fakename": "realname",
        "gemini-2.5-pro-preview-05-06": "gpt-4o",
        "claude-3-opus-20240229": "gpt-4-turbo",
    }


@pytest.mark.asyncio
async def test_model_name_replacement_policy_no_request():
    policy = ModelNameReplacementPolicy(model_mapping={})
    context = TransactionContext()
    
    with pytest.raises(NoRequestError):
        await policy.apply(context, cast(DependencyContainer, None), cast(AsyncSession, None))


@pytest.mark.asyncio
async def test_model_name_replacement_policy_no_content(mock_container, mock_session):
    policy = ModelNameReplacementPolicy(model_mapping={"fakename": "realname"})
    context = TransactionContext(request=cast(httpx.Request, MockRequest(content=None)))
    
    result = await policy.apply(context, mock_container, mock_session)
    assert result == context  # Context should be returned unchanged


@pytest.mark.asyncio
async def test_model_name_replacement_policy_invalid_json(mock_container, mock_session):
    policy = ModelNameReplacementPolicy(model_mapping={"fakename": "realname"})
    context = TransactionContext(request=cast(httpx.Request, MockRequest(content=b"not valid json")))
    
    result = await policy.apply(context, mock_container, mock_session)
    assert result == context  # Context should be returned unchanged
    assert context.request.content == b"not valid json"  # Content should be unchanged


@pytest.mark.asyncio
async def test_model_name_replacement_policy_no_model_field(mock_container, mock_session):
    policy = ModelNameReplacementPolicy(model_mapping={"fakename": "realname"})
    request_content = json.dumps({"messages": [{"role": "user", "content": "Hello"}]}).encode("utf-8")
    context = TransactionContext(request=cast(httpx.Request, MockRequest(content=request_content)))
    
    result = await policy.apply(context, mock_container, mock_session)
    assert result == context  # Context should be returned unchanged
    assert context.request.content == request_content  # Content should be unchanged


@pytest.mark.asyncio
async def test_model_name_replacement_policy_model_not_in_mapping(mock_container, mock_session):
    policy = ModelNameReplacementPolicy(model_mapping={"fakename": "realname"})
    request_content = json.dumps({"model": "other-model", "messages": []}).encode("utf-8")
    context = TransactionContext(request=cast(httpx.Request, MockRequest(content=request_content)))
    
    result = await policy.apply(context, mock_container, mock_session)
    assert result == context  # Context should be returned unchanged
    assert json.loads(context.request.content.decode("utf-8"))["model"] == "other-model"  # Model should be unchanged


@pytest.mark.asyncio
async def test_model_name_replacement_policy_model_in_mapping(mock_container, mock_session, model_mapping):
    policy = ModelNameReplacementPolicy(model_mapping=model_mapping)
    
    for fake_name, real_name in model_mapping.items():
        request_content = json.dumps({"model": fake_name, "messages": []}).encode("utf-8")
        context = TransactionContext(request=cast(httpx.Request, MockRequest(content=request_content)))
        
        result = await policy.apply(context, mock_container, mock_session)
        assert result == context  # Context should be returned
        assert json.loads(context.request.content.decode("utf-8"))["model"] == real_name  # Model should be replaced


@pytest.mark.parametrize(
    "model_mapping,name",
    [
        ({"fakename": "realname"}, None),
        ({"gemini-2.5-pro-preview-05-06": "gpt-4o"}, "TestPolicy"),
    ],
)
def test_model_name_replacement_policy_serialization(model_mapping: Dict[str, str], name: str):
    policy = ModelNameReplacementPolicy(model_mapping=model_mapping, name=name)
    
    serialized = policy.serialize()
    expected_name = name or "ModelNameReplacementPolicy"
    
    assert serialized["name"] == expected_name
    assert serialized["model_mapping"] == model_mapping
    
    deserialized = ModelNameReplacementPolicy.from_serialized(serialized)
    
    assert deserialized.name == expected_name
    assert deserialized.model_mapping == model_mapping

import importlib
import inspect
import pkgutil
from typing import ForwardRef, List, Type, get_type_hints

import luthien_control.control_policy  # Import the package
import pytest
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext
from sqlalchemy.ext.asyncio import AsyncSession


def discover_policy_classes() -> List[Type[ControlPolicy]]:
    """Discovers all non-abstract subclasses of ControlPolicy within the control_policy package."""
    policy_classes = []
    package = luthien_control.control_policy
    prefix = package.__name__ + "."

    # Iterate through modules in the package path
    for _, module_name, _ in pkgutil.walk_packages(package.__path__, prefix):
        try:
            module = importlib.import_module(module_name)
            # Iterate through members of the module
            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, ControlPolicy)
                    and obj is not ControlPolicy
                    and not inspect.isabstract(obj)
                ):
                    if obj not in policy_classes:  # Avoid duplicates
                        policy_classes.append(obj)
        except Exception as e:
            # Use proper f-string formatting
            print(f"Warning: Could not import or inspect module {module_name}: {e}")

    # Use proper f-string formatting
    print(f"Discovered policy classes: {[cls.__name__ for cls in policy_classes]}")
    return policy_classes


# Run discovery to get the list of classes for parameterization
ALL_POLICY_CLASSES = discover_policy_classes()

# --- Compliance Test Cases ---


@pytest.mark.parametrize("policy_class", ALL_POLICY_CLASSES)
def test_policy_apply_signature(policy_class: Type[ControlPolicy]):
    """Verify the 'apply' method signature for all ControlPolicy subclasses."""
    assert hasattr(policy_class, "apply"), f"{policy_class.__name__} missing 'apply' method"
    apply_method = getattr(policy_class, "apply")
    assert inspect.iscoroutinefunction(apply_method), f"{policy_class.__name__}.apply must be async"

    sig = inspect.signature(apply_method)
    params = sig.parameters

    # Check parameter names and order (ignoring 'self')
    expected_params = ["self", "context", "container", "session"]
    assert list(params.keys()) == expected_params, (
        f"{policy_class.__name__}.apply parameter names mismatch: {list(params.keys())}"
    )

    # Check parameter type hints (more involved due to potential ForwardRefs)
    try:
        # Resolve forward references using the module's globals
        type_hints = get_type_hints(apply_method, globalns=inspect.getmodule(policy_class).__dict__)
    except Exception as e:
        pytest.fail(f"Could not get type hints for {policy_class.__name__}.apply: {e}")

    # Note: get_type_hints includes the return type
    assert type_hints.get("context") is TransactionContext, (
        f"{policy_class.__name__}.apply 'context' hint is not TransactionContext: {type_hints.get('context')}"
    )
    assert type_hints.get("container") is DependencyContainer, (
        f"{policy_class.__name__}.apply 'container' hint is not DependencyContainer: {type_hints.get('container')}"
    )
    assert type_hints.get("session") is AsyncSession, (
        f"{policy_class.__name__}.apply 'session' hint is not AsyncSession: {type_hints.get('session')}"
    )
    assert type_hints.get("return") is TransactionContext, (
        f"{policy_class.__name__}.apply return hint is not TransactionContext: {type_hints.get('return')}"
    )


@pytest.mark.parametrize("policy_class", ALL_POLICY_CLASSES)
def test_policy_serialize_signature(policy_class: Type[ControlPolicy]):
    """Verify the 'serialize' method signature for all ControlPolicy subclasses."""
    assert hasattr(policy_class, "serialize"), f"{policy_class.__name__} missing 'serialize' method"
    serialize_method = getattr(policy_class, "serialize")
    assert callable(serialize_method), f"{policy_class.__name__}.serialize must be callable"

    sig = inspect.signature(serialize_method)
    params = sig.parameters
    assert list(params.keys()) == ["self"], (
        f"{policy_class.__name__}.serialize should only take 'self': {list(params.keys())}"
    )

    try:
        type_hints = get_type_hints(serialize_method, globalns=inspect.getmodule(policy_class).__dict__)
    except Exception as e:
        pytest.fail(f"Could not get type hints for {policy_class.__name__}.serialize: {e}")

    return_hint = type_hints.get("return")
    assert return_hint is not None, f"{policy_class.__name__}.serialize missing return type hint"
    # Compare name instead of type object identity/equality due to resolution issues
    assert getattr(return_hint, "__name__", str(return_hint)) == SerializableDict.__name__, (
        f"{policy_class.__name__}.serialize return hint is not SerializableDict: {return_hint}"
    )


@pytest.mark.parametrize("policy_class", ALL_POLICY_CLASSES)
def test_policy_from_serialized_signature(policy_class: Type[ControlPolicy]):
    """Verify the 'from_serialized' classmethod signature for all ControlPolicy subclasses."""
    assert hasattr(policy_class, "from_serialized"), f"{policy_class.__name__} missing 'from_serialized' method"

    # Use inspect.getattr_static to get the attribute without invoking the descriptor protocol
    from_serialized_obj = inspect.getattr_static(policy_class, "from_serialized")
    assert isinstance(from_serialized_obj, classmethod), (
        f"{policy_class.__name__}.from_serialized should be a classmethod descriptor, got {type(from_serialized_obj)}"
    )

    # Get the actual function underlying the classmethod
    actual_func = from_serialized_obj.__func__
    assert callable(actual_func), f"{policy_class.__name__}.from_serialized underlying func must be callable"

    sig = inspect.signature(actual_func)
    params = sig.parameters

    # Expected parameters: cls, config
    param_names = list(params.keys())
    assert param_names[0] == "cls", f"{policy_class.__name__}.from_serialized first param should be 'cls'"
    assert param_names[1] == "config", f"{policy_class.__name__}.from_serialized second param should be 'config'"
    assert len(param_names) == 2, f"{policy_class.__name__}.from_serialized should only accept 'cls' and 'config'"

    # Check return type hint
    try:
        type_hints = get_type_hints(actual_func, globalns=inspect.getmodule(policy_class).__dict__)
    except Exception as e:
        pytest.fail(f"Could not get type hints for {policy_class.__name__}.from_serialized: {e}")

    return_hint = type_hints.get("return")
    expected_return = policy_class  # Expect the class itself, or a ForwardRef to it

    if return_hint is None:
        pytest.fail(f"{policy_class.__name__}.from_serialized missing return type hint")

    # Handle ForwardRef correctly
    if isinstance(return_hint, ForwardRef):
        # Check if the ForwardRef refers to the policy class name
        assert return_hint.__forward_arg__ == policy_class.__name__, (
            f"{policy_class.__name__}.from_serialized return hint is ForwardRef('{return_hint.__forward_arg__}'), "
            f"expected '{policy_class.__name__}'"
        )
    elif getattr(return_hint, "__origin__", None) is Type and hasattr(return_hint, "__args__"):
        args = getattr(return_hint, "__args__", None)
        assert args is not None and args[0] is expected_return, (
            f"{policy_class.__name__}.from_serialized return hint is {return_hint}, "
            f"expected Type[{expected_return.__name__}]"
        )
    else:  # Direct type hint
        assert return_hint is expected_return, (
            f"{policy_class.__name__}.from_serialized return hint is {return_hint}, expected {expected_return.__name__}"
        )


@pytest.mark.parametrize("policy_class", ALL_POLICY_CLASSES)
def test_policy_required_dependencies_attribute(policy_class: Type[ControlPolicy]):
    """Verify the optional 'REQUIRED_DEPENDENCIES' class attribute."""
    # This check is optional as not all policies might define it explicitly
    if hasattr(policy_class, "REQUIRED_DEPENDENCIES"):
        req_deps = getattr(policy_class, "REQUIRED_DEPENDENCIES")
        assert isinstance(req_deps, (list, set)), (
            f"{policy_class.__name__}.REQUIRED_DEPENDENCIES must be a list or set, found {type(req_deps)}"
        )
        for dep in req_deps:
            assert isinstance(dep, str), (
                f"{policy_class.__name__}.REQUIRED_DEPENDENCIES must contain strings, found {type(dep)}: {dep}"
            )

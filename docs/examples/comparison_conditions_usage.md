# Using Comparison Conditions

This guide explains how to use comparison conditions in control policies and how to handle type checker warnings.

## Basic Usage

Comparison conditions provide a clean way to evaluate values in transactions:

```python
from luthien_control.control_policy.conditions.comparison_conditions import (
    EqualsCondition,
    ContainsCondition,
    GreaterThanCondition
)
from luthien_control.control_policy.conditions.value_resolvers import path

# Compare request field to static value
model_condition = EqualsCondition(path("request.payload.model"), "gpt-4o")

# Compare two dynamic values
temperature_condition = EqualsCondition(
    path("request.payload.temperature"), 
    path("data.settings.default_temperature")
)

# Check if array contains value
model_allowed = ContainsCondition(
    path("data.settings.allowed_models"), 
    path("request.payload.model")
)

# Numeric comparisons
token_limit = GreaterThanCondition(path("request.payload.max_tokens"), 1000)
```

## Available Condition Types

- `EqualsCondition` - Check if values are equal
- `NotEqualsCondition` - Check if values are not equal  
- `ContainsCondition` - Check if left contains right (arrays, strings)
- `LessThanCondition` - Numeric less than comparison
- `LessThanOrEqualCondition` - Numeric less than or equal comparison
- `GreaterThanCondition` - Numeric greater than comparison
- `GreaterThanOrEqualCondition` - Numeric greater than or equal comparison
- `RegexMatchCondition` - Check if value matches regex pattern

## Constructor Patterns

Each condition supports two constructor patterns:

### Positional Arguments (Recommended)
```python
# Concise and readable
condition = EqualsCondition(path("request.payload.model"), "gpt-4o")
condition = ContainsCondition(["gpt-4o", "gpt-3.5-turbo"], path("request.payload.model"))
```

### Keyword Arguments (Type-safe)
```python
# Explicit and type-checker friendly
condition = EqualsCondition(left=path("request.payload.model"), right="gpt-4o")
condition = ContainsCondition(left=["gpt-4o", "gpt-3.5-turbo"], right=path("request.payload.model"))
```

## Handling Pyright Type Checker Warnings

When using positional arguments, you may encounter this pyright warning:
```
Expected 0 positional arguments (reportCallIssue)
```

This is a known issue due to the underlying Pydantic BaseModel inheritance. The code works correctly at runtime.

### Solution 1: Suppress Individual Calls
```python
condition = EqualsCondition(path("test"), "value")  # pyright: ignore[reportCallIssue]
```

### Solution 2: Suppress at File Level
Add this at the top of your Python file:
```python
# pyright: reportCallIssue=false
```

### Solution 3: Use Keyword Arguments
```python
# No warnings with keyword arguments
condition = EqualsCondition(left=path("test"), right="value")
```

## Best Practices

1. **Use positional arguments** for concise, readable condition creation in tests and simple cases
2. **Use keyword arguments** when working in strict typing environments or when clarity is paramount
3. **Suppress warnings selectively** using the `# pyright: ignore[reportCallIssue]` comment rather than disabling all call issue reports
4. **Group related suppressions** by adding `# pyright: reportCallIssue=false` at the file level when you have many comparison conditions

## Example: Policy with Conditions

```python
# pyright: reportCallIssue=false

from luthien_control.control_policy.branching_policy import BranchingPolicy
from luthien_control.control_policy.conditions.comparison_conditions import EqualsCondition
from luthien_control.control_policy.conditions.value_resolvers import path
from luthien_control.control_policy.noop_policy import NoopPolicy
from collections import OrderedDict

# Create conditions with natural syntax
gpt4_condition = EqualsCondition(path("request.payload.model"), "gpt-4o")
admin_condition = EqualsCondition(path("data.user_type"), "admin")

# Use in branching policy
policy_map = OrderedDict([
    (gpt4_condition, NoopPolicy(name="GPT-4 Policy")),
    (admin_condition, NoopPolicy(name="Admin Policy"))
])

branching_policy = BranchingPolicy(cond_to_policy_map=policy_map)
```

This approach gives you clean, readable condition definitions while properly handling type checker concerns. 
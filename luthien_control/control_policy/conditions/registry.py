from luthien_control.control_policy.conditions.all_cond import AllCondition
from luthien_control.control_policy.conditions.any_cond import AnyCondition
from luthien_control.control_policy.conditions.comparisons import (
    ContainsCondition,
    EqualsCondition,
    GreaterThanCondition,
    GreaterThanOrEqualCondition,
    LessThanCondition,
    LessThanOrEqualCondition,
    NotEqualsCondition,
    RegexMatchCondition,
)
from luthien_control.control_policy.conditions.not_cond import NotCondition

NAME_TO_CONDITION_CLASS = {
    "not": NotCondition,
    "any": AnyCondition,
    "all": AllCondition,
    "equals": EqualsCondition,
    "not_equals": NotEqualsCondition,
    "less_than": LessThanCondition,
    "less_than_or_equal": LessThanOrEqualCondition,
    "greater_than": GreaterThanCondition,
    "greater_than_or_equal": GreaterThanOrEqualCondition,
    "regex_match": RegexMatchCondition,
    "contains": ContainsCondition,
}

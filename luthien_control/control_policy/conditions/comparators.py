import re
from typing import Any, Callable


class Comparator:
    def __init__(self, fn: Callable[[Any, Any], bool]):
        self.fn = fn

    def evaluate(self, left: Any, right: Any) -> bool:
        return self.fn(left, right)


equals = Comparator(lambda a, b: a == b)
contains = Comparator(lambda a, b: a in b)
less_than = Comparator(lambda a, b: a < b)
less_than_or_equal = Comparator(lambda a, b: a <= b)
greater_than = Comparator(lambda a, b: a > b)
greater_than_or_equal = Comparator(lambda a, b: a >= b)
regex_match = Comparator(lambda target, pattern: re.search(pattern, target) is not None)

NAME_TO_COMPARATOR = {
    "equals": equals,
    "contains": contains,
    "less_than": less_than,
    "less_than_or_equal": less_than_or_equal,
    "greater_than": greater_than,
    "greater_than_or_equal": greater_than_or_equal,
    "regex_match": regex_match,
}

COMPARATOR_TO_NAME = {v: k for k, v in NAME_TO_COMPARATOR.items()}

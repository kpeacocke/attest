"""Applicability predicate evaluation for controls (REQ-3.1)."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any


@dataclass
class ApplicabilityDecision:
    """Outcome of evaluating a control's only_if/skip_if predicates."""

    applicable: bool
    reason: str = ""
    error: str = ""


class _SafeEvaluator:
    """Evaluate a restricted Python expression AST against a variable mapping."""

    def __init__(self, variables: dict[str, Any]) -> None:
        self.variables = variables

    def eval(self, expression: str) -> Any:
        tree = ast.parse(expression, mode="eval")
        return self._eval_node(tree.body)

    def _eval_name(self, node: ast.Name) -> Any:
        if node.id not in self.variables:
            raise ValueError(f"Unknown predicate variable '{node.id}'.")
        return self.variables[node.id]

    def _eval_bool_op(self, node: ast.BoolOp) -> bool:
        values = [bool(self._eval_node(v)) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError("Unsupported boolean operator in predicate.")

    def _compare_values(self, left: Any, op: ast.cmpop, right: Any) -> bool:
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right
        if isinstance(op, ast.In):
            return left in right
        if isinstance(op, ast.NotIn):
            return left not in right
        raise ValueError("Unsupported comparison operator in predicate.")

    def _eval_compare(self, node: ast.Compare) -> bool:
        left = self._eval_node(node.left)
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            right = self._eval_node(comparator)
            if not self._compare_values(left, op, right):
                return False
            left = right
        return True

    def _eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            return self._eval_name(node)

        if isinstance(node, ast.BoolOp):
            return self._eval_bool_op(node)

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not bool(self._eval_node(node.operand))

        if isinstance(node, ast.Compare):
            return self._eval_compare(node)

        raise ValueError("Unsupported syntax in predicate expression.")


def evaluate_applicability(
    *,
    only_if: str | None,
    skip_if: str | None,
    variables: dict[str, Any],
) -> ApplicabilityDecision:
    """Evaluate applicability predicates and return a deterministic decision."""
    evaluator = _SafeEvaluator(variables)

    if only_if:
        try:
            only_result = bool(evaluator.eval(only_if))
        except Exception as exc:
            return ApplicabilityDecision(
                applicable=False,
                error=f"only_if predicate error: {exc}",
            )
        if not only_result:
            return ApplicabilityDecision(
                applicable=False, reason=f"only_if not satisfied: {only_if}"
            )

    if skip_if:
        try:
            skip_result = bool(evaluator.eval(skip_if))
        except Exception as exc:
            return ApplicabilityDecision(
                applicable=False,
                error=f"skip_if predicate error: {exc}",
            )
        if skip_result:
            return ApplicabilityDecision(applicable=False, reason=f"skip_if matched: {skip_if}")

    return ApplicabilityDecision(applicable=True)

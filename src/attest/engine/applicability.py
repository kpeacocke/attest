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

    def _eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id not in self.variables:
                raise ValueError(f"Unknown predicate variable '{node.id}'.")
            return self.variables[node.id]

        if isinstance(node, ast.BoolOp):
            values = [bool(self._eval_node(v)) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
            raise ValueError("Unsupported boolean operator in predicate.")

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not bool(self._eval_node(node.operand))

        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators, strict=False):
                right = self._eval_node(comparator)
                if isinstance(op, ast.Eq):
                    ok = left == right
                elif isinstance(op, ast.NotEq):
                    ok = left != right
                elif isinstance(op, ast.Lt):
                    ok = left < right
                elif isinstance(op, ast.LtE):
                    ok = left <= right
                elif isinstance(op, ast.Gt):
                    ok = left > right
                elif isinstance(op, ast.GtE):
                    ok = left >= right
                elif isinstance(op, ast.In):
                    ok = left in right
                elif isinstance(op, ast.NotIn):
                    ok = left not in right
                else:
                    raise ValueError("Unsupported comparison operator in predicate.")

                if not ok:
                    return False
                left = right
            return True

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

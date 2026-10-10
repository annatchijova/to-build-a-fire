"""Bounded static scenario check for the sample authorization function.

This module parses MR source as data. It never imports or executes that source.
Only a deliberately small Python AST subset is understood; unknown syntax yields
NOT_RUN so the policy keeps human attention on the claim.
"""

from __future__ import annotations

import ast


MAX_SOURCE_BYTES = 256_000
CHECK_SCOPE = (
    "Static AST interpretation of src/auth.py:can_read_record over all eight "
    "combinations of authenticated, admin, and owner booleans in the supported "
    "expression subset. "
    "This does not prove repository-wide imports, runtime reachability, or "
    "authorization behavior outside this function."
)


class _UnsupportedSyntax(Exception):
    pass


_NO_RETURN = object()
_ATTRIBUTES = {
    ("user", "is_authenticated"),
    ("user", "is_admin"),
    ("user", "id"),
    ("record", "owner_id"),
}


def _validate_expression(node: ast.AST) -> None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        if (node.value.id, node.attr) in {
            ("user", "is_authenticated"), ("user", "is_admin"),
        }:
            return
    if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        if len(node.values) < 2:
            raise _UnsupportedSyntax
        for value in node.values:
            _validate_expression(value)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        _validate_expression(node.operand)
        return
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
        left = _attribute_key(node.left)
        right = _attribute_key(node.comparators[0])
        if {left, right} != {("user", "id"), ("record", "owner_id")}:
            raise _UnsupportedSyntax
        return
    raise _UnsupportedSyntax


def _attribute_key(node: ast.AST) -> tuple[str, str] | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        key = (node.value.id, node.attr)
        return key if key in _ATTRIBUTES else None
    return None


def _validate_statements(statements: list[ast.stmt]) -> None:
    for statement in statements:
        if isinstance(statement, ast.Return):
            if statement.value is None:
                raise _UnsupportedSyntax
            _validate_expression(statement.value)
        elif isinstance(statement, ast.If):
            _validate_expression(statement.test)
            _validate_statements(statement.body)
            _validate_statements(statement.orelse)
        else:
            raise _UnsupportedSyntax


def _attribute_value(node: ast.Attribute, context: dict[str, dict[str, object]]) -> object:
    if not isinstance(node.value, ast.Name):
        raise _UnsupportedSyntax
    key = (node.value.id, node.attr)
    if key not in _ATTRIBUTES:
        raise _UnsupportedSyntax
    return context[node.value.id][node.attr]


def _evaluate(node: ast.AST, context: dict[str, dict[str, object]]) -> object:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Attribute):
        return _attribute_value(node, context)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result: object = True
            for value in node.values:
                result = _evaluate(value, context)
                if not bool(result):
                    return result
            return result
        result = False
        for value in node.values:
            result = _evaluate(value, context)
            if bool(result):
                return result
        return result
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not bool(_evaluate(node.operand, context))
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        left = _evaluate(node.left, context)
        right = _evaluate(node.comparators[0], context)
        if isinstance(node.ops[0], ast.Eq):
            return left == right
        if isinstance(node.ops[0], ast.NotEq):
            return left != right
    raise _UnsupportedSyntax


def _execute_statements(statements: list[ast.stmt], context: dict[str, dict[str, object]]) -> object:
    for statement in statements:
        if isinstance(statement, ast.Return):
            assert statement.value is not None
            return _evaluate(statement.value, context)
        if isinstance(statement, ast.If):
            branch = statement.body if bool(_evaluate(statement.test, context)) else statement.orelse
            result = _execute_statements(branch, context)
            if result is not _NO_RETURN:
                return result
            continue
        raise _UnsupportedSyntax
    return _NO_RETURN


def _scenarios() -> list[tuple[str, dict[str, dict[str, object]], bool]]:
    scenarios = []
    for authenticated in (False, True):
        for admin in (False, True):
            for owner in (False, True):
                if not authenticated:
                    name = "unauthenticated_denied"
                elif admin:
                    name = "admin_allowed"
                elif owner:
                    name = "owner_allowed"
                else:
                    name = "authenticated_non_owner_denied"
                scenario_id = (
                    f"{name} (authenticated={str(authenticated).lower()}, "
                    f"admin={str(admin).lower()}, owner={str(owner).lower()})"
                )
                scenarios.append((scenario_id, {
                    "user": {"is_authenticated": authenticated, "is_admin": admin, "id": 7},
                    "record": {"owner_id": 7 if owner else 8},
                }, authenticated and (admin or owner)))
    return scenarios


def _not_run(reason: str) -> dict[str, object]:
    return {"status": "NOT_RUN", "failed_scenarios": [], "details": f"NOT_RUN: {reason}"}


def check_authorization_invariants(source: bytes | None) -> dict[str, object]:
    """Evaluate a finite, declared scenario matrix without executing MR code."""
    if source is None:
        return _not_run("src/auth.py is absent at the requested revision")
    if not isinstance(source, bytes):
        return _not_run("source is not bytes")
    if len(source) > MAX_SOURCE_BYTES:
        return _not_run("source exceeds the 256 KB limit")
    try:
        text = source.decode("utf-8", errors="strict")
        module = ast.parse(text, filename="src/auth.py", mode="exec")
    except (UnicodeDecodeError, SyntaxError, ValueError, RecursionError):
        return _not_run("source is not bounded, valid UTF-8 Python syntax")

    module_statements = list(module.body)
    if (module_statements and isinstance(module_statements[0], ast.Expr)
            and isinstance(module_statements[0].value, ast.Constant)
            and isinstance(module_statements[0].value.value, str)):
        module_statements.pop(0)
    if len(module_statements) != 1 or not isinstance(module_statements[0], ast.FunctionDef):
        return _not_run("module has top-level code outside the supported function")

    functions = [
        node for node in module_statements
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "can_read_record"
    ]
    if len(functions) != 1 or not isinstance(functions[0], ast.FunctionDef):
        return _not_run("expected one top-level synchronous can_read_record function")
    function = functions[0]
    arguments = function.args
    if (function.decorator_list or arguments.posonlyargs or arguments.vararg
            or arguments.kwonlyargs or arguments.kwarg or arguments.defaults
            or [arg.arg for arg in arguments.args] != ["user", "record"]):
        return _not_run("can_read_record signature or decorators are unsupported")

    statements = list(function.body)
    if statements and isinstance(statements[0], ast.Expr) and isinstance(statements[0].value, ast.Constant) and isinstance(statements[0].value.value, str):
        statements.pop(0)
    try:
        _validate_statements(statements)
        failed = []
        for name, context, expected in _scenarios():
            actual = _execute_statements(statements, context)
            if not isinstance(actual, bool):
                return _not_run("can_read_record did not return a boolean in every scenario")
            if actual is not expected:
                failed.append(name)
    except _UnsupportedSyntax:
        return _not_run("function uses syntax outside the supported static subset")
    except RecursionError:
        return _not_run("function AST nesting exceeds the supported limit")

    failed = sorted(failed)
    status = "FAIL" if failed else "PASS"
    if failed:
        details = "FAIL: expected authorization behavior violated in " + ", ".join(failed)
    else:
        details = "PASS: all eight combinations in the supported expression subset matched"
    return {"status": status, "failed_scenarios": failed, "details": details}


def build_authorization_check(source: bytes | None, revision: str) -> dict[str, object]:
    """Bind the static result and its finite scope to the exact MR head SHA."""
    result = check_authorization_invariants(source)
    return {
        "id": "authorization-invariants",
        "claim_id": "authorization-boundary",
        "status": result["status"],
        "revision": revision,
        "source": {"name": "tbaf-static-auth-invariants", "version": "1"},
        "scope": CHECK_SCOPE,
        "artifact_ref": f"git-object:{revision}:src/auth.py" if source is not None else None,
        "details": result["details"],
    }

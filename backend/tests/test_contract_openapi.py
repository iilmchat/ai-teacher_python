"""Контрактные тесты OpenAPI (S22-001).

Снапшот `tests/contracts/openapi.json` — то, что мы обещаем клиентам.
Тест разрешает только аддитивные изменения; всё остальное требует осознанного
обновления снапшота отдельным коммитом (`python scripts/snapshot_openapi.py`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.main import app
from tests.contract_utils import diff_openapi, diff_shape

CONTRACTS = Path(__file__).parent / "contracts"
SNAPSHOT = CONTRACTS / "openapi.json"


def _snapshot() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return data


def _spec(
    paths: dict[str, Any] | None = None,
    schemas: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "paths": paths or {},
        "components": {"schemas": schemas or {}},
    }


def _op(schema_ref: str = "#/components/schemas/Item") -> dict[str, Any]:
    return {
        "responses": {
            "200": {
                "content": {
                    "application/json": {"schema": {"$ref": schema_ref}},
                }
            }
        }
    }


def test_openapi_matches_snapshot() -> None:
    problems = diff_openapi(_snapshot(), app.openapi())

    assert problems == [], (
        "OpenAPI изменился несовместимо со снапшотом:\n  - "
        + "\n  - ".join(problems)
        + "\nЕсли изменение осознанное и аддитивное — обновите снапшот: "
        "python scripts/snapshot_openapi.py"
    )


def test_snapshot_is_valid_json_with_paths() -> None:
    snapshot = _snapshot()

    assert snapshot["info"]["title"]
    assert snapshot["paths"], "снапшот пуст — перегенерируйте"
    assert snapshot["components"]["schemas"], "в снапшоте нет схем"


def test_removed_path_is_breaking() -> None:
    expected = _spec(paths={"/a": {"get": _op()}})
    actual = _spec(paths={})

    assert any("удалён путь /a" in problem for problem in diff_openapi(expected, actual))


def test_removed_method_is_breaking() -> None:
    expected = _spec(paths={"/a": {"get": _op(), "post": _op()}})
    actual = _spec(paths={"/a": {"get": _op()}})

    problems = diff_openapi(expected, actual)
    assert any("удалена операция POST /a" in problem for problem in problems)


def test_removed_response_field_is_breaking() -> None:
    expected = _spec(
        paths={"/a": {"get": _op()}},
        schemas={"Item": {"type": "object", "properties": {"id": {"type": "integer"}}}},
    )
    actual = _spec(
        paths={"/a": {"get": _op()}},
        schemas={"Item": {"type": "object", "properties": {}}},
    )

    problems = diff_openapi(expected, actual)
    assert any("удалено поле 'id'" in problem for problem in problems)


def test_type_change_is_breaking() -> None:
    expected = _spec(
        paths={"/a": {"get": _op()}},
        schemas={"Item": {"type": "object", "properties": {"id": {"type": "integer"}}}},
    )
    actual = _spec(
        paths={"/a": {"get": _op()}},
        schemas={"Item": {"type": "object", "properties": {"id": {"type": "string"}}}},
    )

    problems = diff_openapi(expected, actual)
    assert any("тип 'string' вместо 'integer'" in problem for problem in problems)


def test_new_required_field_is_breaking() -> None:
    expected = _spec(
        paths={"/a": {"get": _op()}},
        schemas={
            "Item": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
            }
        },
    )
    actual = _spec(
        paths={"/a": {"get": _op()}},
        schemas={
            "Item": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "x": {"type": "string"}},
                "required": ["id", "x"],
            }
        },
    )

    problems = diff_openapi(expected, actual)
    assert any("новое обязательное поле 'x'" in problem for problem in problems)


def test_removed_enum_value_is_breaking() -> None:
    expected = _spec(
        paths={"/a": {"get": _op()}},
        schemas={
            "Item": {
                "type": "object",
                "properties": {"status": {"type": "string", "enum": ["a", "b"]}},
            }
        },
    )
    actual = _spec(
        paths={"/a": {"get": _op()}},
        schemas={
            "Item": {
                "type": "object",
                "properties": {"status": {"type": "string", "enum": ["a"]}},
            }
        },
    )

    problems = diff_openapi(expected, actual)
    assert any("удалены значения enum ['b']" in problem for problem in problems)


def test_removed_response_code_is_breaking() -> None:
    expected = _spec(paths={"/a": {"get": {"responses": {"200": {}, "404": {}}}}})
    actual = _spec(paths={"/a": {"get": {"responses": {"200": {}}}}})

    problems = diff_openapi(expected, actual)
    assert any("удалён ответ 404" in problem for problem in problems)


def test_additive_changes_are_allowed() -> None:
    expected = _spec(
        paths={"/a": {"get": _op()}},
        schemas={
            "Item": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "status": {"type": "string", "enum": ["a"]},
                },
                "required": ["id"],
            }
        },
    )
    actual = _spec(
        paths={"/a": {"get": _op()}, "/b": {"get": _op()}},
        schemas={
            "Item": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "status": {"type": "string", "enum": ["a", "b"]},
                    "new_optional": {"type": "string"},
                },
                "required": ["id"],
            },
            "Extra": {"type": "object"},
        },
    )

    assert diff_openapi(expected, actual) == []


def test_shape_detects_missing_field() -> None:
    problems = diff_shape({"id": "number", "name": "str"}, {"id": "number"}, "resp")

    assert problems == ["resp: пропало поле 'name'"]


def test_shape_allows_new_field_and_checks_nested() -> None:
    assert diff_shape({"id": "number"}, {"id": "number", "extra": "str"}, "resp") == []

    problems = diff_shape(
        {"items": [{"id": "number"}]},
        {"items": [{"name": "str"}]},
        "resp",
    )
    assert problems == ["resp.items[]: пропало поле 'id'"]

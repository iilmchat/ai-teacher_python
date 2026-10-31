"""Сравнение OpenAPI-снапшотов и «форм» ответов (S22-001).

Правила совместимости — аддитивные изменения разрешены, breaking запрещены:

* пути и операции можно добавлять, но не удалять;
* коды ответов можно добавлять, но не удалять;
* поля схем можно добавлять (необязательные), но не удалять и не менять тип;
* новое **обязательное** поле — breaking (меняет контракт запроса/ответа);
* значения `enum` можно добавлять, но не удалять;
* новое значение `enum` — аддитивно.

Те же правила применяются к «форме» JSON-ответа (`dict`/`list`/`str`),
которую фиксируют фикстуры ключевых эндпоинтов.
"""

from __future__ import annotations

from typing import Any

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "options", "head"})


def shape(value: Any) -> Any:
    """Форма JSON: ключи словаря, длины списков, тип скаляра.

    Значения не сравниваются (они зависят от данных), но структура — да.
    Пустой список остаётся `[]` (форма неизвестна) — это осознанно: эндпоинт
    может вернуть пустую выдачу на тестовых данных.
    """
    if isinstance(value, dict):
        return {key: shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        if not value:
            return []
        # Первый элемент задаёт форму; смешанные списки в API не встречаются.
        first = shape(value[0])
        for item in value[1:]:
            if shape(item) != first:
                return [first, shape(item)]
        return [first]
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "str"
    if value is None:
        return None
    return type(value).__name__


def _pointer(spec: dict[str, Any], ref: str) -> Any:
    node: Any = spec
    for part in ref.lstrip("#/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _resolve(node: Any, spec: dict[str, Any]) -> Any:
    seen: set[str] = set()
    while isinstance(node, dict) and "$ref" in node:
        ref = str(node["$ref"])
        if ref in seen or not ref.startswith("#/"):
            return node
        seen.add(ref)
        resolved = _pointer(spec, ref)
        if resolved is None:
            return node
        node = resolved
    return node


def _diff_schema(
    expected: Any,
    actual: Any,
    expected_spec: dict[str, Any],
    actual_spec: dict[str, Any],
    label: str,
) -> list[str]:
    expected = _resolve(expected, expected_spec)
    actual = _resolve(actual, actual_spec)
    if expected is None or actual is None:
        return []
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return []

    problems: list[str] = []

    expected_type = expected.get("type")
    actual_type = actual.get("type")
    if expected_type and actual_type and expected_type != actual_type:
        problems.append(f"{label}: тип {actual_type!r} вместо {expected_type!r}")

    expected_enum = expected.get("enum")
    actual_enum = actual.get("enum")
    if isinstance(expected_enum, list) and isinstance(actual_enum, list):
        removed = [value for value in expected_enum if value not in actual_enum]
        if removed:
            problems.append(f"{label}: удалены значения enum {removed}")

    expected_props = expected.get("properties") or {}
    actual_props = actual.get("properties") or {}
    if isinstance(expected_props, dict) and isinstance(actual_props, dict):
        for name, subschema in expected_props.items():
            if name not in actual_props:
                problems.append(f"{label}: удалено поле {name!r}")
                continue
            problems.extend(
                _diff_schema(
                    subschema,
                    actual_props[name],
                    expected_spec,
                    actual_spec,
                    f"{label}.{name}",
                )
            )

    expected_required = set(expected.get("required") or [])
    actual_required = set(actual.get("required") or [])
    for name in sorted(expected_required - actual_required):
        problems.append(f"{label}: поле {name!r} больше не обязательное")
    for name in sorted(actual_required - expected_required):
        problems.append(f"{label}: новое обязательное поле {name!r}")

    if "items" in expected:
        problems.extend(
            _diff_schema(
                expected["items"],
                actual.get("items"),
                expected_spec,
                actual_spec,
                f"{label}[]",
            )
        )

    for keyword in ("anyOf", "oneOf", "allOf"):
        expected_variants = expected.get(keyword)
        actual_variants = actual.get(keyword)
        if isinstance(expected_variants, list) and isinstance(actual_variants, list):
            if len(actual_variants) < len(expected_variants):
                problems.append(f"{label}: меньше вариантов {keyword}")
            for index, variant in enumerate(expected_variants[: len(actual_variants)]):
                problems.extend(
                    _diff_schema(
                        variant,
                        actual_variants[index],
                        expected_spec,
                        actual_spec,
                        f"{label}.{keyword}[{index}]",
                    )
                )

    return problems


def _diff_operation(
    path: str,
    method: str,
    expected_op: dict[str, Any],
    actual_op: dict[str, Any],
    expected_spec: dict[str, Any],
    actual_spec: dict[str, Any],
) -> list[str]:
    label = f"{method.upper()} {path}"
    problems: list[str] = []

    expected_responses = expected_op.get("responses") or {}
    actual_responses = actual_op.get("responses") or {}
    for code, expected_response in expected_responses.items():
        if code not in actual_responses:
            problems.append(f"{label}: удалён ответ {code}")
            continue
        expected_content = (expected_response or {}).get("content") or {}
        actual_content = (actual_responses[code] or {}).get("content") or {}
        for media_type, body in expected_content.items():
            if media_type not in actual_content:
                problems.append(f"{label}: удалён тип {media_type} в ответе {code}")
                continue
            problems.extend(
                _diff_schema(
                    (body or {}).get("schema"),
                    (actual_content[media_type] or {}).get("schema"),
                    expected_spec,
                    actual_spec,
                    f"{label} {code} {media_type}",
                )
            )

    expected_body = (expected_op.get("requestBody") or {}).get("content") or {}
    actual_body = (actual_op.get("requestBody") or {}).get("content") or {}
    for media_type, body in expected_body.items():
        if media_type not in actual_body:
            problems.append(f"{label}: удалён тип {media_type} в запросе")
            continue
        problems.extend(
            _diff_schema(
                (body or {}).get("schema"),
                (actual_body[media_type] or {}).get("schema"),
                expected_spec,
                actual_spec,
                f"{label} request {media_type}",
            )
        )

    return problems


def diff_openapi(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Список breaking-изменений (пустой список — контракт совместим)."""
    problems: list[str] = []

    expected_paths = expected.get("paths") or {}
    actual_paths = actual.get("paths") or {}
    for path, expected_item in expected_paths.items():
        if path not in actual_paths:
            problems.append(f"удалён путь {path}")
            continue
        for method, expected_op in expected_item.items():
            if method not in HTTP_METHODS:
                continue
            if method not in actual_paths[path]:
                problems.append(f"удалена операция {method.upper()} {path}")
                continue
            problems.extend(
                _diff_operation(
                    path,
                    method,
                    expected_op,
                    actual_paths[path][method],
                    expected,
                    actual,
                )
            )

    expected_schemas = (expected.get("components") or {}).get("schemas") or {}
    actual_schemas = (actual.get("components") or {}).get("schemas") or {}
    for name, expected_schema in expected_schemas.items():
        if name not in actual_schemas:
            problems.append(f"удалена схема {name}")
            continue
        problems.extend(
            _diff_schema(
                expected_schema,
                actual_schemas[name],
                expected,
                actual,
                f"schema {name}",
            )
        )

    return problems


def diff_shape(expected: Any, actual: Any, label: str) -> list[str]:
    """Сравнение формы JSON-ответа: ключи/типы не должны исчезать."""
    problems: list[str] = []

    if isinstance(expected, dict) and isinstance(actual, dict):
        for key, value in expected.items():
            if key not in actual:
                problems.append(f"{label}: пропало поле {key!r}")
                continue
            problems.extend(diff_shape(value, actual[key], f"{label}.{key}"))
    elif isinstance(expected, list) and isinstance(actual, list):
        if expected and actual:
            problems.extend(diff_shape(expected[0], actual[0], f"{label}[]"))
    elif isinstance(expected, str) and isinstance(actual, dict):
        # В фикстуре записан объект, а в ответе — примитив (или наоборот).
        problems.append(f"{label}: ожидался объект, пришёл {type(actual).__name__}")
    return problems

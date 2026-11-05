"""Раннер песочницы для контейнера (S24-001).

Образ собирается из `backend/sandbox_runner/Dockerfile` и **не содержит**
зависимостей приложения (pydantic, sqlalchemy, БД): только stdlib,
RestrictedPython и чистое ядро `sandbox_runtime`.

Два режима:

* по умолчанию — читает одну JSON-строку `{code, cases, memory_limit_mb,
  max_output_chars}` из stdin, на каждый кейс пишет строку результата в stdout,
  в конце — `{"done": true}` (тот же протокол, что у нативного батча);
* `--self-check` — проверка изоляции контейнера: read-only rootfs, tmpfs,
  отсутствие сети и capabilities. Печатает JSON для тестов/диагностики.
"""

from __future__ import annotations

import json
import os
import socket
import sys

sys.path.insert(0, "/app")

from app.core.sandbox_runtime import run_restricted  # noqa: E402


def _self_check() -> dict[str, object]:
    """Проверить изоляцию изнутри контейнера"""
    report: dict[str, object] = {
        "uid": os.getuid() if hasattr(os, "getuid") else -1,
        "read_only_rootfs": False,
        "tmp_writable": False,
        "network_blocked": False,
        "capabilities_zero": False,
    }

    try:
        with open("/app/should_not_write.txt", "w", encoding="utf-8") as handle:
            handle.write("x")
    except OSError:
        report["read_only_rootfs"] = True

    try:
        with open("/tmp/probe.txt", "w", encoding="utf-8") as handle:
            handle.write("x")
        report["tmp_writable"] = True
    except OSError:
        report["tmp_writable"] = False

    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=2):
            report["network_blocked"] = False
    except OSError:
        report["network_blocked"] = True

    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("CapEff:"):
                    report["capabilities_zero"] = line.split()[1] == "0000000000000000"
                    break
    except OSError:
        pass

    return report


def _run_cases(payload: dict[str, object]) -> None:
    code = str(payload.get("code", ""))
    cases = payload.get("cases") or []
    memory_limit_mb = payload.get("memory_limit_mb")
    max_output_chars = payload.get("max_output_chars")
    limits_applied = False

    for index, case in enumerate(cases):
        try:
            result = run_restricted(
                code,
                str(case),
                memory_limit_mb=int(memory_limit_mb) if memory_limit_mb else None,
                max_output_chars=int(max_output_chars) if max_output_chars else None,
                apply_limits=not limits_applied,
            )
        except BaseException as exc:  # noqa: BLE001 — SystemExit/KeyboardInterrupt
            result = {
                "success": False,
                "output": "",
                "error": f"{type(exc).__name__}: {exc}",
                "error_type": type(exc).__name__,
            }
        limits_applied = True
        result["index"] = index
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if "--self-check" in args:
        print(json.dumps(_self_check(), ensure_ascii=False))
        return 0

    line = sys.stdin.readline()
    if not line:
        return 0

    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return 2

    _run_cases(payload)
    sys.stdout.write('{"done": true}\n')
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

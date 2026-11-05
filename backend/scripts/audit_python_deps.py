#!/usr/bin/env python
"""Аудит Python-зависимостей по GitHub Advisory Database.

Зачем нужен: на машине разработки PyPI (pypi.org / files.pythonhosted.org)
заблокирован, поэтому `pip-audit` установить нельзя. Скрипт скачивает
глобальные advisory для ecosystem=pip через публичный GitHub API и сопоставляет
их с версиями из `pip list --format=json`. Только stdlib + `packaging`
(опционально; без него используется упрощённое сравнение версий).

Использование:
    python scripts/audit_python_deps.py
    python scripts/audit_python_deps.py --json-out audit.json --fail-on high
    python scripts/audit_python_deps.py --installed-json pip_list.json --offline

Коды возврата:
    0 — находок уровня >= --fail-on нет (или --fail-on none);
    1 — есть находки уровня >= --fail-on;
    2 — аудит не удалось выполнить (нет сети/кэша, данные неполные).

Ограничение: API GitHub без токена — 60 запросов/час на IP. Полный список
advisory для pip занимает порядка 30-40 страниц, поэтому результат кэшируется
в temp-каталоге (по умолчанию 24 ч), а при исчерпании лимита используется
последний кэш с пометкой partial.

Формат API: https://docs.github.com/en/rest/security-advisories/global-advisories
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

API_URL = "https://api.github.com/advisories"
USER_AGENT = "ai-teacher-python-dependency-audit/1.0"
CACHE_FILE_NAME = "github-advisories-pip.json"
DEFAULT_CACHE_TTL_HOURS = 24
DEFAULT_MAX_PAGES = 60
SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "moderate": 2,
    "medium": 2,
    "low": 1,
    "unknown": 0,
}
SEVERITY_DISPLAY = {
    "critical": "critical",
    "high": "high",
    "moderate": "moderate",
    "medium": "moderate",
    "low": "low",
    "unknown": "unknown",
}
RANGE_RE = re.compile(r"^(<=|>=|<|>|=)?\s*(\S+)$")


def normalize_name(name: str) -> str:
    """PEP 503-нормализация имени пакета."""
    return re.sub(r"[-_.]+", "-", name).lower()


def print_err(message: str) -> None:
    print(message, file=sys.stderr)


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Сравнение версий
# ---------------------------------------------------------------------------


def _parse_version(text: str) -> Any:
    try:
        from packaging.version import InvalidVersion, Version
    except ImportError:  # pragma: no cover - packaging есть в venv, но не обязателен
        return _parse_version_fallback(text)
    try:
        return Version(text)
    except InvalidVersion:
        return _parse_version_fallback(text)


def _parse_version_fallback(text: str) -> tuple[int, ...]:
    """Упрощённое сравнение: числовые части через точку, без prerelease."""
    parts: list[int] = []
    for chunk in text.split("."):
        match = re.match(r"^(\d+)", chunk)
        if not match:
            break
        parts.append(int(match.group(1)))
    return tuple(parts) or (0,)


def _compare(left: Any, right: Any) -> int:
    if left.__class__ is not right.__class__:
        # разные типы (Version vs tuple): сравниваем через строковое представление
        left, right = _parse_version_fallback(str(left)), _parse_version_fallback(str(right))
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def version_matches(installed: str, vulnerable_range: str) -> bool:
    """Проверка версии на попадание в диапазон вида '>= 2.4.0, < 2.8.0'."""
    if not vulnerable_range or not vulnerable_range.strip():
        return True
    current = _parse_version(installed)
    for raw in vulnerable_range.split(","):
        part = raw.strip()
        if not part or part == "*":
            continue
        match = RANGE_RE.match(part)
        if match is None:
            print_err(f"  ! не разобрал диапазон {part!r} ({vulnerable_range!r}), пропускаю")
            continue
        operator = match.group(1) or "="
        target_text = match.group(2)
        if target_text == "*":
            continue
        target = _parse_version(target_text)
        comparison = _compare(current, target)
        if operator == "=" and comparison != 0:
            return False
        if operator == ">" and comparison <= 0:
            return False
        if operator == ">=" and comparison < 0:
            return False
        if operator == "<" and comparison >= 0:
            return False
        if operator == "<=" and comparison > 0:
            return False
    return True


# ---------------------------------------------------------------------------
# Загрузка advisory
# ---------------------------------------------------------------------------


@dataclass
class FetchResult:
    advisories: list[dict[str, Any]]
    pages: int = 0
    partial: bool = False
    from_cache: bool = False
    error: str | None = None
    next_url: str | None = None


def _request_json(url: str, timeout: float = 60.0) -> tuple[list[dict[str, Any]], dict[str, str]]:
    import urllib.request

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
        headers = {key.lower(): value for key, value in response.headers.items()}
    if not isinstance(payload, list):
        raise ValueError(f"неожиданный ответ API: {type(payload).__name__}")
    return payload, headers


def _next_link(headers: dict[str, str]) -> str | None:
    link = headers.get("link", "")
    for chunk in link.split(","):
        parts = [item.strip() for item in chunk.split(";")]
        if len(parts) >= 2 and parts[1] in ('rel="next"', "rel=next"):
            return parts[0].strip("<>")
    return None


def cache_path() -> Path:
    return Path(tempfile.gettempdir()) / "ai-teacher-audit" / CACHE_FILE_NAME


def load_cache(max_age_hours: float, allow_partial: bool = False) -> FetchResult | None:
    path = cache_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
    except (OSError, KeyError, ValueError) as exc:
        print_err(f"! кэш advisory повреждён ({exc}), скачиваю заново")
        return None
    age_hours = (utc_now() - fetched_at).total_seconds() / 3600
    if age_hours > max_age_hours:
        return None
    advisories = payload.get("advisories", [])
    next_url = payload.get("next_url")
    print(
        f"Кэш GitHub Advisory: {len(advisories)} advisory, "
        f"возраст {age_hours:.1f} ч (лимит {max_age_hours:.0f} ч)"
    )
    if next_url and not allow_partial:
        print_err("! кэш неполный (был исчерпан лимит API) — запустите с --resume")
    return FetchResult(
        advisories=advisories,
        pages=int(payload.get("pages", 0)),
        from_cache=True,
        partial=bool(next_url),
        next_url=next_url,
    )


def save_cache(
    advisories: list[dict[str, Any]],
    pages: int = 0,
    next_url: str | None = None,
) -> None:
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "fetched_at": iso(utc_now()),
                    "pages": pages,
                    "next_url": next_url,
                    "advisories": advisories,
                }
            ),
            encoding="utf-8",
        )
        suffix = " (неполный, можно продолжить с --resume)" if next_url else ""
        print(f"Кэш сохранён: {path}{suffix}")
    except OSError as exc:  # pragma: no cover - зависит от ФС
        print_err(f"! не удалось сохранить кэш: {exc}")


def fetch_advisories(
    max_pages: int,
    start_url: str | None = None,
    advisories: list[dict[str, Any]] | None = None,
    pages_start: int = 0,
) -> FetchResult:
    """Скачать advisory для ecosystem=pip (cursor-пагинация GitHub API).

    При исчерпании лимита API возвращает partial=True и next_url, с которого
    можно продолжить вызовом --resume (лимит 60 запросов/час на IP).
    """
    items: list[dict[str, Any]] = list(advisories or [])
    url: str | None = start_url or f"{API_URL}?ecosystem=pip&per_page=100"
    result = FetchResult(advisories=items, pages=pages_start)
    started = time.monotonic()

    while url and result.pages < max_pages:
        try:
            page, headers = _request_json(url)
        except Exception as exc:  # noqa: BLE001 - сетевые ошибки разнородны
            message = f"{type(exc).__name__}: {exc}"
            if not items:
                result.error = message
                return result
            print_err(f"! ошибка на странице {result.pages + 1}: {message}")
            result.partial = True
            result.next_url = url
            return result

        items.extend(page)
        result.pages += 1
        remaining = int(headers.get("x-ratelimit-remaining", "1"))
        elapsed = time.monotonic() - started
        print(
            f"  страница {result.pages}: +{len(page)} (всего {len(items)}), "
            f"{elapsed:.1f} c, remaining={remaining}"
        )

        url = _next_link(headers)
        if not page or url is None:
            return result
        if remaining <= 1:
            print_err("! исчерпан лимит GitHub API (60 запросов/час) — данные неполные")
            result.partial = True
            result.next_url = url
            return result

    if url:
        print_err(f"! достигнут --max-pages={max_pages}, данные неполные")
        result.partial = True
        result.next_url = url
    return result


def get_advisories(args: argparse.Namespace) -> FetchResult:
    if args.offline:
        cached = load_cache(max_age_hours=float("inf"), allow_partial=True)
        if cached is None:
            return FetchResult(advisories=[], error="offline, кэша нет")
        return cached

    if args.resume:
        cached = load_cache(max_age_hours=float("inf"), allow_partial=True)
        if cached is None:
            return FetchResult(advisories=[], error="--resume: кэша нет")
        if not cached.next_url:
            print("Кэш уже полный — resume не требуется")
            return cached
        result = fetch_advisories(
            args.max_pages,
            start_url=cached.next_url,
            advisories=cached.advisories,
            pages_start=cached.pages,
        )
        save_cache(result.advisories, pages=result.pages, next_url=result.next_url)
        return result

    if not args.refresh:
        cached = load_cache(args.cache_ttl_hours)
        if cached is not None:
            return cached

    result = fetch_advisories(args.max_pages)
    if result.error:
        # Сеть недоступна — пробуем последний кэш, даже просроченный
        stale = load_cache(max_age_hours=float("inf"), allow_partial=True)
        if stale is not None:
            print_err(f"! сеть недоступна ({result.error}), использую просроченный кэш")
            stale.partial = True
            return stale
        return result
    save_cache(result.advisories, pages=result.pages, next_url=result.next_url)
    return result


# ---------------------------------------------------------------------------
# Сопоставление
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    severity: str
    package: str
    installed: str
    vulnerable_range: str
    patched: str
    advisory_id: str
    cve_id: str
    summary: str
    html_url: str


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)
    advisories: int = 0
    installed: int = 0
    partial: bool = False
    from_cache: bool = False
    pages: int = 0


def index_advisories(
    advisories: list[dict[str, Any]],
) -> dict[str, list[tuple[dict[str, Any], dict[str, Any]]]]:
    """Индекс: нормализованное имя пакета -> [(advisory, vulnerability)]."""
    index: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for advisory in advisories:
        if advisory.get("withdrawn_at"):
            continue
        for vulnerability in advisory.get("vulnerabilities") or []:
            package = vulnerability.get("package") or {}
            if package.get("ecosystem") != "pip":
                continue
            name = normalize_name(str(package.get("name", "")))
            if not name:
                continue
            index.setdefault(name, []).append((advisory, vulnerability))
    return index


def severity_of(advisory: dict[str, Any], vulnerability: dict[str, Any]) -> str:
    raw = str(vulnerability.get("severity") or advisory.get("severity") or "unknown").lower()
    return SEVERITY_DISPLAY.get(raw, raw)


def collect_findings(
    installed_map: dict[str, str],
    advisories: list[dict[str, Any]],
) -> list[Finding]:
    index = index_advisories(advisories)
    findings: list[Finding] = []
    seen: set[tuple[str, str, str]] = set()
    for package_name, installed_version in installed_map.items():
        for advisory, vulnerability in index.get(package_name, []):
            vulnerable_range = str(vulnerability.get("vulnerable_version_range") or "")
            if not version_matches(installed_version, vulnerable_range):
                continue
            advisory_id = str(advisory.get("ghsa_id") or advisory.get("cve_id") or "?")
            key = (package_name, advisory_id, vulnerable_range)
            if key in seen:
                continue
            seen.add(key)
            patched = vulnerability.get("first_patched_version") or "—"
            findings.append(
                Finding(
                    severity=severity_of(advisory, vulnerability),
                    package=package_name,
                    installed=installed_version,
                    vulnerable_range=vulnerable_range or "(все версии)",
                    patched=str(patched),
                    advisory_id=advisory_id,
                    cve_id=str(advisory.get("cve_id") or ""),
                    summary=str(advisory.get("summary") or ""),
                    html_url=str(advisory.get("html_url") or ""),
                )
            )
    findings.sort(
        key=lambda item: (SEVERITY_RANK.get(item.severity, 0), item.package, item.advisory_id),
        reverse=True,
    )
    return findings


def load_installed(args: argparse.Namespace) -> dict[str, str]:
    if args.installed_json:
        payload = json.loads(Path(args.installed_json).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("--installed-json: ожидался JSON-массив из pip list --format=json")
        return {
            normalize_name(str(item["name"])): str(item["version"])
            for item in payload
            if isinstance(item, dict) and "name" in item and "version" in item
        }

    import subprocess

    command = [sys.executable, "-m", "pip", "list", "--format=json", "--disable-pip-version-check"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"pip list завершился с кодом {completed.returncode}: {completed.stderr}"
        )
    payload = json.loads(completed.stdout)
    return {
        normalize_name(str(item["name"])): str(item["version"])
        for item in payload
        if isinstance(item, dict) and "name" in item and "version" in item
    }


# ---------------------------------------------------------------------------
# Вывод
# ---------------------------------------------------------------------------


def render_table(findings: list[Finding]) -> str:
    if not findings:
        return "Уязвимых пакетов не найдено."
    header = (
        f"{'SEVERITY':<9}{'PACKAGE':<24}{'INSTALLED':<12}"
        f"{'VULNERABLE RANGE':<24}{'PATCHED':<12}ADVISORY"
    )
    lines = [header, "-" * len(header)]
    for item in findings:
        advisory = item.advisory_id
        if item.cve_id and item.cve_id not in advisory:
            advisory = f"{advisory} / {item.cve_id}"
        lines.append(
            f"{item.severity:<9}{item.package:<24}{item.installed:<12}"
            f"{item.vulnerable_range:<24}{item.patched:<12}{advisory}"
        )
        lines.append(f"          {item.summary}")
        if item.html_url:
            lines.append(f"          {item.html_url}")
    return "\n".join(lines)


def write_json(path: Path, result: AuditResult, args: argparse.Namespace) -> None:
    summary = dict.fromkeys(("critical", "high", "moderate", "low", "unknown"), 0)
    for item in result.findings:
        summary[item.severity] = summary.get(item.severity, 0) + 1
    payload = {
        "generated_at": iso(utc_now()),
        "source": API_URL + "?ecosystem=pip",
        "audit_tool": "backend/scripts/audit_python_deps.py",
        "fail_on": args.fail_on,
        "installed_packages": result.installed,
        "advisories_checked": result.advisories,
        "pages_fetched": result.pages,
        "cache_used": result.from_cache,
        "partial": result.partial,
        "summary": summary,
        "findings": [item.__dict__ for item in result.findings],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON-отчёт: {path}")


def threshold_rank(value: str) -> int:
    if value == "none":
        return -1
    return SEVERITY_RANK[value]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Аудит Python-зависимостей по GitHub Advisory Database (без pip-audit).",
    )
    parser.add_argument(
        "--fail-on",
        choices=["critical", "high", "moderate", "low", "none"],
        default="high",
        help="порог для ненулевого кода возврата (по умолчанию high)",
    )
    parser.add_argument("--json-out", type=Path, help="куда сохранить JSON-отчёт")
    parser.add_argument("--installed-json", type=Path, help="файл с pip list --format=json")
    parser.add_argument("--offline", action="store_true", help="только кэш, без сети")
    parser.add_argument("--refresh", action="store_true", help="игнорировать свежий кэш")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="продолжить неполное скачивание с сохранённого курсора (лимит API)",
    )
    parser.add_argument(
        "--cache-ttl-hours",
        type=float,
        default=DEFAULT_CACHE_TTL_HOURS,
        help=f"срок жизни кэша advisory в часах (по умолчанию {DEFAULT_CACHE_TTL_HOURS})",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"максимум страниц API (по умолчанию {DEFAULT_MAX_PAGES})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print("Аудит Python-зависимостей (GitHub Advisory Database, ecosystem=pip)")

    try:
        installed = load_installed(args)
    except Exception as exc:  # noqa: BLE001 - сообщаем и выходим с кодом 2
        print_err(f"! не удалось получить список пакетов: {exc}")
        return 2

    fetch = get_advisories(args)
    if fetch.error:
        print_err(f"! не удалось получить advisory: {fetch.error}")
        return 2

    result = AuditResult(
        advisories=len(fetch.advisories),
        installed=len(installed),
        partial=fetch.partial,
        from_cache=fetch.from_cache,
        pages=fetch.pages,
    )
    result.findings = collect_findings(installed, fetch.advisories)

    print(f"\nПроверено пакетов: {len(installed)}; advisory: {len(fetch.advisories)}")
    if result.partial:
        print_err("ВНИМАНИЕ: данные неполные (лимит API или сеть) — результат может быть неполным")
    print()
    print(render_table(result.findings))

    summary: dict[str, int] = {}
    for item in result.findings:
        summary[item.severity] = summary.get(item.severity, 0) + 1
    print()
    if summary:
        print("Итого: " + ", ".join(f"{key}={value}" for key, value in sorted(summary.items())))
    else:
        print("Итого: находок нет")

    if args.json_out:
        write_json(args.json_out, result, args)

    threshold = threshold_rank(args.fail_on)
    blocking = [
        item for item in result.findings if SEVERITY_RANK.get(item.severity, 0) >= threshold
    ]
    if blocking:
        print(f"\nБЛОКИРУЮЩИЕ находки (severity >= {args.fail_on}): {len(blocking)}")
        return 1
    if result.partial:
        print_err("\nАудит неполный: недостаточно данных, чтобы подтвердить отсутствие уязвимостей")
        return 2
    print("\nOK: блокирующих находок нет")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

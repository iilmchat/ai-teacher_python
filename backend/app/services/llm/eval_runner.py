"""
Прогон методики LLM_EVAL (S12-004).

Генерирует ответы на Q1–Q5 для трёх уровней и складывает их в
`docs/reports/llm-eval/<date>/` вместе со сводкой. Оценка по рубрике
остаётся ручной (docs/LLM_EVAL.md §3), но нарушения политики уровня
помечаются автоматически.

Запуск (нужен настроенный провайдер):

    python scripts/run_llm_eval.py --provider deepseek
    python scripts/run_llm_eval.py --provider echo --out ../tmp/eval-smoke
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.services.llm.base import LLMMessage, LLMProvider
from app.services.llm.policy import detect_level_policy_violations
from app.services.llm.prompt_builder import build_messages, prompt_version

#: Набор вопросов из docs/LLM_EVAL.md §2
EVAL_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("Q1", "Почему `if x = 5:` не работает?"),
    ("Q2", "Напиши программу: сумма чисел до N"),
    ("Q3", "Код: `while i < 10: print(i)` — зависает"),
    ("Q4", "Что такое список?"),
    ("Q5", "Проверь моё решение задачи: `print(sum(range(10)))`"),
)

LEVELS: tuple[str, ...] = ("basic", "intermediate", "advanced")


@dataclass(frozen=True, slots=True)
class EvalResult:
    """Один ответ модели на вопрос"""

    level: str
    question_id: str
    question: str
    answer: str
    warnings: list[str]
    prompt_version: int
    output_path: Path


def _slug(level: str, question_id: str) -> str:
    return f"{level}/{question_id}.md"


def _render_answer(result: EvalResult, provider_name: str, model: str) -> str:
    warnings = ", ".join(result.warnings) if result.warnings else "нет"
    return (
        f"# {result.level} · {result.question_id}\n\n"
        f"**Вопрос:** {result.question}\n\n"
        f"**Провайдер:** {provider_name} ({model}) · "
        f"**Версия промпта:** {result.prompt_version}\n\n"
        f"**Предупреждения политики:** {warnings}\n\n"
        f"## Ответ\n\n{result.answer}\n"
    )


def render_summary(results: list[EvalResult], provider_name: str, model: str) -> str:
    """Сводная таблица прогона для отчёта"""
    lines = [
        "# LLM_EVAL — сводка прогона",
        "",
        f"**Провайдер:** {provider_name} ({model})",
        f"**Ответов:** {len(results)}",
        "",
        "| Уровень | Вопрос | Символов | Предупреждения |",
        "|---------|--------|----------|----------------|",
    ]
    for result in results:
        warnings = ", ".join(result.warnings) if result.warnings else "—"
        lines.append(
            f"| {result.level} | {result.question_id} | {len(result.answer)} | {warnings} |"
        )
    lines.extend(
        [
            "",
            "Оценка по рубрике (0–5) — вручную по docs/LLM_EVAL.md §3;",
            "автоматически проверяется только политика уровня.",
            "",
        ]
    )
    return "\n".join(lines)


async def run_eval(
    provider: LLMProvider,
    output_dir: Path,
    *,
    levels: tuple[str, ...] = LEVELS,
    questions: tuple[tuple[str, str], ...] = EVAL_QUESTIONS,
) -> list[EvalResult]:
    """Сгенерировать ответы и сохранить их вместе со сводкой"""
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[EvalResult] = []

    for level in levels:
        for question_id, question in questions:
            messages: list[LLMMessage] = build_messages(level, [], question)
            answer = await provider.generate(messages)
            warnings = detect_level_policy_violations(level, answer)
            path = output_dir / _slug(level, question_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            result = EvalResult(
                level=level,
                question_id=question_id,
                question=question,
                answer=answer,
                warnings=warnings,
                prompt_version=prompt_version(level),
                output_path=path,
            )
            path.write_text(
                _render_answer(result, provider.name, provider.model), encoding="utf-8"
            )
            results.append(result)

    summary = render_summary(results, provider.name, provider.model)
    (output_dir / "SUMMARY.md").write_text(summary, encoding="utf-8")
    (output_dir / "results.json").write_text(
        json.dumps(
            [
                {
                    "level": result.level,
                    "question_id": result.question_id,
                    "warnings": result.warnings,
                    "prompt_version": result.prompt_version,
                }
                for result in results
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return results


def default_output_dir(day: date | None = None) -> Path:
    """Каталог отчёта: `docs/reports/llm-eval/<date>/` от корня проекта"""
    project_root = Path(__file__).resolve().parents[3]
    stamp = (day or date.today()).isoformat()
    return project_root / "docs" / "reports" / "llm-eval" / stamp


def provider_status(provider: LLMProvider) -> dict[str, Any]:
    """Краткое описание провайдера для CLI"""
    return {
        "name": provider.name,
        "model": provider.model,
        "configured": provider.is_configured(),
        "fallback": provider.fallback_name or None,
    }

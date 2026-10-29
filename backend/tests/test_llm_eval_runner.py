"""
Тесты прогонщика LLM_EVAL (S12-004).

Реальный прогон требует ключа/локальной модели, поэтому проверяем
инфраструктуру на детерминированном провайдере `echo`.
"""

from datetime import date
from pathlib import Path

from app.services.llm.echo import EchoProvider
from app.services.llm.eval_runner import (
    EVAL_QUESTIONS,
    LEVELS,
    default_output_dir,
    provider_status,
    run_eval,
)


async def test_run_eval_writes_all_answers_and_summary(tmp_path: Path) -> None:
    results = await run_eval(EchoProvider(), tmp_path)

    assert len(results) == len(LEVELS) * len(EVAL_QUESTIONS) == 15
    for level in LEVELS:
        for question_id, _ in EVAL_QUESTIONS:
            path = tmp_path / level / f"{question_id}.md"
            assert path.is_file(), path
            assert "## Ответ" in path.read_text(encoding="utf-8")

    summary = (tmp_path / "SUMMARY.md").read_text(encoding="utf-8")
    assert "# LLM_EVAL" in summary
    assert "| basic | Q1 |" in summary
    assert (tmp_path / "results.json").is_file()


async def test_run_eval_records_prompt_version(tmp_path: Path) -> None:
    from app.services.llm.prompt_builder import prompt_version

    results = await run_eval(EchoProvider(), tmp_path)
    expected = {prompt_version(level) for level in LEVELS}

    assert {result.prompt_version for result in results} == expected
    assert all(result.answer.strip() for result in results)


def test_default_output_dir_uses_date() -> None:
    path = default_output_dir(date(2026, 10, 29))

    assert str(path).replace("\\", "/").endswith("docs/reports/llm-eval/2026-10-29")


def test_provider_status_reports_configuration() -> None:
    status = provider_status(EchoProvider())

    assert status == {
        "name": "echo",
        "model": "echo",
        "configured": True,
        "fallback": None,
    }

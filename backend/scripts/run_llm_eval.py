"""
CLI прогона LLM_EVAL (S12-004).

Запуск из `backend/`:

    python scripts/run_llm_eval.py --provider deepseek
    python scripts/run_llm_eval.py --provider echo --out ../tmp/eval-smoke

Для реального прогона нужен `DEEPSEEK_API_KEY` (или запущенный LM Studio).
Без настроенного провайдера скрипт завершается с кодом 2 и ничего не пишет.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Разрешаем импорт пакета app при запуске из backend/scripts
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.llm import create_llm_provider  # noqa: E402
from app.services.llm.eval_runner import (  # noqa: E402
    default_output_dir,
    provider_status,
    run_eval,
)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Прогон LLM_EVAL (Q1–Q5 × 3 уровня)")
    parser.add_argument(
        "--provider",
        default=None,
        help="deepseek | lm_studio | echo (по умолчанию LLM_PROVIDER)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="каталог отчёта (по умолчанию docs/reports/llm-eval/<date>)",
    )
    args = parser.parse_args()

    provider = create_llm_provider(args.provider)
    status = provider_status(provider)
    if not status["configured"]:
        print(
            f"Провайдер {status['name']} не настроен: задайте DEEPSEEK_API_KEY "
            "или запустите LM Studio. Прогон не выполнен."
        )
        await provider.close()
        return 2

    output_dir = args.out or default_output_dir()
    try:
        results = await run_eval(provider, output_dir)
    finally:
        await provider.close()

    warnings = sum(1 for result in results if result.warnings)
    print(
        f"Готово: {len(results)} ответов, предупреждений политики — {warnings}. "
        f"Каталог: {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

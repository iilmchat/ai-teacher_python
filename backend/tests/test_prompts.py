"""
Тесты промптов и сборки контекста (S4-003, S5-001).

Проверяем, что промпт каждого уровня существует, содержит обязательные
маркеры образовательной политики и корректно собирается в список сообщений.
"""

import pytest

from app.models.user import UserLevel
from app.services.chat_service import extract_code_blocks, parse_level
from app.services.llm import create_llm_provider
from app.services.llm.base import LLMError, LLMMessage
from app.services.llm.prompt_builder import (
    MAX_CONTEXT_MESSAGES,
    PromptError,
    available_levels,
    build_messages,
    load_prompt_versions,
    load_system_prompt,
    prompt_version,
)


@pytest.mark.parametrize("level", [UserLevel.BASIC, UserLevel.INTERMEDIATE, UserLevel.ADVANCED])
def test_prompt_file_exists_and_not_empty(level: UserLevel) -> None:
    """У каждого уровня есть непустой промпт"""
    prompt = load_system_prompt(level)

    assert len(prompt) > 100
    assert "Python" in prompt


def test_basic_prompt_forbids_ready_solution() -> None:
    """Базовый уровень запрещает готовые решения"""
    prompt = load_system_prompt(UserLevel.BASIC)
    lowered = prompt.lower()

    assert "не давай готовый код" in lowered
    assert "наводящие вопросы" in lowered


def test_intermediate_prompt_allows_partial_examples() -> None:
    """Средний уровень показывает синтаксис, но не решение целиком"""
    prompt = load_system_prompt(UserLevel.INTERMEDIATE).lower()

    assert "синтаксис" in prompt
    assert "не выдавать полное решение" in prompt or "не выдавать" in prompt
    # Уточнение после живого прогона (intermediate v2):
    assert "других данных" in prompt
    assert "каркас" in prompt


def test_advanced_prompt_requires_full_solution() -> None:
    """Продвинутый уровень требует полное решение с разбором"""
    prompt = load_system_prompt(UserLevel.ADVANCED).lower()

    assert "полное решение" in prompt
    assert "альтернати" in prompt


def test_available_levels_cover_all_levels() -> None:
    """Файлы есть для всех трёх уровней"""
    assert set(available_levels()) == {
        UserLevel.BASIC,
        UserLevel.INTERMEDIATE,
        UserLevel.ADVANCED,
    }


def test_unknown_level_raises_prompt_error() -> None:
    """Неизвестный уровень — доменная ошибка"""
    with pytest.raises(PromptError):
        load_system_prompt("unknown")


def test_build_messages_puts_system_prompt_first() -> None:
    """Первое сообщение — системный промпт уровня"""
    messages = build_messages(UserLevel.BASIC, [], "привет")

    assert messages[0].role == "system"
    assert messages[0].content == load_system_prompt(UserLevel.BASIC)
    assert messages[-1] == LLMMessage(role="user", content="привет")


def test_build_messages_truncates_long_history() -> None:
    """В контекст попадают только последние MAX_CONTEXT_MESSAGES сообщений"""
    history = [LLMMessage(role="user", content=f"msg-{i}") for i in range(50)]

    messages = build_messages(UserLevel.BASIC, history, "текущий")

    # system + MAX_CONTEXT_MESSAGES истории + текущее сообщение
    assert len(messages) == MAX_CONTEXT_MESSAGES + 2
    assert messages[1].content == "msg-30"
    assert messages[-1].content == "текущий"


def test_build_messages_puts_task_context_after_level_prompt() -> None:
    """Контекст задачи — второе системное сообщение (S42-006)"""
    messages = build_messages(
        UserLevel.BASIC,
        [("user", "прошлый вопрос"), ("assistant", "прошлый ответ")],
        "текущий вопрос",
        task_context="Контекст задачи: сумма двух чисел",
    )

    assert [m.role for m in messages] == [
        "system",
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert messages[1].content == "Контекст задачи: сумма двух чисел"
    assert messages[-1].content == "текущий вопрос"


def test_build_messages_without_task_context_is_unchanged() -> None:
    """Без контекста задачи список сообщений прежний (S42-006)"""
    messages = build_messages(UserLevel.BASIC, [], "привет")

    assert [m.role for m in messages] == ["system", "user"]


def test_build_messages_accepts_role_content_tuples() -> None:
    """История может быть передана парами (role, content)"""
    messages = build_messages(
        "basic", [("user", "вопрос"), ("assistant", "ответ")], "новый"
    )

    assert [m.role for m in messages] == ["system", "user", "assistant", "user"]


def test_extract_code_blocks() -> None:
    """Из ответа извлекаются блоки кода"""
    text = "Текст\n```python\nprint('a')\n```\nЕщё\n```\nx = 1\n```"

    assert extract_code_blocks(text) == ["print('a')", "x = 1"]


def test_extract_code_blocks_empty_when_none() -> None:
    """Нет блоков — пустой список"""
    assert extract_code_blocks("просто текст") == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("basic", UserLevel.BASIC),
        ("intermediate", UserLevel.INTERMEDIATE),
        ("advanced", UserLevel.ADVANCED),
        (UserLevel.ADVANCED, UserLevel.ADVANCED),
    ],
)
def test_parse_level_accepts_valid_values(value: object, expected: UserLevel) -> None:
    """Валидные уровни нормализуются"""
    assert parse_level(value) == expected  # type: ignore[arg-type]


def test_parse_level_rejects_unknown() -> None:
    """Неизвестный уровень отклоняется"""
    with pytest.raises(Exception) as exc_info:
        parse_level("guru")
    assert "guru" in str(exc_info.value)


def test_create_llm_provider_unknown_name() -> None:
    """Неизвестный провайдер — LLMError"""
    with pytest.raises(LLMError):
        create_llm_provider("unknown-provider")


def test_create_llm_provider_deepseek() -> None:
    """Провайдер deepseek создаётся по имени"""
    provider = create_llm_provider("deepseek")
    assert provider.name == "deepseek"


def test_create_llm_provider_lm_studio() -> None:
    """Провайдер lm_studio создаётся по имени и берёт модель из настроек"""
    from app.config import settings

    provider = create_llm_provider("lm_studio")
    assert provider.name == "lm_studio"
    assert provider.model == settings.lm_studio_model


def test_prompt_versions_cover_all_levels() -> None:
    """versions.json содержит версию для каждого уровня"""
    versions = load_prompt_versions()

    assert set(versions) == {level.value for level in UserLevel}
    assert all(isinstance(value, int) and value >= 1 for value in versions.values())


def test_prompt_version_matches_file() -> None:
    """Версия из файла доступна через API prompt_builder"""
    versions = load_prompt_versions()

    assert prompt_version(UserLevel.BASIC) == versions["basic"]
    assert prompt_version("advanced") == versions["advanced"]


def test_prompt_version_defaults_to_one_for_unknown_level() -> None:
    """Для неизвестного уровня не падаем, а считаем версию первой"""
    assert prompt_version("unknown") == 1


def test_create_llm_provider_with_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Настроенный fallback оборачивает основной провайдер"""
    from app.config import settings
    from app.services.llm.fallback import FallbackProvider

    monkeypatch.setattr(settings, "llm_provider", "echo")
    monkeypatch.setattr(settings, "llm_fallback_provider", "lm_studio")

    provider = create_llm_provider()

    assert isinstance(provider, FallbackProvider)
    assert provider.name == "echo"
    assert provider.fallback_name == "lm_studio"

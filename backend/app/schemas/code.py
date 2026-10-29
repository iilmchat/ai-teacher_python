"""
Pydantic schemas для выполнения кода (S6-004, S6-005).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

#: Максимальная длина принимаемого кода (символов)
MAX_CODE_LENGTH = 20_000


class CodeRequest(BaseModel):
    """Код на выполнение/анализ"""

    code: str = Field(..., min_length=1, max_length=MAX_CODE_LENGTH)
    #: Данные для input() — по строке на вызов
    stdin: str | None = Field(default=None, max_length=10_000)


class ExecutionResponse(BaseModel):
    """Результат выполнения кода"""

    success: bool
    output: str = ""
    error: str | None = None
    error_type: str | None = None
    execution_time: float = 0.0
    violations: list[str] = Field(default_factory=list)
    #: Удалось ли применить лимит памяти (S13-001, S13-002)
    memory_limit_enforced: bool = False
    #: Вывод был обрезан по лимиту (S13-005)
    output_truncated: bool = False


class ExecutionRecordResponse(BaseModel):
    """Сохранённая запись о выполнении"""

    id: UUID
    code: str
    output: str
    error: str | None
    success: bool
    execution_time: float
    created_at: datetime

    model_config = {"from_attributes": True}


class LintIssueSchema(BaseModel):
    """Замечание линтера"""

    line: int
    column: int
    code: str
    message: str
    severity: str


class LintResponse(BaseModel):
    """Результат линтинга"""

    issues: list[LintIssueSchema]
    errors: int
    warnings: int
    infos: int


class AnalyzeResponse(BaseModel):
    """Результат анализа кода: замечания + метрики"""

    issues: list[LintIssueSchema]
    stats: dict[str, int]
    summary: str

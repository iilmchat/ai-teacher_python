"""
Сервис задач и прогресса обучения (S7-003, S7-006).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.executor import SandboxedExecutor
from app.core.test_runner import CaseRunOutcome, run_test_cases
from app.db.repositories.task import (
    ProgressRepository,
    TaskAttemptRepository,
    TaskRepository,
    TaskVersionRepository,
)
from app.errors import NotFoundError, ValidationError
from app.models.task import (
    AttemptFeedback,
    Task,
    TaskAttempt,
    TaskDifficulty,
    TaskStatus,
    TaskVersion,
    UserTaskProgress,
)
from app.models.user import User
from app.schemas.task import (
    AttemptDetail,
    AttemptFeedbackItem,
    AttemptItem,
    AttemptList,
    DraftStatus,
    ProgressItem,
    ProgressSummary,
    RecommendedTask,
    RecommendedTaskList,
    SubmitResponse,
    TaskCreate,
    TaskDetail,
    TaskListItem,
    TaskStatsResponse,
    TaskUpdate,
    TaskVersionItem,
    TestCaseResult,
)
from app.services.cache import invalidate_tasks_cache

#: Порядок сложности: easy -> medium -> hard.
_DIFFICULTY_ORDER: dict[TaskDifficulty, int] = {
    TaskDifficulty.EASY: 0,
    TaskDifficulty.MEDIUM: 1,
    TaskDifficulty.HARD: 2,
}


def _difficulty_rank(task: Task | None) -> int:
    """Ранг сложности задачи (0 — самая простая)."""
    if task is None:
        return -1
    return _DIFFICULTY_ORDER.get(task.difficulty, 0)


class TaskService:
    """Бизнес-логика задач"""

    def __init__(self, db: AsyncSession, executor: SandboxedExecutor) -> None:
        self.db = db
        self.executor = executor
        self.tasks = TaskRepository(db)
        self.progress = ProgressRepository(db)
        self.attempts = TaskAttemptRepository(db)
        self.versions = TaskVersionRepository(db)

    # --- Чтение ---------------------------------------------------------

    async def list_tasks(
        self,
        user: User,
        *,
        difficulty: TaskDifficulty | None = None,
        category: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        status: TaskStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TaskListItem]:
        """Список активных задач со статусом прохождения.

        `status` фильтрует по прогрессу самого ученика: без
        записи прогресса задача считается «не начата».
        """
        tasks = await self.tasks.list_tasks(
            difficulty=difficulty,
            category=category,
            tag=tag,
            search=search,
            user_id=user.id,
            status=status,
            skip=skip,
            limit=limit,
        )
        progress_map = await self.progress.get_user_progress_map(user.id)

        items: list[TaskListItem] = []
        for task in tasks:
            record = progress_map.get(task.id)
            items.append(
                TaskListItem(
                    id=task.id,
                    title=task.title,
                    difficulty=task.difficulty,
                    category=task.category,
                    hints_count=len(task.hints or []),
                    status=record.status if record else TaskStatus.NOT_STARTED,
                    tags=list(task.tags or []),
                )
            )
        return items

    async def list_categories(self) -> list[str]:
        """Категории активных задач"""
        return await self.tasks.list_categories()

    async def recommended_tasks(
        self, user: User, limit: int = 5
    ) -> RecommendedTaskList:
        """Рекомендации следующих задач (S42-005).

        Правила (детерминированные, без случайности):

        1. Решенные задачи не рекомендуются.
        2. Сложность не выше, чем у последней решённой + одна ступень.
        3. Приоритет: начатые задачи, затем совпадение тегов с недавно
           решёнными, затем близость по сложности.
        4. Порядок одинаковых кандидатов — по дате создания, затем по id.

        Каждая рекомендация объясняет, почему она предложена.
        """
        progress_map = await self.progress.get_user_progress_map(user.id)
        candidates = await self.tasks.list_tasks(limit=1000)

        solved: list[tuple[Task, datetime]] = []
        for task in candidates:
            record = progress_map.get(task.id)
            if record is None:
                continue
            if record.status == TaskStatus.COMPLETED:
                solved.append((task, record.completed_at or record.updated_at))

        # Последняя решённая задача задаёт верхнюю границу сложности.
        solved.sort(key=lambda pair: (pair[1], pair[0].id))
        last_solved = solved[-1][0] if solved else None
        max_rank = _difficulty_rank(last_solved) + 1 if last_solved else 2

        # Теги недавно решённых задач — подсказка темы.
        recent_tags: set[str] = set()
        for task, _ in solved[-3:]:
            recent_tags.update(tag.lower() for tag in (task.tags or []))

        scored: list[tuple[tuple[int, int, float, str, UUID], RecommendedTask]] = []
        for task in candidates:
            record = progress_map.get(task.id)
            if record is not None and record.status == TaskStatus.COMPLETED:
                continue
            rank = _difficulty_rank(task)
            if rank > max_rank:
                continue

            overlap = recent_tags.intersection(
                tag.lower() for tag in (task.tags or [])
            )
            in_progress = record is not None

            if in_progress:
                reason = "continue"
                reason_text = "Вы уже начали эту задачу — продолжите с того места"
                priority = 0
            elif overlap:
                reason = "same_topic"
                reason_text = (
                    "Та же тема, что и в недавно решённых задачах"
                )
                priority = 1
            elif not solved:
                reason = "starter"
                reason_text = "С чего начать: простая задача по теме"
                priority = 2
            elif rank <= _difficulty_rank(last_solved):
                reason = "easier"
                reason_text = "Проще, чем последняя решённая задача"
                priority = 3
            else:
                reason = "next_step"
                reason_text = "Следующий шаг по сложности"
                priority = 4

            # Чем меньше значение, тем раньше рекомендация.
            sort_key = (
                priority,
                -len(overlap),
                float(rank),
                task.created_at.isoformat(),
                task.id,
            )
            scored.append(
                (
                    sort_key,
                    RecommendedTask(
                        id=task.id,
                        title=task.title,
                        difficulty=task.difficulty,
                        category=task.category,
                        tags=list(task.tags or []),
                        reason=reason,
                        reason_text=reason_text,
                    ),
                )
            )

        scored.sort(key=lambda pair: pair[0])
        items = [item for _, item in scored[:limit]]
        return RecommendedTaskList(items=items)
    async def _get_task_or_404(self, task_id: UUID) -> Task:
        task = await self.tasks.get(task_id)
        if task is None:
            raise NotFoundError("Задача не найдена")
        return task

    async def get_task_detail(self, task_id: UUID, user: User) -> TaskDetail:
        """Карточка задачи с прогрессом ученика"""
        task = await self._get_task_or_404(task_id)
        record = await self.progress.get_by_user_and_task(user.id, task.id)

        return TaskDetail(
            id=task.id,
            title=task.title,
            description=task.description,
            difficulty=task.difficulty,
            category=task.category,
            hints=list(task.hints or []),
            solution_template=task.solution_template,
            test_cases_count=len(task.test_cases or []),
            status=record.status if record else TaskStatus.NOT_STARTED,
            attempts=record.attempts if record else 0,
            tags=list(task.tags or []),
            draft_code=record.draft_code if record else None,
            draft_updated_at=record.draft_updated_at if record else None,
        )

    async def get_hint(self, task_id: UUID, index: int) -> tuple[str, int]:
        """Подсказка по номеру (с нуля) и общее число подсказок"""
        task = await self._get_task_or_404(task_id)
        hints = list(task.hints or [])
        if not hints:
            raise NotFoundError("У задачи нет подсказок")
        if index < 0 or index >= len(hints):
            raise ValidationError(f"Подсказка {index} не найдена (всего {len(hints)})")
        return str(hints[index]), len(hints)

    # --- Проверка решения ----------------------------------------------

    def _to_results(self, outcome: CaseRunOutcome) -> list[TestCaseResult]:
        return [
            TestCaseResult(
                index=item.index,
                passed=item.passed,
                description=item.description,
                input=item.input,
                expected_output=item.expected_output,
                actual_output=item.actual_output,
                error=item.error,
            )
            for item in outcome.results
        ]

    async def submit_solution(
        self, task_id: UUID, user: User, code: str
    ) -> SubmitResponse:
        """Проверить решение, обновить попытки и статус"""
        task = await self._get_task_or_404(task_id)
        outcome = await self._run_cases(task, code)

        record = await self.progress.get_by_user_and_task(user.id, task.id)
        if record is None:
            record = UserTaskProgress(
                user_id=user.id,
                task_id=task.id,
                status=TaskStatus.NOT_STARTED,
                attempts=0,
            )
            self.db.add(record)

        record.attempts += 1
        record.updated_at = datetime.utcnow()
        # Отправка засчитана — черновик больше не нужен (S42-003).
        record.draft_code = None
        record.draft_updated_at = None

        if outcome.passed:
            record.status = TaskStatus.COMPLETED
            record.completed_at = record.completed_at or datetime.utcnow()
            if record.best_solution is None:
                record.best_solution = code
        elif record.status == TaskStatus.NOT_STARTED:
            record.status = TaskStatus.IN_PROGRESS

        # История попыток (S42-002): каждая засчитанная отправка попадает
        # в журнал с кодом и разбором по кейсам.
        self.db.add(
            TaskAttempt(
                user_id=user.id,
                task_id=task.id,
                code=code,
                passed=outcome.passed,
                passed_count=outcome.passed_count,
                total_count=outcome.total_count,
                results=[item.model_dump() for item in self._to_results(outcome)],
            )
        )

        await self.db.commit()
        await self.db.refresh(record)

        if outcome.passed:
            # Достижения не должны ломать выдачу результата ученику
            try:
                from app.services.engagement_service import evaluate_achievements

                await evaluate_achievements(self.db, user.id)
            except Exception:  # noqa: BLE001
                import structlog

                structlog.get_logger(__name__).warning(
                    "achievement_evaluation_failed", user_id=str(user.id)
                )

        return SubmitResponse(
            passed=outcome.passed,
            passed_count=outcome.passed_count,
            total_count=outcome.total_count,
            attempts=record.attempts,
            status=record.status,
            results=self._to_results(outcome),
            message=self._build_message(outcome),
            practice=False,
        )

    async def check_solution(
        self, task_id: UUID, user: User, code: str
    ) -> SubmitResponse:
        """Пробная проверка (S42-001): попытка не засчитывается.

        Отличается от `submit_solution` только учётом прогресса: счётчик
        попыток и статус задачи не меняются, достижения не начисляются.
        Результат тот же — ученик видит тот же разбор по тест-кейсам.
        """
        task = await self._get_task_or_404(task_id)
        outcome = await self._run_cases(task, code)

        record = await self.progress.get_by_user_and_task(user.id, task.id)
        attempts = record.attempts if record else 0
        status = record.status if record else TaskStatus.NOT_STARTED

        return SubmitResponse(
            passed=outcome.passed,
            passed_count=outcome.passed_count,
            total_count=outcome.total_count,
            attempts=attempts,
            status=status,
            results=self._to_results(outcome),
            message=self._build_message(outcome, practice=True),
            practice=True,
        )

    async def _feedback_map(
        self, attempt_ids: list[UUID]
    ) -> dict[UUID, list[AttemptFeedbackItem]]:
        """Комментарии учителей для набора попыток (S46-002).

        Один запрос на страницу истории: иначе на каждую попытку уходил бы
        отдельный round-trip. Комментарии внутри попытки — новые сверху.
        """
        if not attempt_ids:
            return {}
        rows = await self.db.execute(
            select(AttemptFeedback, User.username)
            .join(User, User.id == AttemptFeedback.teacher_id)
            .where(AttemptFeedback.attempt_id.in_(attempt_ids))
            .order_by(AttemptFeedback.created_at.desc())
        )
        mapping: dict[UUID, list[AttemptFeedbackItem]] = {}
        for feedback, teacher_name in rows.all():
            mapping.setdefault(feedback.attempt_id, []).append(
                AttemptFeedbackItem(
                    id=feedback.id,
                    comment=feedback.comment,
                    teacher_name=teacher_name,
                    created_at=feedback.created_at,
                )
            )
        return mapping

    async def list_attempts(
        self, task_id: UUID, user: User, skip: int = 0, limit: int = 20
    ) -> AttemptList:
        """История попыток ученика по задаче (S42-002), новые сверху

        С S46-002 к каждой попытке прикладываются комментарии учителей:
        ученик видит разбор прямо в истории.
        """
        await self._get_task_or_404(task_id)
        items = await self.attempts.list_for_user_and_task(
            user.id, task_id, skip=skip, limit=limit
        )
        total = await self.attempts.count_for_user_and_task(user.id, task_id)
        feedback = await self._feedback_map([item.id for item in items])
        return AttemptList(
            items=[
                AttemptItem(
                    id=item.id,
                    task_id=item.task_id,
                    passed=item.passed,
                    passed_count=item.passed_count,
                    total_count=item.total_count,
                    created_at=item.created_at,
                    feedback=feedback.get(item.id, []),
                )
                for item in items
            ],
            total=total,
        )

    async def get_attempt(
        self, task_id: UUID, attempt_id: UUID, user: User
    ) -> AttemptDetail:
        """Детальная попытка с кодом и разбором по кейсам.

        Попытка принадлежит ученику: чужая недоступна (404), чтобы по
        идентификатору нельзя было проверить существование чужой записи.
        """
        await self._get_task_or_404(task_id)
        attempt = await self.attempts.get(attempt_id)
        if (
            attempt is None
            or attempt.task_id != task_id
            or attempt.user_id != user.id
        ):
            raise NotFoundError("Попытка не найдена")

        results = [TestCaseResult(**item) for item in (attempt.results or [])]
        feedback = await self._feedback_map([attempt.id])
        return AttemptDetail(
            id=attempt.id,
            task_id=attempt.task_id,
            passed=attempt.passed,
            passed_count=attempt.passed_count,
            total_count=attempt.total_count,
            created_at=attempt.created_at,
            code=attempt.code,
            results=results,
            feedback=feedback.get(attempt.id, []),
        )

    async def save_draft(
        self, task_id: UUID, user: User, code: str
    ) -> DraftStatus:
        """Сохранить черновик решения (S42-003).

        Черновик не является решением: счётчик попыток и статус задачи
        не меняются, в историю попыток запись не попадает. Пустой код
        удаляет черновик.
        """
        task = await self._get_task_or_404(task_id)

        record = await self.progress.get_by_user_and_task(user.id, task.id)
        if record is None:
            record = UserTaskProgress(
                user_id=user.id,
                task_id=task.id,
                status=TaskStatus.NOT_STARTED,
                attempts=0,
            )
            self.db.add(record)

        if not code.strip():
            record.draft_code = None
            record.draft_updated_at = None
        else:
            record.draft_code = code
            record.draft_updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(record)

        return DraftStatus(
            has_draft=record.draft_code is not None,
            updated_at=record.draft_updated_at,
        )

    async def clear_draft(self, task_id: UUID, user: User) -> DraftStatus:
        """Очистить черновик решения (S42-003)."""
        await self._get_task_or_404(task_id)

        record = await self.progress.get_by_user_and_task(user.id, task_id)
        if record is None:
            return DraftStatus(has_draft=False, updated_at=None)

        record.draft_code = None
        record.draft_updated_at = None
        await self.db.commit()

        return DraftStatus(has_draft=False, updated_at=None)

    async def _run_cases(self, task: Task, code: str) -> CaseRunOutcome:
        """Прогнать код по тест-кейсам задачи"""
        if not task.test_cases:
            raise ValidationError("У задачи нет тест-кейсов для проверки")
        return await run_test_cases(self.executor, code, list(task.test_cases))

    @staticmethod
    def _build_message(outcome: CaseRunOutcome, *, practice: bool = False) -> str:
        """Человекочитаемый итог проверки"""
        if outcome.passed:
            message = (
                "Задача решена! Все тесты пройдены "
                f"({outcome.passed_count}/{outcome.total_count})."
            )
        elif outcome.violations:
            message = "Код нарушает правила песочницы: " + "; ".join(outcome.violations)
        else:
            message = (
                f"Пройдено {outcome.passed_count} из {outcome.total_count} тестов. "
                "Посмотрите, на каком вводе расходится вывод."
            )
        if practice:
            return f"{message} Пробная проверка — попытка не засчитывается."
        return message

    # --- Прогресс -------------------------------------------------------

    async def get_progress(self, user: User) -> ProgressSummary:
        """Сводка прогресса ученика по всем активным задачам"""
        tasks = await self.tasks.list_tasks(limit=1000)
        progress_map = await self.progress.get_user_progress_map(user.id)

        items: list[ProgressItem] = []
        completed = in_progress = not_started = 0
        by_difficulty: dict[str, dict[str, int]] = {
            difficulty.value: {"total": 0, "completed": 0}
            for difficulty in TaskDifficulty
        }

        for task in tasks:
            record = progress_map.get(task.id)
            status = record.status if record else TaskStatus.NOT_STARTED

            if status == TaskStatus.COMPLETED:
                completed += 1
            elif status == TaskStatus.IN_PROGRESS:
                in_progress += 1
            else:
                not_started += 1

            bucket = by_difficulty[task.difficulty.value]
            bucket["total"] += 1
            if status == TaskStatus.COMPLETED:
                bucket["completed"] += 1

            items.append(
                ProgressItem(
                    task_id=task.id,
                    title=task.title,
                    difficulty=task.difficulty,
                    status=status,
                    attempts=record.attempts if record else 0,
                    completed_at=record.completed_at if record else None,
                )
            )

        total = len(tasks)
        completion_rate = round(completed / total * 100, 1) if total else 0.0

        return ProgressSummary(
            total_tasks=total,
            completed=completed,
            in_progress=in_progress,
            not_started=not_started,
            completion_rate=completion_rate,
            by_difficulty=by_difficulty,
            items=items,
        )

    async def get_stats(self, user: User) -> TaskStatsResponse:
        """Статистика задач и активности ученика"""
        by_difficulty = await self.tasks.count_by_difficulty()
        by_category = await self.tasks.count_by_category()
        progress_items = await self.progress.get_user_progress(user.id)

        return TaskStatsResponse(
            total_tasks=sum(by_difficulty.values()),
            by_difficulty=by_difficulty,
            by_category=by_category,
            total_attempts=sum(item.attempts for item in progress_items),
            total_completions=sum(
                1 for item in progress_items if item.status == TaskStatus.COMPLETED
            ),
        )

    # --- Управление (преподаватель/админ) -------------------------------

    @staticmethod
    def _snapshot(task: Task) -> dict[str, object]:
        """Полный снимок задачи для истории версий"""
        return {
            "title": task.title,
            "description": task.description,
            "difficulty": task.difficulty.value,
            "category": task.category,
            "tags": list(task.tags or []),
            "test_cases": list(task.test_cases or []),
            "hints": list(task.hints or []),
            "solution_template": task.solution_template,
            "is_active": task.is_active,
        }

    async def _save_version(self, task: Task, author: User | None) -> None:
        """Сохранить текущее состояние задачи как новую версию"""
        next_version = await self.versions.latest_version(task.id) + 1
        await self.versions.create(
            TaskVersion(
                task_id=task.id,
                version=next_version,
                snapshot=self._snapshot(task),
                created_by=author.id if author is not None else None,
            )
        )

    async def create_task(
        self,
        payload: TaskCreate,
        author: User,
        *,
        invalidate_cache: bool = True,
    ) -> Task:
        """Создать задачу (S19-003: сбрасывает кэш каталога и категорий)"""
        task = Task(
            title=payload.title,
            description=payload.description,
            difficulty=payload.difficulty,
            category=payload.category,
            tags=list(payload.tags),
            test_cases=[case.model_dump() for case in payload.test_cases],
            hints=list(payload.hints),
            solution_template=payload.solution_template,
            created_by=author.id,
        )
        created = await self.tasks.create(task)
        if invalidate_cache:
            await invalidate_tasks_cache()
        return created

    async def create_many(
        self, payloads: list[TaskCreate], author: User
    ) -> list[Task]:
        """Создать несколько задач (генерация/массовый импорт)"""
        created: list[Task] = []
        for payload in payloads:
            created.append(
                await self.create_task(payload, author, invalidate_cache=False)
            )
        if created:
            await invalidate_tasks_cache()
        return created

    async def export_active(self) -> list[Task]:
        """Все активные задачи для выгрузки"""
        return await self.tasks.list_tasks(limit=1000)

    async def update_task(
        self, task_id: UUID, payload: TaskUpdate, author: User | None = None
    ) -> Task:
        """Обновить задачу, сохранив предыдущее состояние в истории"""
        task = await self._get_task_or_404(task_id)
        data = payload.model_dump(exclude_unset=True)

        if not data:
            return task

        if "test_cases" in data and data["test_cases"] is not None:
            data["test_cases"] = [
                case.model_dump() if hasattr(case, "model_dump") else case
                for case in payload.test_cases or []
            ]

        # Снимок делаем до мутации, иначе история потеряет старое состояние
        await self._save_version(task, author)

        for field_name, value in data.items():
            setattr(task, field_name, value)

        await self.db.commit()
        await self.db.refresh(task)
        await invalidate_tasks_cache()
        return task

    async def list_versions(self, task_id: UUID) -> list[TaskVersionItem]:
        """История версий задачи (новые сверху)"""
        await self._get_task_or_404(task_id)
        versions = await self.versions.list_for_task(task_id)
        items: list[TaskVersionItem] = []
        for version in versions:
            snapshot = dict(version.snapshot or {})
            test_cases = snapshot.get("test_cases") or []
            items.append(
                TaskVersionItem(
                    id=version.id,
                    version=version.version,
                    title=str(snapshot.get("title", "")),
                    test_cases_count=len(test_cases)
                    if isinstance(test_cases, list)
                    else 0,
                    solution_template=snapshot.get("solution_template"),
                    created_at=version.created_at,
                )
            )
        return items

    async def restore_version(
        self, task_id: UUID, version: int, author: User | None = None
    ) -> Task:
        """Откатить задачу к версии (текущее состояние тоже сохраняется)"""
        task = await self._get_task_or_404(task_id)
        target = await self.versions.get_by_version(task_id, version)
        if target is None:
            raise NotFoundError(f"Версия {version} не найдена")
        snapshot = dict(target.snapshot or {})

        await self._save_version(task, author)

        task.title = str(snapshot.get("title", task.title))
        task.description = str(snapshot.get("description", task.description))
        try:
            task.difficulty = TaskDifficulty(str(snapshot.get("difficulty")))
        except ValueError:
            task.difficulty = task.difficulty
        task.category = str(snapshot.get("category", task.category))
        task.tags = list(snapshot.get("tags") or [])
        task.test_cases = list(snapshot.get("test_cases") or [])
        task.hints = list(snapshot.get("hints") or [])
        task.solution_template = snapshot.get("solution_template")
        task.is_active = bool(snapshot.get("is_active", True))

        await self.db.commit()
        await self.db.refresh(task)
        await invalidate_tasks_cache()
        return task

    async def delete_task(self, task_id: UUID) -> None:
        """Удалить задачу (мягко: деактивировать, если есть прогресс)"""
        await self._get_task_or_404(task_id)
        # Проверяем прогресс отдельным запросом: lazy-relationship
        # `task.progress` в async-сессии даёт MissingGreenlet
        if await self.progress.exists_for_task(task_id):
            task = await self._get_task_or_404(task_id)
            task.is_active = False
            await self.db.commit()
            await invalidate_tasks_cache()
            return
        await self.tasks.delete(task_id)
        await invalidate_tasks_cache()

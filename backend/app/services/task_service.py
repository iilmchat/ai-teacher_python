"""
Сервис задач и прогресса обучения (S7-003, S7-006).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.executor import SandboxedExecutor
from app.core.test_runner import CaseRunOutcome, run_test_cases
from app.db.repositories.task import (
    ProgressRepository,
    TaskRepository,
    TaskVersionRepository,
)
from app.errors import NotFoundError, ValidationError
from app.models.task import (
    Task,
    TaskDifficulty,
    TaskStatus,
    TaskVersion,
    UserTaskProgress,
)
from app.models.user import User
from app.schemas.task import (
    ProgressItem,
    ProgressSummary,
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


class TaskService:
    """Бизнес-логика задач"""

    def __init__(self, db: AsyncSession, executor: SandboxedExecutor) -> None:
        self.db = db
        self.executor = executor
        self.tasks = TaskRepository(db)
        self.progress = ProgressRepository(db)
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
        skip: int = 0,
        limit: int = 100,
    ) -> list[TaskListItem]:
        """Список активных задач со статусом прохождения"""
        tasks = await self.tasks.list_tasks(
            difficulty=difficulty,
            category=category,
            tag=tag,
            search=search,
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
        if not task.test_cases:
            raise ValidationError("У задачи нет тест-кейсов для проверки")

        outcome = await run_test_cases(self.executor, code, list(task.test_cases))

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

        if outcome.passed:
            record.status = TaskStatus.COMPLETED
            record.completed_at = record.completed_at or datetime.utcnow()
            if record.best_solution is None:
                record.best_solution = code
        elif record.status == TaskStatus.NOT_STARTED:
            record.status = TaskStatus.IN_PROGRESS

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

        return SubmitResponse(
            passed=outcome.passed,
            passed_count=outcome.passed_count,
            total_count=outcome.total_count,
            attempts=record.attempts,
            status=record.status,
            results=self._to_results(outcome),
            message=message,
        )

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

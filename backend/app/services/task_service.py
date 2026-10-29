"""
Сервис задач и прогресса обучения (S7-003, S7-006).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.executor import SandboxedExecutor
from app.core.test_runner import CaseRunOutcome, run_test_cases
from app.db.repositories.task import ProgressRepository, TaskRepository
from app.errors import NotFoundError, ValidationError
from app.models.task import (
    Task,
    TaskDifficulty,
    TaskStatus,
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
    TestCaseResult,
)


class TaskService:
    """Бизнес-логика задач"""

    def __init__(self, db: AsyncSession, executor: SandboxedExecutor) -> None:
        self.db = db
        self.executor = executor
        self.tasks = TaskRepository(db)
        self.progress = ProgressRepository(db)

    # --- Чтение ---------------------------------------------------------

    async def list_tasks(
        self,
        user: User,
        *,
        difficulty: TaskDifficulty | None = None,
        category: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TaskListItem]:
        """Список активных задач со статусом прохождения"""
        tasks = await self.tasks.list_tasks(
            difficulty=difficulty,
            category=category,
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
                )
            )
        return items

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

    async def create_task(self, payload: TaskCreate, author: User) -> Task:
        """Создать задачу"""
        task = Task(
            title=payload.title,
            description=payload.description,
            difficulty=payload.difficulty,
            category=payload.category,
            test_cases=[case.model_dump() for case in payload.test_cases],
            hints=list(payload.hints),
            solution_template=payload.solution_template,
            created_by=author.id,
        )
        return await self.tasks.create(task)

    async def update_task(self, task_id: UUID, payload: TaskUpdate) -> Task:
        """Обновить задачу"""
        task = await self._get_task_or_404(task_id)
        data = payload.model_dump(exclude_unset=True)

        if "test_cases" in data and data["test_cases"] is not None:
            data["test_cases"] = [
                case.model_dump() if hasattr(case, "model_dump") else case
                for case in payload.test_cases or []
            ]

        for field_name, value in data.items():
            setattr(task, field_name, value)

        await self.db.commit()
        await self.db.refresh(task)
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
            return
        await self.tasks.delete(task_id)

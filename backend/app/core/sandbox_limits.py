"""
Ограничения ресурсов песочницы (S13-001, S13-002, S13-005).

Лимит памяти ставится внутри дочернего интерпретатора, а не в родителе:
так его нельзя «потерять» между spawn и первым выделением памяти, и он не
затрагивает процесс API.

- POSIX: `resource.setrlimit(RLIMIT_AS)`.
- Windows: Job Object с `JOB_OBJECT_LIMIT_PROCESS_MEMORY`; процесс назначает
  себя в job сам, поэтому гонки с запуском пользовательского кода нет.
"""

import sys
from typing import Any

#: Сколько символов stdout максимум отдаём клиенту
DEFAULT_MAX_OUTPUT_CHARS = 100_000

OUTPUT_TRUNCATED_NOTE = "\n… вывод обрезан: превышен лимит {limit} символов"

#: Флаг Job Object: ограничить committed memory процесса
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9

#: Держим handle job до конца жизни процесса, иначе job уничтожается
_WINDOWS_JOB: Any = None


def apply_memory_limit(limit_mb: int) -> tuple[bool, str | None]:
    """Применить лимит памяти к текущему процессу.

    Возвращает `(enforced, reason)`: `reason` заполняется, если лимит
    применить не удалось (тогда песочница продолжает работать с таймаутом).
    """
    if limit_mb <= 0:
        return False, "лимит памяти отключён (EXECUTOR_MEMORY_LIMIT=0)"
    limit_bytes = limit_mb * 1024 * 1024
    if sys.platform == "win32":
        return _apply_windows_memory_limit(limit_bytes)
    return _apply_posix_memory_limit(limit_bytes)


def _apply_posix_memory_limit(limit_bytes: int) -> tuple[bool, str | None]:
    """RLIMIT_AS на Linux/macOS"""
    try:
        import resource
    except ImportError as exc:  # pragma: no cover — экзотическая платформа
        return False, f"resource недоступен: {exc}"

    # mypy видит resource только с атрибутами текущей платформы (на Windows
    # их нет), поэтому работаем через Any — вызов всё равно только на POSIX.
    resource_any: Any = resource
    try:
        _, hard = resource_any.getrlimit(resource_any.RLIMIT_AS)
        new_hard = (
            limit_bytes
            if hard == resource_any.RLIM_INFINITY
            else min(int(hard), limit_bytes)
        )
        resource_any.setrlimit(resource_any.RLIMIT_AS, (new_hard, new_hard))
    except (OSError, ValueError) as exc:
        return False, f"setrlimit(RLIMIT_AS): {exc}"
    return True, None


def _apply_windows_memory_limit(limit_bytes: int) -> tuple[bool, str | None]:
    """Job Object с лимитом памяти процесса (Windows)"""
    global _WINDOWS_JOB
    if sys.platform != "win32":  # pragma: no cover — защита от прямого вызова
        return False, "Job Object доступен только на Windows"

    import ctypes
    from ctypes import wintypes

    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class _ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    win_dll = vars(ctypes)["WinDLL"]
    kernel32 = win_dll("kernel32", use_last_error=True)

    create_job = kernel32.CreateJobObjectW
    create_job.restype = wintypes.HANDLE
    create_job.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]

    set_info = kernel32.SetInformationJobObject
    set_info.restype = wintypes.BOOL
    set_info.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]

    assign = kernel32.AssignProcessToJobObject
    assign.restype = wintypes.BOOL
    assign.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

    get_current = kernel32.GetCurrentProcess
    get_current.restype = wintypes.HANDLE
    get_current.argtypes = []

    job = create_job(None, None)
    if not job:
        return False, f"CreateJobObject: {ctypes.WinError(ctypes.get_last_error())}"

    info = _ExtendedLimitInformation()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY
    info.ProcessMemoryLimit = limit_bytes
    if not set_info(
        job,
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        error = ctypes.WinError(ctypes.get_last_error())
        return False, f"SetInformationJobObject: {error}"

    if not assign(job, get_current()):
        error = ctypes.WinError(ctypes.get_last_error())
        return False, f"AssignProcessToJobObject: {error}"

    _WINDOWS_JOB = job
    return True, None


def truncate_output(text: str, max_chars: int | None) -> tuple[str, bool]:
    """Обрезать вывод до лимита; вернуть `(текст, обрезано ли)`"""
    if not max_chars or max_chars <= 0 or len(text) <= max_chars:
        return text, False

    note = OUTPUT_TRUNCATED_NOTE.format(limit=max_chars)
    keep = max(0, max_chars - len(note))
    return text[:keep] + note, True

"""Стартовый набор учебных задач (S7-001, S14-002).

Данные вынесены из CLI-скрипта: их использует и `scripts/seed_tasks.py`,
и автонаполнение при старте (`SEED_ON_START`). Импорт идемпотентен по
заголовку задачи.
"""

from app.models.task import TaskDifficulty

TASKS: list[dict[str, object]] = [
    {
        "title": "Сумма двух чисел",
        "description": (
            "Считайте два целых числа (каждое на отдельной строке) и выведите их сумму."
        ),
        "difficulty": TaskDifficulty.EASY,
        "category": "input_output",
        "test_cases": [
            {"input": "2\n3\n", "expected_output": "5", "description": "Простые числа"},
            {"input": "-5\n5\n", "expected_output": "0", "description": "Отрицательные"},
            {"input": "100\n250\n", "expected_output": "350", "description": "Большие числа"},
        ],
        "hints": [
            "input() возвращает строку — её нужно превратить в число через int().",
            "Считайте два числа: a = int(input()) и b = int(input()).",
            "Выведите результат через print(a + b).",
        ],
        "solution_template": "a = int(input())\nb = int(input())\nprint(a + b)\n",
    },
    {
        "title": "Чётное или нечётное",
        "description": (
            "Считайте одно целое число и выведите 'чётное', если оно чётное, "
            "и 'нечётное' в противном случае."
        ),
        "difficulty": TaskDifficulty.EASY,
        "category": "conditions",
        "test_cases": [
            {"input": "4\n", "expected_output": "чётное"},
            {"input": "7\n", "expected_output": "нечётное"},
            {"input": "0\n", "expected_output": "чётное"},
        ],
        "hints": [
            "Остаток от деления в Python — оператор %.",
            "Число чётное, если n % 2 == 0.",
            "Не забудьте ветку else для нечётных чисел.",
        ],
        "solution_template": (
            "n = int(input())\n"
            "if n % 2 == 0:\n"
            "    print(\"чётное\")\n"
            "else:\n"
            "    print(\"нечётное\")\n"
        ),
    },
    {
        "title": "Сумма чисел от 1 до N",
        "description": "Считайте N и выведите сумму всех целых чисел от 1 до N включительно.",
        "difficulty": TaskDifficulty.EASY,
        "category": "loops",
        "test_cases": [
            {"input": "5\n", "expected_output": "15"},
            {"input": "1\n", "expected_output": "1"},
            {"input": "100\n", "expected_output": "5050"},
        ],
        "hints": [
            "Заведите переменную-накопитель, например total = 0.",
            "Переберите числа через for i in range(1, n + 1).",
            "Внутри цикла добавляйте i к total.",
        ],
        "solution_template": (
            "n = int(input())\n"
            "total = 0\n"
            "for i in range(1, n + 1):\n"
            "    total += i\n"
            "print(total)\n"
        ),
    },
    {
        "title": "Максимум из трёх",
        "description": (
            "Считайте три целых числа и выведите наибольшее из них "
            "без использования max()."
        ),
        "difficulty": TaskDifficulty.MEDIUM,
        "category": "conditions",
        "test_cases": [
            {"input": "1\n2\n3\n", "expected_output": "3"},
            {"input": "9\n4\n9\n", "expected_output": "9"},
            {"input": "-1\n-5\n-3\n", "expected_output": "-1"},
        ],
        "hints": [
            "Можно сравнить числа парами: сначала a и b, потом результат с c.",
            "Храните текущий максимум в переменной и обновляйте её при необходимости.",
            "Не забудьте случай равенства чисел.",
        ],
        "solution_template": (
            "a = int(input())\n"
            "b = int(input())\n"
            "c = int(input())\n"
            "current = a\n"
            "if b > current:\n"
            "    current = b\n"
            "if c > current:\n"
            "    current = c\n"
            "print(current)\n"
        ),
    },
    {
        "title": "Таблица умножения",
        "description": (
            "Считайте N и выведите таблицу умножения этого числа на 1..5, "
            "каждый результат на новой строке."
        ),
        "difficulty": TaskDifficulty.MEDIUM,
        "category": "loops",
        "test_cases": [
            {"input": "3\n", "expected_output": "3\n6\n9\n12\n15"},
            {"input": "1\n", "expected_output": "1\n2\n3\n4\n5"},
        ],
        "hints": [
            "Используйте for i in range(1, 6).",
            "Умножайте число на i и печатайте результат.",
        ],
        "solution_template": (
            "n = int(input())\n"
            "for i in range(1, 6):\n"
            "    print(n * i)\n"
        ),
    },
    {
        "title": "Реверс числа",
        "description": (
            "Считайте целое число и выведите его цифры в обратном порядке "
            "(например, 123 → 321). Нули в конце исходного числа отбрасываются."
        ),
        "difficulty": TaskDifficulty.HARD,
        "category": "strings",
        "test_cases": [
            {"input": "123\n", "expected_output": "321"},
            {"input": "10\n", "expected_output": "1"},
            {"input": "7\n", "expected_output": "7"},
        ],
        "hints": [
            "Строку можно перевернуть срезом text[::-1].",
            "После переворота остаток в начале можно убрать через int(...) и снова str(...).",
            "Учтите, что int автоматически убирает ведущие нули.",
        ],
        "solution_template": (
            "text = input().strip()\n"
            "print(str(int(text[::-1])))\n"
        ),
    },
]


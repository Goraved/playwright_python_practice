import argparse
import ast
import os
import sys
from collections import Counter
from typing import Union


class CodeSmellDetector(ast.NodeVisitor):
    """
    Аналізатор CodeSmellDetector перевіряє pytest-тести на основі Playwright на наявність різних проблем (code smells).

    Перевірки (натхненні xUnit Test Patterns та SonarQube):
    1. "Рулетка перевірок" (Assertion Roulette):
       - Забагато перевірок (assert) у тесті.
    2. Занадто багато умов (Too many conditions):
       - Надмірна кількість if.
    3. Занадто багато циклів (Too many loops):
       - Надмірна кількість for/while.
    4. Незрозумілий гість (Mystery Guest):
       - Читання зовнішніх файлів `open()`.
    5. Харкод селектор (Hard-coded Selector):
       - Використання селекторів напряму.
    6. Фіксований таймаут (Fixed Timeout):
       - Використання wait_for_timeout замість динамічного очікування.
    7. Занадто багато прямих очікувань (time.sleep) (Direct Sleep):
       - Використання time.sleep у тестах (до 3 разів дозволено).
    8. Тест занадто довгий (Test too long):
       - Надмірна кількість операторів у тесті.
    9. Занадто складна вкладеність (Nested complexity):
       - 2+ рівні вкладеності if/for/while.
    10. Небезпечне виконання коду (Dangerous execution):
        - Використання `eval()` чи `exec()`.
    11. Харкод пароля (Hard-coded password):
        - Присвоєння значень змінним на кшталт `password`, `pwd`.
    12. Друк у тесті (Print in tests):
        - Наявність `print()` у тестах.
    """

    def __init__(self,
                 max_asserts: int = 30,
                 max_conditions: int = 3,
                 max_loops: int = 3,
                 max_test_length: int = 200) -> None:
        self.max_asserts = max_asserts
        self.max_conditions = max_conditions
        self.max_loops = max_loops
        self.max_test_length = max_test_length

        self.current_test: Union[str, None] = None
        self.current_test_lineno: int = 0
        self.assert_count = 0
        self.condition_count = 0
        self.loop_count = 0
        self.sleep_count = 0
        self.test_smells: dict[str, dict[str, Union[int, list[str]]]] = {}
        self.in_test = False
        self.current_test_body = []
        self.complexity_depth = 0
        self.complexity_violation = False
        self.complexity_line = None  # Line where complexity was first detected

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("test_"):
            self.current_test = node.name
            self.in_test = True
            self.assert_count = 0
            self.condition_count = 0
            self.loop_count = 0
            self.sleep_count = 0
            self.current_test_lineno = node.lineno
            self.current_test_body = node.body
            self.complexity_depth = 0
            self.complexity_violation = False
            self.complexity_line = None

            self.test_smells[self.current_test] = {
                "lineno": self.current_test_lineno,
                "smells": []
            }

            # Перевірка на Незрозумілого гостя
            for stmt in node.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    if isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "open":
                        self.test_smells[self.current_test]["smells"].append(
                            "Незрозумілий гість: Тест використовує зовнішні файли через 'open()'. Використовуйте фікстури або моки."
                        )

        self.generic_visit(node)

        if self.in_test and self.current_test:
            # Рахуємо довжину тесту без першого docstring
            test_length = len(self.current_test_body)
            if (self.current_test_body
                    and isinstance(self.current_test_body[0], ast.Expr)
                    and isinstance(self.current_test_body[0].value, ast.Constant)
                    and isinstance(self.current_test_body[0].value.value, str)):
                test_length -= 1

            # Рулетка перевірок
            if self.assert_count > self.max_asserts:
                self.test_smells[self.current_test]["smells"].append(
                    f"Занадто багато перевірок (assert): {self.assert_count} перевірок."
                )
            # Занадто багато умов
            if self.condition_count > self.max_conditions:
                self.test_smells[self.current_test]["smells"].append(
                    f"Занадто багато умов (if): {self.condition_count} умов."
                )
            # Занадто багато циклів
            if self.loop_count > self.max_loops:
                self.test_smells[self.current_test]["smells"].append(
                    f"Занадто багато циклів (for/while): {self.loop_count} циклів."
                )
            # Надмірна довжина тесту
            if test_length > self.max_test_length:
                self.test_smells[self.current_test]["smells"].append(
                    f"Тест занадто довгий: {test_length} рядків."
                )

            # Надмірна вкладеність
            if self.complexity_violation and self.complexity_line is not None:
                self.test_smells[self.current_test]["smells"].append(
                    f"Занадто складна вкладеність умов/циклів (рядок {self.complexity_line})."
                )

            # Понад 3 sleep
            if self.sleep_count > 3:
                self.test_smells[self.current_test]["smells"].append(
                    f"Занадто багато прямих очікувань (time.sleep): Використано sleep {self.sleep_count} разів, більше 3 допустимих."
                )

            self.in_test = False
            self.current_test = None
            self.current_test_body = []

    def visit_Assert(self, node: ast.Assert) -> None:
        if self.in_test and self.current_test:
            self.assert_count += 1
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        if self.in_test and self.current_test:
            self.condition_count += 1
            self.complexity_depth += 1
            if self.complexity_depth > 2 and not self.complexity_violation:
                self.complexity_violation = True
                self.complexity_line = node.lineno
            self.generic_visit(node)
            self.complexity_depth -= 1
        else:
            self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        if self.in_test and self.current_test:
            self.loop_count += 1
            self.complexity_depth += 1
            if self.complexity_depth > 2 and not self.complexity_violation:
                self.complexity_violation = True
                self.complexity_line = node.lineno
            self.generic_visit(node)
            self.complexity_depth -= 1
        else:
            self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        if self.in_test and self.current_test:
            self.loop_count += 1
            self.complexity_depth += 1
            if self.complexity_depth > 2 and not self.complexity_violation:
                self.complexity_violation = True
                self.complexity_line = node.lineno
            self.generic_visit(node)
            self.complexity_depth -= 1
        else:
            self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self.in_test and self.current_test:
            # Фіксований таймаут
            if isinstance(node.func, ast.Attribute) and node.func.attr == "wait_for_timeout":
                self.test_smells[self.current_test]["smells"].append(
                    "Фіксований таймаут: Використовується wait_for_timeout. Краще застосовувати динамічні очікування."
                )

            # Харкод селектор
            if (isinstance(node.func, ast.Attribute) and
                    node.func.attr in ["locator", "get_by_selector"] and
                    node.args and isinstance(node.args[0], ast.Constant)):
                selector = node.args[0].value
                if isinstance(selector, str) and (selector.startswith("#") or selector.startswith(".")):
                    self.test_smells[self.current_test]["smells"].append(
                        f"Харкод селектор: '{selector}'. Використовуйте параметри чи Page Object."
                    )

            # Занадто багато прямих очікувань (time.sleep) (підрахунок sleep)
            if isinstance(node.func, ast.Name) and node.func.id == "sleep":
                self.sleep_count += 1
            elif (isinstance(node.func, ast.Attribute) and
                  isinstance(node.func.value, ast.Name) and
                  node.func.value.id == "time" and
                  node.func.attr == "sleep"):
                self.sleep_count += 1

            # Небезпечне виконання коду: eval/exec
            if isinstance(node.func, ast.Name) and node.func.id in ["eval", "exec"]:
                self.test_smells[self.current_test]["smells"].append(
                    f"Небезпечне виконання коду: виклик {node.func.id}(). Уникайте використання eval/exec."
                )

            # Використання print у тесті
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                self.test_smells[self.current_test]["smells"].append(
                    "Використання print у тесті. Розгляньте логування або приберіть зайву діагностику."
                )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Харкод пароля: змінні з "password" чи "pwd" у назві
        if self.in_test and self.current_test:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id.lower()
                    if ("password" in var_name or "pwd" in var_name) and isinstance(node.value, ast.Constant):
                        if isinstance(node.value.value, str):
                            self.test_smells[self.current_test]["smells"].append(
                                f"Харкод пароля: змінна '{target.id}' містить пароль у відкритому вигляді."
                            )

        self.generic_visit(node)


def analyze_file(file_path: str, max_asserts: int, max_conditions: int, max_loops: int, max_test_length: int) -> dict[
    str, dict[str, Union[int, list[str]]]]:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            tree = ast.parse(file.read())
    except SyntaxError as e:
        return {"SyntaxError": {"lineno": 0, "smells": [f"Синтаксична помилка у файлі {file_path}: {e}"]}}

    detector = CodeSmellDetector(
        max_asserts=max_asserts,
        max_conditions=max_conditions,
        max_loops=max_loops,
        max_test_length=max_test_length
    )
    detector.visit(tree)
    return detector.test_smells


def find_pytest_files(directory: str) -> list[str]:
    test_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))
    return test_files


def categorize_smell(smell: str) -> str:
    if "Занадто багато перевірок (assert)" in smell:
        return "Занадто багато перевірок (assert)"
    elif "Занадто багато умов (if)" in smell:
        return "Занадто багато умов (if)"
    elif "Занадто багато циклів (for/while)" in smell:
        return "Занадто багато циклів (for/while)"
    elif "Незрозумілий гість" in smell:
        return "Незрозумілий гість"
    elif "Харкод селектор" in smell:
        return "Харкод селектор"
    elif "Фіксований таймаут" in smell:
        return "Фіксований таймаут"
    elif "Занадто багато прямих очікувань (time.sleep)" in smell:
        return "Занадто багато прямих очікувань (time.sleep)"
    elif "Тест занадто довгий" in smell:
        return "Тест занадто довгий"
    elif "Занадто складна вкладеність" in smell:
        return "Занадто складна вкладеність"
    elif "Небезпечне виконання коду" in smell:
        return "Небезпечне виконання коду"
    elif "Харкод пароля" in smell:
        return "Харкод пароля"
    elif "Використання print" in smell:
        return "Використання print у тесті"
    else:
        return "Невідома категорія"


def main() -> None:
    parser = argparse.ArgumentParser(description="Аналіз 'code smells' у pytest-тестах на основі Playwright.")
    parser.add_argument("--dir", default="../tests", help="Директорія з тестами. За замовчуванням: ../tests")
    parser.add_argument("--max-asserts", type=int, default=30,
                        help="Максимальна кількість перевірок у тесті. За замовчуванням: 30")
    parser.add_argument("--max-conditions", type=int, default=3,
                        help="Максимальна кількість умов у тесті. За замовчуванням: 3")
    parser.add_argument("--max-loops", type=int, default=3,
                        help="Максимальна кількість циклів у тесті. За замовчуванням: 3")
    parser.add_argument("--max-test-length", type=int, default=200,
                        help="Максимальна кількість операторів у тесті (без docstring). За замовчуванням: 200")
    args = parser.parse_args()

    print(f"Аналіз файлів pytest у директорії '{args.dir}' на наявність 'code smells'...\n")
    test_files = find_pytest_files(args.dir)
    if not test_files:
        print("Не знайдено жодного файлу з тестами.")
        sys.exit(0)

    total_tests = 0
    smelly_tests = 0
    all_smells_collected = []

    for file_path in test_files:
        test_smells = analyze_file(
            file_path,
            max_asserts=args.max_asserts,
            max_conditions=args.max_conditions,
            max_loops=args.max_loops,
            max_test_length=args.max_test_length
        )

        # Підрахунок усіх тестів (крім SyntaxError)
        for tname in test_smells:
            if tname != "SyntaxError":
                total_tests += 1

        # Фільтруємо лише тести з 'code smells'
        file_smelly_tests = {t: d for t, d in test_smells.items() if d["smells"]}

        if not file_smelly_tests:
            continue

        print(f"[Файл]: {file_path}")
        for test_name, data in file_smelly_tests.items():
            if test_name == "SyntaxError":
                for msg in data["smells"]:
                    print(f"  - {msg}")
                    all_smells_collected.append(msg)
                continue

            smelly_tests += 1
            print(f"\n  [Тест]: {test_name}")
            for smell in data["smells"]:
                print(f"    - {smell}")
                all_smells_collected.append(smell)
            print()

    if smelly_tests == 0:
        print("Не знайдено тестів із 'code smells'.")
        return

    clean_tests = total_tests - smelly_tests
    smelly_percentage = (smelly_tests / total_tests) * 100 if total_tests > 0 else 0

    categorized_smells = [categorize_smell(s) for s in all_smells_collected]
    category_counter = Counter(categorized_smells)

    print("=== Підсумок аналізу ===")
    print(f"Всього проаналізовано тестів: {total_tests}")
    print(f"Тестів із 'code smells': {smelly_tests}")
    print(f"Тестів без 'code smells': {clean_tests}")
    print(f"Відсоток 'smelly' тестів: {smelly_percentage:.2f}%\n")

    print("Статистика по категоріях 'code smells':")
    for cat, count in category_counter.most_common():
        print(f" - {cat}: {count}")


if __name__ == "__main__":
    main()

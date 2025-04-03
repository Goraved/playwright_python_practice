import argparse
import ast
import os
import sys
from collections import Counter
from typing import Union


class CodeSmellDetector(ast.NodeVisitor):
    """
    CodeSmellDetector analyzer checks Playwright-based pytest tests for various issues (code smells).

    Checks (inspired by xUnit Test Patterns and SonarQube):
    1. "Assertion Roulette":
       - Too many assertions in a test.
    2. Too many conditions:
       - Excessive number of if statements.
    3. Too many loops:
       - Excessive number of for/while loops.
    4. Mystery Guest:
       - Reading external files using `open()`.
    5. Hard-coded Selector:
       - Direct selector usage.
    6. Fixed Timeout:
       - Using wait_for_timeout instead of dynamic waiting.
    7. Direct Sleep (time.sleep):
       - Using time.sleep in tests (up to 3 times allowed).
    8. Test too long:
       - Excessive number of statements in a test.
    9. Nested complexity:
       - 2+ levels of nesting for if/for/while.
    10. Dangerous execution:
        - Using `eval()` or `exec()`.
    11. Hard-coded password:
        - Assigning values to variables like `password`, `pwd`.
    12. Print in tests:
        - Presence of `print()` in tests.
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

            # Check for Mystery Guest
            for stmt in node.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    if isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "open":
                        self.test_smells[self.current_test]["smells"].append(
                            "Mystery Guest: Test uses external files via 'open()'. Use fixtures or mocks."
                        )

        self.generic_visit(node)

        if self.in_test and self.current_test:
            # Count test length without first docstring
            test_length = len(self.current_test_body)
            if (self.current_test_body
                    and isinstance(self.current_test_body[0], ast.Expr)
                    and isinstance(self.current_test_body[0].value, ast.Constant)
                    and isinstance(self.current_test_body[0].value.value, str)):
                test_length -= 1

            # Assertion Roulette
            if self.assert_count > self.max_asserts:
                self.test_smells[self.current_test]["smells"].append(
                    f"Too many assertions: {self.assert_count} assertions."
                )
            # Too many conditions
            if self.condition_count > self.max_conditions:
                self.test_smells[self.current_test]["smells"].append(
                    f"Too many conditions (if): {self.condition_count} conditions."
                )
            # Too many loops
            if self.loop_count > self.max_loops:
                self.test_smells[self.current_test]["smells"].append(
                    f"Too many loops (for/while): {self.loop_count} loops."
                )
            # Test length
            if test_length > self.max_test_length:
                self.test_smells[self.current_test]["smells"].append(
                    f"Test too long: {test_length} lines."
                )

            # Nested complexity
            if self.complexity_violation and self.complexity_line is not None:
                self.test_smells[self.current_test]["smells"].append(
                    f"Excessive nested conditions/loops (line {self.complexity_line})."
                )

            # More than 3 sleep
            if self.sleep_count > 3:
                self.test_smells[self.current_test]["smells"].append(
                    f"Too many direct waits (time.sleep): Used sleep {self.sleep_count} times, more than 3 allowed."
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
            # Fixed timeout
            if isinstance(node.func, ast.Attribute) and node.func.attr == "wait_for_timeout":
                self.test_smells[self.current_test]["smells"].append(
                    "Fixed Timeout: Using wait_for_timeout. Better to use dynamic waits."
                )

            # Hard-coded selector
            if (isinstance(node.func, ast.Attribute) and
                    node.func.attr in ["locator", "get_by_selector"] and
                    node.args and isinstance(node.args[0], ast.Constant)):
                selector = node.args[0].value
                if isinstance(selector, str) and (selector.startswith("#") or selector.startswith(".")):
                    self.test_smells[self.current_test]["smells"].append(
                        f"Hard-coded Selector: '{selector}'. Use parameters or Page Object."
                    )

            # Direct sleep counting
            if isinstance(node.func, ast.Name) and node.func.id == "sleep":
                self.sleep_count += 1
            elif (isinstance(node.func, ast.Attribute) and
                  isinstance(node.func.value, ast.Name) and
                  node.func.value.id == "time" and
                  node.func.attr == "sleep"):
                self.sleep_count += 1

            # Dangerous code execution: eval/exec
            if isinstance(node.func, ast.Name) and node.func.id in ["eval", "exec"]:
                self.test_smells[self.current_test]["smells"].append(
                    f"Dangerous Execution: calling {node.func.id}(). Avoid using eval/exec."
                )

            # Using print in test
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                self.test_smells[self.current_test]["smells"].append(
                    "Print used in test. Consider logging or remove unnecessary diagnostics."
                )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Hard-coded password: variables with "password" or "pwd" in name
        if self.in_test and self.current_test:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id.lower()
                    if ("password" in var_name or "pwd" in var_name) and isinstance(node.value, ast.Constant):
                        if isinstance(node.value.value, str):
                            self.test_smells[self.current_test]["smells"].append(
                                f"Hard-coded Password: variable '{target.id}' contains password in plain text."
                            )

        self.generic_visit(node)


def analyze_file(file_path: str, max_asserts: int, max_conditions: int, max_loops: int, max_test_length: int) -> dict[
    str, dict[str, Union[int, list[str]]]]:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            tree = ast.parse(file.read())
    except SyntaxError as e:
        return {"SyntaxError": {"lineno": 0, "smells": [f"Syntax Error in file {file_path}: {e}"]}}

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
    if "Too many assertions" in smell:
        return "Too many assertions"
    elif "Too many conditions (if)" in smell:
        return "Too many conditions (if)"
    elif "Too many loops (for/while)" in smell:
        return "Too many loops (for/while)"
    elif "Mystery Guest" in smell:
        return "Mystery Guest"
    elif "Hard-coded Selector" in smell:
        return "Hard-coded Selector"
    elif "Fixed Timeout" in smell:
        return "Fixed Timeout"
    elif "Too many direct waits (time.sleep)" in smell:
        return "Too many direct waits (time.sleep)"
    elif "Test too long" in smell:
        return "Test too long"
    elif "Excessive nested" in smell:
        return "Excessive nested complexity"
    elif "Dangerous Execution" in smell:
        return "Dangerous code execution"
    elif "Hard-coded Password" in smell:
        return "Hard-coded password"
    elif "Print used in test" in smell:
        return "Print in test"
    else:
        return "Unknown category"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze 'code smells' in Playwright-based pytest tests.")
    parser.add_argument("--dir", default="../tests", help="Directory with tests. Default: ../tests")
    parser.add_argument("--max-asserts", type=int, default=30,
                        help="Maximum number of assertions in a test. Default: 30")
    parser.add_argument("--max-conditions", type=int, default=3,
                        help="Maximum number of conditions in a test. Default: 3")
    parser.add_argument("--max-loops", type=int, default=3,
                        help="Maximum number of loops in a test. Default: 3")
    parser.add_argument("--max-test-length", type=int, default=200,
                        help="Maximum number of statements in a test (without docstring). Default: 200")
    args = parser.parse_args()

    print(f"Analyzing pytest files in directory '{args.dir}' for code smells...\n")
    test_files = find_pytest_files(args.dir)
    if not test_files:
        print("No test files found.")
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

        # Count all tests (except SyntaxError)
        for tname in test_smells:
            if tname != "SyntaxError":
                total_tests += 1

        # Filter only tests with 'code smells'
        file_smelly_tests = {t: d for t, d in test_smells.items() if d["smells"]}

        if not file_smelly_tests:
            continue

        print(f"[File]: {file_path}")
        for test_name, data in file_smelly_tests.items():
            if test_name == "SyntaxError":
                for msg in data["smells"]:
                    print(f"  - {msg}")
                    all_smells_collected.append(msg)
                continue

            smelly_tests += 1
            print(f"\n  [Test]: {test_name}")
            for smell in data["smells"]:
                print(f"    - {smell}")
                all_smells_collected.append(smell)
            print()

    clean_tests = total_tests - smelly_tests
    smelly_percentage = (smelly_tests / total_tests) * 100 if total_tests > 0 else 0

    categorized_smells = [categorize_smell(s) for s in all_smells_collected]
    category_counter = Counter(categorized_smells)

    print("=== Analysis Summary ===")
    print(f"Total tests analyzed: {total_tests}")
    print(f"Tests with code smells: {smelly_tests}")
    print(f"Tests without code smells: {clean_tests}")
    print(f"Percentage of 'smelly' tests: {smelly_percentage:.2f}%\n")

    print("Code Smell Categories Statistics:")
    for cat, count in category_counter.most_common():
        print(f" - {cat}: {count}")


if __name__ == "__main__":
    main()
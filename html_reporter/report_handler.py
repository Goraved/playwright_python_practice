"""
report_handler.py

Handles test reporting logic, including result aggregation, HTML generation, and environment metadata.
This module provides functionality for:
- Storing and managing test results
- Generating GitHub links for test files
- Collecting environment information
- Aggregating test results across multiple workers
- Generating HTML test reports

Classes:
    TestResult: Stores and manages individual test result data

Functions:
    save_test_result: Saves test results to JSON files
    aggregate_results: Combines results from multiple worker files
    calculate_stats: Generates test execution statistics
    format_timestamp: Converts Unix timestamps to readable format  
    get_pytest_metadata: Collects pytest and package version info
    generate_html_report: Creates the final HTML test report
"""
import base64
import importlib.metadata
import json
import os
import platform
import re
import time
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Union

import jinja2
import pytest


class TestResult:
    """
    Stores and manages test result data including execution details, metadata and environment info.
    
    Attributes:
        timestamp (float): Test execution timestamp
        nodeid (str): Pytest node identifier
        outcome (str): Test result outcome (passed/failed/skipped etc)
        phase_durations (float): Test execution duration in seconds
        description (str): Test docstring/description
        markers (list[str]): Applied pytest markers
        metadata (Dict): Additional test metadata 
        environment (Dict): Environment information
        screenshot (Optional[str]): Screenshot data if captured
        error (Optional[str]): Error details if test failed
        logs (list[str]): Test execution logs
        exception_type (str): Type of exception if test failed
        wasxfail (Optional[bool]): Whether test was expected to fail
        worker_id (str): xdist worker identifier
        github_link (str): Link to test file in GitHub
    """

    def __init__(self, item: pytest.Item, outcome: str, duration: float, phase_durations: dict[str, float],
                 **kwargs) -> None:
        """
        Initialize test result with execution data.

        Args:
            item: Pytest test item
            outcome: Test execution outcome
            phase_durations: Test execution duration
        """
        self.timestamp = kwargs.get('timestamp', time.time())
        self.nodeid = item.nodeid
        self.outcome = outcome
        self.duration = duration
        self.phase_durations = phase_durations
        self.description = item.obj.__doc__ or ""
        self.markers = [mark.name for mark in item.iter_markers()]
        self.metadata = self._extract_metadata(item)
        self.environment = self._get_environment_info(item)
        self.screenshot: Optional[str] = None
        self.error: Optional[str] = None
        self.logs: list[str] = []
        self.exception_type = ""
        self.wasxfail: Optional[bool] = None
        self.skip_reason: Optional[str] = None
        self.phase: str = "call"  # default to call phase
        self.error_phase: Optional[str] = None  # indicates which phase had an error
        self.execution_count: int = getattr(item, 'execution_count', 1)
        self.caplog: Optional[str] = None
        self.capstderr: Optional[str] = None
        self.capstdout: Optional[str] = None

        if hasattr(item.config, "workerinput"):
            self.worker_id = item.config.workerinput.get("workerid", "master")
        else:
            self.worker_id = "master"

        self.github_link = self._generate_github_link(item)

    def _generate_github_link(self, item: pytest.Item) -> str:
        """
        Generate a GitHub link to the test file and line number.

        Args:
            item: Pytest test item

        Returns:
            str: URL to test file in GitHub
        """
        try:
            parts = self.nodeid.split("::")
            file_path = parts[0]
            line_number = getattr(item.function, "__code__", None).co_firstlineno if hasattr(item, "function") else "1"

            github_base_url = "https://github.com/Goraved/playwright_python_practice/blob/master/"
            github_url = f"{github_base_url}{file_path}#L{line_number}"

            return github_url
        except Exception as e:
            return f"Error generating GitHub link: {str(e)}"

    @staticmethod
    def _get_environment_info(item: pytest.Item) -> dict[str, str]:
        """
        Collect environment information including browser details.

        Args:
            item: Pytest test item

        Returns:
            Dict containing environment information
        """
        env_info = {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor()
        }

        page = item.funcargs.get("page")
        if page:
            try:
                browser = page.context.browser
                env_info.update({
                    "browser": browser.browser_type.name.capitalize(),
                    "browser_version": browser.version
                })
            except Exception:
                env_info.update({
                    "browser": "Unknown",
                    "browser_version": "Unknown"
                })
        return env_info

    @staticmethod
    def _extract_metadata(item: pytest.Item) -> dict[str, Any]:
        """
        Extract metadata from test item markers.

        Args:
            item: pytest test item

        Returns:
            Dict containing test metadata
        """
        metadata = {}
        for mark in item.own_markers:
            if mark.name == "meta":
                for key, value in mark.kwargs.items():
                    if isinstance(value, type):
                        metadata[key] = value.__name__
                    else:
                        metadata[key] = value
            elif mark.name == "parametrize":
                # Extract parameter value from test name
                param_value = None
                if '[' in item.name and ']' in item.name:
                    param_value = item.name.split('[')[-1].rstrip(']')

                for arg in mark.args:
                    if isinstance(arg, list):
                        for param in arg:
                            # Match parameter value with the one from test name
                            if hasattr(param, 'values') and param.id == param_value:
                                for value in param.values:
                                    if hasattr(value, 'mark') and value.mark.name == 'meta':
                                        for key, val in value.mark.kwargs.items():
                                            if isinstance(val, type):
                                                metadata[key] = val.__name__
                                            else:
                                                metadata[key] = val
        return metadata

    def to_dict(self) -> dict[str, Any]:
        """
        Convert test result to dictionary for JSON serialization.

        Returns:
            Dict containing all test result data
        """
        # Validate essential attributes are present
        assert hasattr(self, 'timestamp'), "TestResult missing 'timestamp' attribute"
        assert hasattr(self, 'nodeid'), "TestResult missing 'nodeid' attribute"
        assert hasattr(self, 'outcome'), "TestResult missing 'outcome' attribute"

        if hasattr(self, 'execution_log'):
            formatted_logs = []
            for log in self.execution_log:
                if ' - ' in log:
                    type_name, rest = log.split(' - ', 1)
                    indent = log.count('  ')
                    formatted_logs.append('  ' * indent + f"{type_name} - {rest}")
            self.logs.extend(formatted_logs)
        return {
            "timestamp": self.timestamp,
            "nodeid": self.nodeid,
            "outcome": self.outcome,
            "duration": self.duration,
            "phase_durations": self.phase_durations,
            "description": self.description,
            "markers": self.markers,
            "metadata": self.metadata,
            "environment": self.environment,
            "screenshot": self.screenshot,
            "error": self.error,
            "logs": self.logs,
            "exception_type": self.exception_type,
            "wasxfail": self.wasxfail,
            "skip_reason": self.skip_reason,
            "worker_id": self.worker_id,
            "github_link": self.github_link,
            "phase": self.phase,
            "error_phase": self.error_phase,
            "execution_count": self.execution_count,
            "caplog": self.caplog,
            "capstderr": self.capstderr,
            "capstdout": self.capstdout
        }


def save_test_result(result: TestResult, report_dir: Path) -> None:
    """
    Save test result as JSON file.

    Args:
        result: TestResult object to save
        report_dir: Directory to save report file
    """
    report_file = report_dir / f"worker_{result.worker_id}.json"
    with open(report_file, "a") as f:
        json.dump(result.to_dict(), f)
        f.write("\n")


def aggregate_results(report_dir: Path) -> list[dict[str, Any]]:
    """
    Aggregate test results from all worker files.

    Args:
        report_dir: Directory containing result files

    Returns:
        List of test results from all workers
    """
    assert isinstance(report_dir, Path), "report_dir must be a Path object"
    assert report_dir.exists(), f"Report directory does not exist: {report_dir}"

    seen_tests = set()
    unique_results = []

    json_files = list(report_dir.glob("*.json"))
    if not json_files:
        return []  # No results found

    for json_file in json_files:
        try:
            with open(json_file) as f:
                for line in f:
                    if line.strip():
                        test = json.loads(line)

                        # Validate each test result has required fields
                        assert "nodeid" in test, f"Test result missing 'nodeid' in file {json_file}"
                        assert "timestamp" in test, f"Test result missing 'timestamp' in file {json_file}"
                        assert "outcome" in test, f"Test result missing 'outcome' in file {json_file}"

                        unique_key = (test["nodeid"], test["timestamp"])  # Unique test identifier
                        if unique_key not in seen_tests:
                            seen_tests.add(unique_key)
                            unique_results.append(test)
        except json.JSONDecodeError as e:
            raise AssertionError(f"Invalid JSON in results file {json_file}: {str(e)}")

    return unique_results


def calculate_stats(results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate test statistics from results.

    Args:
        results: List of test results

    Returns:
        Dict containing test statistics
    """
    assert isinstance(results, list), "Results must be a list"

    if not results:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "error": 0,
            "xfailed": 0,
            "xpassed": 0,
            "rerun": 0,
            "start_time": 0,
            "end_time": 0,
            "total_duration": 0,
            "success_rate": 0
        }

    # Assert that all results have required keys
    required_keys = ["timestamp", "outcome", "duration"]
    for result in results:
        for key in required_keys:
            assert key in result, f"Test result missing required '{key}' key"

    start_time = min(r["timestamp"] for r in results)
    end_time = max(r["timestamp"] + (r["duration"] or 0) for r in results)
    total_duration = end_time - start_time
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r["outcome"] == "passed"),
        "failed": sum(1 for r in results if r["outcome"] == "failed"),
        "skipped": sum(1 for r in results if r["outcome"] == "skipped"),
        "error": sum(1 for r in results if r["outcome"] == "error"),
        "xfailed": sum(1 for r in results if r["outcome"] == "xfailed"),
        "xpassed": sum(1 for r in results if r["outcome"] == "xpassed"),
        "rerun": sum(1 for r in results if r["outcome"] == "rerun"),
        "start_time": start_time,
        "end_time": end_time,
        "total_duration": total_duration,
        "success_rate": round(
            (sum(1 for r in results if r["outcome"] == "passed") / len(results)) * 100, 2
        )
    }


def format_timestamp(timestamp: float) -> str:
    """
    Convert Unix timestamp to readable format.

    Args:
        timestamp: Unix timestamp

    Returns:
        Formatted date/time string
    """
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


@lru_cache(maxsize=1)
def get_pytest_metadata() -> dict[str, Union[str, dict[str, str]]]:
    """
    Get metadata about pytest and related packages.

    Returns:
        Dict containing version information for pytest and related packages
    """
    metadata = {
        "pytest_version": pytest.__version__,
        "packages": {}
    }

    pytest_related = [
        "pytest-html", "pytest-xdist", "pytest-timeout",
        "pytest-rerunfailures", "pytest-picked", "pytest-metadata",
        "pytest-anyio", "pytest-cov"
    ]

    for package in pytest_related:
        try:
            metadata["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass

    common_packages = ["playwright", "httpx", "psycopg2-binary", "jinja2"]
    for package in common_packages:
        try:
            metadata["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass

    return metadata


def generate_human_readable_summary(results: list[dict], stats: dict, slow_test_threshold_sec: int = 120) -> str:
    """
    Generate the ULTIMATE human-readable and action-packed test run summary,
    crafted in HTML for better styling and web presentation.

    This summary delivers:
    - Crystal-clear, engaging, and conversational tone
    - Actionable insights and prioritized recommendations
    - Detailed diagnostics across test statuses, performance, reliability, and reruns
    - A laser focus on immediate next steps for the team
    """

    if not results:
        return "🚨 <b>CODE RED: Test Results MIA!</b> 🚨<br>We have a critical situation &ndash; no test results were found. Possible culprits: test execution failures, incorrect report directory, or deeper system issues. <b>Immediate attention and troubleshooting required!</b>"

    # --- 🔍 Run Overview: The Big Picture ---
    total_tests = stats['total']
    pass_rate = (stats['passed'] / total_tests * 100) if total_tests > 0 else 0

    # --- 🚨 Situation Message Based on Pass Rate ---
    if pass_rate == 100:
        situation_message = "🌟 Perfection Achieved: All tests passed flawlessly. Outstanding work!"
    elif pass_rate >= 95:
        situation_message = "🏆 Exceptional performance: nearly all tests passed with flying colors!"
    elif pass_rate >= 90:
        situation_message = "🎉 Great performance: a very high pass rate, with only minor issues remaining."
    elif pass_rate >= 80:
        situation_message = "👍 Solid performance: a good pass rate, though there is room for improvement."
    elif pass_rate >= 60:
        situation_message = "⚠️ Moderate performance: several tests failed or errored; attention needed."
    else:
        situation_message = "🚨 Critical performance alert: the pass rate is extremely low; immediate action required!"

    earliest_start_time = stats['start_time']
    latest_end_time = stats['end_time']
    run_duration_seconds = stats['total_duration']
    formatted_runtime = time.strftime("%H:%M:%S", time.gmtime(run_duration_seconds))

    slow_tests = [r for r in results if r['duration'] > slow_test_threshold_sec]
    rerun_tests = [r for r in results if r['outcome'] == "rerun"]

    high_level_summary = (
        f"📊 <b>Executive Test Dashboard</b> 📊<br>"
        f"- <b>Total Tests Executed:</b> {total_tests} brave test warriors ventured into battle!<br>"
        f"- <b>Overall Pass Rate:</b> {pass_rate:.1f}% &ndash; Our crucial quality indicator.<br>"
        f"- <b>Total Run Time:</b> {formatted_runtime} &ndash; Keeping an eye on efficiency.<br>"
        f"- <b>Key Issues:</b> {stats['failed']} failures, {stats['error']} errors, {stats['rerun']} reruns, {len(slow_tests)} sluggish tests. Our immediate action items."
    )

    # --- 🚦 Status Breakdown: Decoding the Test Results ---
    total_failing = stats['failed'] + stats['error'] + stats['xfailed']
    status_messages = []

    if total_failing == 0 and stats['passed'] == total_tests:
        status_messages.append(
            "🏆 <b>Perfection Achieved: 100% Tests Passing!</b> 🏆<br>An immaculate test run! Savor this moment, but remember &ndash; vigilance is key. Keep pushing forward!")
    else:
        status_messages.append("🔎 <b>Detailed Test Status Diagnostics:</b>")
        status_messages.extend([
            f"  ✅ <b>{stats['passed']} Tests Passed ({pass_rate:.1f}%):</b> The backbone of our test suite. Nurture and expand this group.",
            f"  ❌ <b>{stats['failed']} Tests Failed ({(stats['failed'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Top priority &ndash; every failure is an opportunity for improvement. Dive into these ASAP.",
            f"  ⚠️ <b>{stats['error']} Errors Encountered ({(stats['error'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Triage needed. Focus on environment stability and test setup.",
            f"  🔄 <b>{stats['rerun']} Tests Rerun ({(stats['rerun'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Reruns can mask underlying problems. Investigate rerun patterns and reasons.",
            f"  ⏩ <b>{stats['skipped']} Tests Skipped ({(stats['skipped'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Review skipped tests. Are we bypassing critical checks?",
            f"  ❎ <b>{stats['xfailed']} Expected Failures ({(stats['xfailed'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Known issues lurking. Prioritize fixes to shift these to passing.",
            f"  ❗ <b>{stats['xpassed']} Unexpected Passes ({(stats['xpassed'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Surprising, but validate before celebrating &ndash; ensure it's genuine progress."
        ])

        if stats['failed'] + stats['error'] + stats['rerun'] > 0:
            status_messages.append(
                "<br>⚡ <b>Urgent Action Items:</b> Laser focus on resolving failures, errors, and tests requiring reruns. These are our top quality blockers.")

    # --- 🏎️ Performance Review: Spotting Speed Bumps ---
    fast_tests = sorted(results, key=lambda x: x['duration'])
    min_test = fast_tests[0] if fast_tests else None
    max_test = fast_tests[-1] if fast_tests else None

    min_test_msg = (
        f"🥇 <b>Fastest Test:</b> <code>{min_test['nodeid']}</code> &ndash; blazed through in just {min_test['duration']:.2f} seconds!"
        if min_test else "No test duration data available."
    )

    max_test_msg = (
        f"🐌 <b>Slowest Test:</b> <code>{max_test['nodeid']}</code> &ndash; took a whopping {max_test['duration']:.2f} seconds. Let's optimize this slowpoke!"
        if max_test else "No test duration data available."
    )

    # Calculate percentage of slow tests
    slow_tests_percent = (len(slow_tests) / total_tests * 100) if total_tests > 0 else 0
    slow_test_stats = (
        f"⏱️ <b>Slow Test Stats:</b> {len(slow_tests)} tests ({slow_tests_percent:.1f}%) took longer than {slow_test_threshold_sec / 60:.0f} minutes to complete."
    )

    if slow_tests:
        categorized_slow_tests = {
            "API Tests": [t for t in slow_tests if
                          "api" in t["nodeid"].lower() or "test_registration" in t["nodeid"].lower()],
            "Excerpt Tests": [t for t in slow_tests if
                              "db" in t["nodeid"].lower() or "test_excerpt" in t["nodeid"].lower()],
            "Notary Tests": [t for t in slow_tests if "notary" in t["nodeid"].lower()],
            "Ministry Tests": [t for t in slow_tests if "ministery" in t["nodeid"].lower()],
            "OMC Tests": [t for t in slow_tests if "omc" in t["nodeid"].lower()],
            "KPK Tests": [t for t in slow_tests if "kpk" in t["nodeid"].lower()],
            "DP Tests": [t for t in slow_tests if "dp" in t["nodeid"].lower()],
            "Admin Tests": [t for t in slow_tests if "admin" in t["nodeid"].lower()],
            "Redash Tests": [t for t in slow_tests if "redash" in t["nodeid"].lower()],
            "Automatic BP Tests": [t for t in slow_tests if "automatic_bp" in t["nodeid"].lower()],
        }

        optimization_msg_lines = [
            f"⏱️ <b>{len(slow_tests)} Sluggish Tests Detected (&gt;{slow_test_threshold_sec / 60:.0f} min):</b> Time for some serious performance tuning!"]
        for category, tests in categorized_slow_tests.items():
            if tests:
                example_test_name = tests[0]['nodeid'].split("::")[-1] if "::" in tests[0]['nodeid'] else tests[0][
                    'nodeid']
                optimization_msg_lines.append(
                    f"  &ndash; <b>{category}:</b> {len(tests)} slowpokes found (e.g., <code>{example_test_name}</code>...). Dig into these for optimization opportunities.")

        optimization_msg_lines.append("<br>🚀 <b>Speed Booster Tactics:</b><br>"
                                      "&ndash; <b>Profiling & Bottleneck Analysis:</b> Identify hotspots with surgical precision &ndash; drill down into method-level timings.<br>"
                                      "&ndash; <b>Turbocharge with Parallelization:</b> Leverage concurrent test execution wherever feasible.<br>"
                                      "&ndash; <b>Streamline with Mocks & Stubs:</b> Replace slow dependencies with lightning-fast mocks.<br>"
                                      "&ndash; <b>Code & Logic Refinement:</b> Prune redundancies, optimize algorithms, and streamline test flows.<br>"
                                      "&ndash; <b>Env & Data Tuning:</b> Ensure test env and test data are lean and mean for optimal performance.")
        optimization_msg = "<br>".join(optimization_msg_lines)

    else:
        optimization_msg = "🏎️💨 <b>Full Speed Ahead!</b> Every test crossed the finish line in record time!"

    # --- 🐢 Slow Functions Analysis: Identifying Method-Level Bottlenecks ---
    if 'slow_functions' in stats and stats['slow_functions']:
        slow_functions_lines = [
            "<br>🐢 <b>Slow Functions Analysis:</b> Methods consistently taking too long across multiple tests:"
        ]

        # Sort slow functions by frequency (most occurrences first)
        sorted_slow_funcs = sorted(stats['slow_functions'].items(), key=lambda x: x[1], reverse=True)

        for func_name, occurrence_count in sorted_slow_funcs:
            slow_functions_lines.append(
                f"  &ndash; <code>{func_name}</code>: slow in <b>{occurrence_count}</b> test(s). Optimize this common bottleneck!"
            )

        if sorted_slow_funcs:
            slow_functions_lines.append(
                "<br>🔧 <b>Function Optimization Tips:</b><br>"
                "&ndash; <b>Refactor Core Logic:</b> Look for redundant operations or inefficient algorithms.<br>"
                "&ndash; <b>Optimize Wait Conditions:</b> Review explicit waits and timeout conditions.<br>"
                "&ndash; <b>Cache Common Operations:</b> Avoid repeating expensive operations.<br>"
                "&ndash; <b>Consider Parallel Execution:</b> Where possible, parallelize time-consuming operations."
            )

        slow_functions_msg = "<br>".join(slow_functions_lines)
    else:
        slow_functions_msg = "📊 <b>Function Timing Analysis:</b> No consistently slow functions detected across multiple tests."

    # --- 🔁 Reruns Report Card: Analyzing Repeated Attempts ---
    if rerun_tests:
        rerun_msg_lines = [
            f"🔄 <b>Rerun Roundup:</b> {len(rerun_tests)} tests went through reruns in this session.",
            "<br>🤔 <b>Rerun Analysis:</b>",
            f"  &ndash; <b>Rerun Rate:</b> {len(rerun_tests) / total_tests:.1%} of tests needed repeated attempts.",
            f"  &ndash; <b>Max Attempts:</b> The most stubborn test, <code>{max(rerun_tests, key=lambda t: t.get('rerun_attempts', 0))['nodeid']}</code>, took {max(t.get('rerun_attempts', 0) for t in rerun_tests)} tries to pass.<br>",
            "💡 <b>Rerun Reflections & Recommendations:</b>",
            "  &ndash; Flaky tests may stem from unstable network conditions, timing issues, or intermittent backend glitches.",
            "  &ndash; To reduce flakiness, consider adding explicit waits, refining synchronization, and ensuring a stable test environment.",
        ]
        rerun_msg = "<br>".join(rerun_msg_lines)
    else:
        rerun_msg = "🎯 <b>One-and-Done!</b> No reruns necessary &ndash; all tests passed on the first try!"

    # --- 📜 The Verdict: Final Test Run Assessment ---
    summary = (
            f"<h4>🎬 <b>Analytical Test Run Commentary</b> 🎬</h1><br>"
            f"{situation_message}<br>"
            f"{high_level_summary}"
            f"<hr>"
            f"<h5>1️⃣ <b>Test Execution Overview:</b></h5>"
            f"- ⏰ Started At: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(earliest_start_time))}<br>"
            f"- ⏰ Finished At: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest_end_time))}<br>"
            f"- 📈 Total Runtime: {formatted_runtime}<br>"
            f"<br><h5>2️⃣ <b>Test Status Specifics:</b></h5>" + "<br>".join(status_messages) + "<br>"
                                                                                               f"<br><h5>3️⃣ <b>Performance Post-Mortem:</b></h5>"
                                                                                               f"- {slow_test_stats}<br>"
                                                                                               f"- {min_test_msg}<br>"
                                                                                               f"- {max_test_msg}<br>"
                                                                                               f"- {optimization_msg}<br>"
                                                                                               f"- {slow_functions_msg}<br>"
                                                                                               f"<br><h5>4️⃣ <b>Reruns Retrospective:</b></h5><br>"
                                                                                               f"- {rerun_msg}<br>"
    )

    return summary


def analyze_slow_execution_logs(results: list[dict[str, Any]], threshold_seconds: float = 10.0) -> dict[str, int]:
    """
    Analyze execution logs from slow tests to identify patterns and common bottlenecks.

    Args:
        results: List of test results
        threshold_seconds: Minimum execution time to consider a function as slow (default: 10 seconds)

    Returns:
        Dictionary mapping slow functions to their occurrence count, including only those that were slow at least 3 times
    """
    log_frequency = {}

    # Process all tests
    for test in results:
        if "logs" in test and test["logs"]:
            for log in test["logs"]:
                # Extract function name and duration
                parts = log.strip().split(': ')
                if len(parts) == 2:
                    function_name = parts[0].strip()
                    duration_str = parts[1].strip()

                    # Extract the duration value
                    duration_match = re.search(r'(\d+\.?\d*)', duration_str)
                    if duration_match:
                        duration_value = float(duration_match.group(1))

                        # Check if the function took longer than the threshold
                        if duration_value > threshold_seconds:
                            # Store the function name and increment its count
                            log_frequency[function_name] = log_frequency.get(function_name, 0) + 1

    # Filter functions that were slow at least 3 times
    frequent_slow_functions = {k: v for k, v in log_frequency.items() if v >= 3}

    # Sort by frequency (most common first)
    sorted_logs = dict(sorted(frequent_slow_functions.items(), key=lambda x: x[1], reverse=True))

    return sorted_logs


def compress_data(data):
    """Compress JSON data to Base64 encoded string"""
    # Convert data to JSON string
    json_data = json.dumps(data, separators=(',', ':'))  # Compact JSON

    # Compress using zlib
    compressed = zlib.compress(json_data.encode('utf-8'), level=6)

    # Base64 encode
    return base64.b64encode(compressed).decode('utf-8')


def generate_html_report(session: pytest.Session, report_dir: Path) -> None:
    """
    Generate the final HTML report.

    Args:
        session: Pytest session object
        report_dir: Directory containing test results
    """
    report_path = session.config.getoption("--html-report")
    assert report_path, "HTML report path not specified. Use --html-report option."

    results = aggregate_results(report_dir)
    if hasattr(session.config, "workerinput"):
        return

    if not results:
        with open(report_path, "w") as f:
            f.write("<html><body><h1>No tests were run</h1></body></html>")
        return

    stats = calculate_stats(results)
    stats['slow_functions'] = analyze_slow_execution_logs(results)
    stats['summary'] = generate_human_readable_summary(results, stats)

    # Assert that we have at least one valid result with environment data
    assert results and 'environment' in results[0], "No valid test results found with environment data"
    environment = results[0]['environment']

    metadata = get_pytest_metadata()
    assert metadata and 'pytest_version' in metadata, "Failed to retrieve pytest metadata"

    from jinja2 import Environment, FileSystemLoader
    try:
        env = Environment(loader=FileSystemLoader("html_reporter"))
        # Verify template directory exists
        assert os.path.exists("html_reporter"), "Templates directory not found"

        env.filters['format_timestamp'] = format_timestamp
        for test in results:
            test['formatted_timestamp'] = format_timestamp(test['timestamp'])

        template = env.get_template("report_template.html")
        # Verify template exists
        assert template, "Report template 'report_template.html' not found"

        # Load CSS and JS from separate files
        with open("html_reporter/static/css/styles.css", "r") as css_file:
            css_content = css_file.read()

        with open("html_reporter/static/js/report.js", "r") as js_file:
            js_content_template = js_file.read()

        # Create a template from the JS content string
        js_template = jinja2.Template(js_content_template)

        # Create optimized results for timeline
        timeline_data = []
        for test in results:
            # Only include fields needed for timeline visualization
            timeline_data.append({
                'timestamp': test['timestamp'],
                'duration': test['duration'],
                'outcome': test['outcome'],
                'nodeid': test['nodeid'],
                'worker_id': test.get('worker_id', 'master'),
                'metadata': {
                    'case_title': test.get('metadata', {}).get('case_title', '')
                }
            })

        # Render the JS with the same context as your main template
        js_context = {
            'results': results,
            'stats': stats,
            'timeline_data': timeline_data,
        }
        js_content = js_template.render(**js_context)

        job_id = None
        job_url = None

        # Validate key data before rendering
        assert isinstance(stats, dict), "Stats must be a dictionary"
        assert 'total' in stats, "Stats missing 'total' key"
        assert 'passed' in stats, "Stats missing 'passed' key"
        assert 'failed' in stats, "Stats missing 'failed' key"
        assert 'success_rate' in stats, "Stats missing 'success_rate' key"
        assert isinstance(results, list), "Results must be a list"
        assert isinstance(environment, dict), "Environment must be a dictionary"

        compressed_tests = compress_data(results)
        compressed_timeline = compress_data(timeline_data)

        html_output = template.render(
            title=session.config.getoption("--report-title"),
            stats=stats,
            results=results,
            timeline_data_json=json.dumps(timeline_data),
            compressed_tests=compressed_tests,
            compressed_timeline=compressed_timeline,
            environment=environment,
            metadata=metadata,
            generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            job_url=job_url,
            job_id=job_id,
            css_content=css_content,
            js_content=js_content
        )

        with open(report_path, "w", encoding='utf-8') as f:
            f.write(html_output)
    except jinja2.exceptions.TemplateError as e:
        error_message = f"Template error when generating report: {str(e)}"
        # Create a basic HTML error report instead
        with open(report_path, "w", encoding='utf-8') as f:
            f.write(f"<html><body><h1>Error Generating Report</h1><p>{error_message}</p></body></html>")
        raise AssertionError(error_message)

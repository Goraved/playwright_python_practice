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
        for index, mark in enumerate(item.own_markers):
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
                            if hasattr(param, 'values') and param.id == param_value.split('-')[index]:
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
    Create a comprehensive HTML-formatted test run summary with actionable insights.

    Delivers a complete overview with:
    - Clear and engaging information about test results
    - Useful recommendations based on test outcomes
    - Detailed analysis across different test aspects
    - Practical next steps for the team
    """

    if not results:
        return "🚨 <b>ALERT: No Test Results Found!</b> 🚨<br>Critical issue detected &ndash; test results are missing. This could be due to execution failures, wrong report location, or system issues. <b>Investigation needed immediately!</b>"

    # --- 📊 Overall Summary Stats ---
    total_tests = stats['total']
    pass_rate = (stats['passed'] / total_tests * 100) if total_tests > 0 else 0

    # --- 🎯 Overall Assessment Based on Pass Rate ---
    if pass_rate == 100:
        situation_message = "🌟 Complete Success: Every single test passed successfully. Excellent work!"
    elif pass_rate >= 95:
        situation_message = "🏆 Outstanding Result: The vast majority of tests passed successfully!"
    elif pass_rate >= 90:
        situation_message = "🎉 Very Good Result: High pass rate with just a few issues to address."
    elif pass_rate >= 80:
        situation_message = "👍 Good Result: Decent pass rate, though improvements are needed."
    elif pass_rate >= 60:
        situation_message = "⚠️ Attention Required: Multiple test failures detected; investigation needed."
    else:
        situation_message = "🚨 Critical Situation: Very low pass rate; requires immediate investigation!"

    earliest_start_time = stats['start_time']
    latest_end_time = stats['end_time']
    run_duration_seconds = stats['total_duration']
    formatted_runtime = time.strftime("%H:%M:%S", time.gmtime(run_duration_seconds))

    slow_tests = [r for r in results if r['duration'] > slow_test_threshold_sec]
    rerun_tests = [r for r in results if r['outcome'] == "rerun"]

    high_level_summary = (
        f"📊 <b>Test Run Summary</b> 📊<br>"
        f"- <b>Tests Executed:</b> {total_tests} tests were run in this session<br>"
        f"- <b>Pass Rate:</b> {pass_rate:.1f}% &ndash; Our key quality metric<br>"
        f"- <b>Duration:</b> {formatted_runtime} &ndash; Total execution time<br>"
        f"- <b>Main Issues:</b> {stats['failed']} failures, {stats['error']} errors, {stats['rerun']} reruns, {len(slow_tests)} slow tests. Priority items to address."
    )

    # --- 📈 Status Details: Breaking Down Test Results ---
    total_failing = stats['failed'] + stats['error'] + stats['xfailed']
    status_messages = []

    if total_failing == 0 and stats['passed'] == total_tests:
        status_messages.append(
            "🏆 <b>Perfect Score: All Tests Passed!</b> 🏆<br>Flawless execution! A rare achievement to celebrate, but stay vigilant and keep improving!")
    else:
        status_messages.append("🔎 <b>Test Status Breakdown:</b>")
        status_messages.extend([
            f"  ✅ <b>{stats['passed']} Passed Tests ({pass_rate:.1f}%):</b> The foundation of our test coverage. Continue to maintain and expand.",
            f"  ❌ <b>{stats['failed']} Failed Tests ({(stats['failed'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Highest priority issues &ndash; each failure represents an area for improvement.",
            f"  ⚠️ <b>{stats['error']} Errors ({(stats['error'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Need assessment. Focus on environment issues and test setup problems.",
            f"  🔄 <b>{stats['rerun']} Rerun Tests ({(stats['rerun'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Reruns often indicate intermittent issues. Important to analyze patterns.",
            f"  ⏩ <b>{stats['skipped']} Skipped Tests ({(stats['skipped'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Evaluate skipped tests. Are we missing important validations?",
            f"  ❎ <b>{stats['xfailed']} Expected Failures ({(stats['xfailed'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Known issues to prioritize for future fixes.",
            f"  ❗ <b>{stats['xpassed']} Unexpected Passes ({(stats['xpassed'] / total_tests * 100 if total_tests else 0):.1f}%):</b> Surprising results &ndash; verify if these represent genuine improvements."
        ])

        if stats['failed'] + stats['error'] + stats['rerun'] > 0:
            status_messages.append(
                "<br>⚡ <b>Priority Actions:</b> Focus on fixing failures, errors, and tests needing reruns. These represent our main quality blockers.")

    # --- ⏱️ Performance Analysis: Finding Speed Issues ---
    fast_tests = sorted(results, key=lambda x: x['duration'])
    min_test = fast_tests[0] if fast_tests else None
    max_test = fast_tests[-1] if fast_tests else None

    min_test_msg = (
        f"🥇 <b>Fastest Test:</b> <code>{min_test['nodeid']}</code> &ndash; completed in only {min_test['duration']:.2f} seconds!"
        if min_test else "No test duration data available."
    )

    max_test_msg = (
        f"🐌 <b>Slowest Test:</b> <code>{max_test['nodeid']}</code> &ndash; required {max_test['duration']:.2f} seconds. Consider optimizing this test!"
        if max_test else "No test duration data available."
    )

    # Calculate slow tests percentage
    slow_tests_percent = (len(slow_tests) / total_tests * 100) if total_tests > 0 else 0
    slow_test_stats = (
        f"⏱️ <b>Slow Test Analysis:</b> {len(slow_tests)} tests ({slow_tests_percent:.1f}%) exceeded {slow_test_threshold_sec / 60:.0f} minutes runtime."
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
            f"⏱️ <b>{len(slow_tests)} Slow Tests Identified (&gt;{slow_test_threshold_sec / 60:.0f} min):</b> Performance improvements needed!"]
        for category, tests in categorized_slow_tests.items():
            if tests:
                example_test_name = tests[0]['nodeid'].split("::")[-1] if "::" in tests[0]['nodeid'] else tests[0][
                    'nodeid']
                optimization_msg_lines.append(
                    f"  &ndash; <b>{category}:</b> {len(tests)} slow tests found (e.g., <code>{example_test_name}</code>...). Potential area for optimization.")

        optimization_msg_lines.append("<br>🚀 <b>Performance Improvement Strategies:</b><br>"
                                      "&ndash; <b>Profiling:</b> Identify performance bottlenecks through detailed timing analysis<br>"
                                      "&ndash; <b>Parallelization:</b> Implement concurrent execution where possible<br>"
                                      "&ndash; <b>Mock Objects:</b> Replace slow dependencies with faster test doubles<br>"
                                      "&ndash; <b>Code Optimization:</b> Eliminate redundant code and improve algorithmic efficiency<br>"
                                      "&ndash; <b>Environment Tuning:</b> Optimize test environment and data for better performance")
        optimization_msg = "<br>".join(optimization_msg_lines)

    else:
        optimization_msg = "🏎️💨 <b>Performance Excellence!</b> All tests completed within acceptable time limits!"

    # --- 🔍 Slow Methods Analysis: Finding Method-Level Bottlenecks ---
    if 'slow_functions' in stats and stats['slow_functions']:
        slow_functions_lines = [
            "<br>🐢 <b>Slow Methods Analysis:</b> Functions consistently taking too long across tests:"
        ]

        # Sort slow functions by frequency (most occurrences first)
        sorted_slow_funcs = sorted(stats['slow_functions'].items(), key=lambda x: x[1], reverse=True)

        for func_name, occurrence_count in sorted_slow_funcs:
            slow_functions_lines.append(
                f"  &ndash; <code>{func_name}</code>: slow in <b>{occurrence_count}</b> test(s). Optimization candidate!"
            )

        if sorted_slow_funcs:
            slow_functions_lines.append(
                "<br>🔧 <b>Method Optimization Recommendations:</b><br>"
                "&ndash; <b>Logic Review:</b> Check for redundant code or inefficient algorithms<br>"
                "&ndash; <b>Wait Logic:</b> Optimize explicit waits and timeout conditions<br>"
                "&ndash; <b>Implement Caching:</b> Store results of expensive operations<br>"
                "&ndash; <b>Parallel Execution:</b> Consider running operations concurrently when possible"
            )

        slow_functions_msg = "<br>".join(slow_functions_lines)
    else:
        slow_functions_msg = "📊 <b>Method Performance Analysis:</b> No consistently slow functions identified across tests."

    # --- 🔁 Rerun Analysis: Understanding Repeated Test Attempts ---
    if rerun_tests:
        rerun_msg_lines = [
            f"🔄 <b>Rerun Summary:</b> {len(rerun_tests)} tests required reruns during this execution.",
            "<br>🤔 <b>Rerun Details:</b>",
            f"  &ndash; <b>Rerun Percentage:</b> {len(rerun_tests) / total_tests:.1%} of tests needed multiple attempts.",
            f"  &ndash; <b>Maximum Attempts:</b> Most challenging test, <code>{max(rerun_tests, key=lambda t: t.get('rerun_attempts', 0))['nodeid']}</code>, required {max(t.get('rerun_attempts', 0) for t in rerun_tests)} attempts.<br>",
            "💡 <b>Addressing Flaky Tests:</b>",
            "  &ndash; Common causes include network instability, timing issues, or intermittent service problems.",
            "  &ndash; Fix strategies: improve wait mechanisms, enhance synchronization, and ensure stable test environments.",
        ]
        rerun_msg = "<br>".join(rerun_msg_lines)
    else:
        rerun_msg = "🎯 <b>First-Time Success!</b> No tests required reruns - all passed on their initial execution!"

    # --- 📋 Final Assessment and Summary ---
    summary = (
            f"<h4>🔍 <b>Test Run Analysis</b> 🔍</h1><br>"
            f"{situation_message}<br>"
            f"{high_level_summary}"
            f"<hr>"
            f"<h5>1️⃣ <b>Execution Details:</b></h5>"
            f"- ⏰ Start Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(earliest_start_time))}<br>"
            f"- ⏰ End Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest_end_time))}<br>"
            f"- 📈 Total Duration: {formatted_runtime}<br>"
            f"<br><h5>2️⃣ <b>Test Result Details:</b></h5>" + "<br>".join(status_messages) + "<br>"
                                                                                             f"<br><h5>3️⃣ <b>Performance Analysis:</b></h5>"
                                                                                             f"- {slow_test_stats}<br>"
                                                                                             f"- {min_test_msg}<br>"
                                                                                             f"- {max_test_msg}<br>"
                                                                                             f"- {optimization_msg}<br>"
                                                                                             f"- {slow_functions_msg}<br>"
                                                                                             f"<br><h5>4️⃣ <b>Rerun Analysis:</b></h5><br>"
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

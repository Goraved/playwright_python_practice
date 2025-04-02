"""
result_handler.py

Handles the test result processing logic for pytest fixtures and hooks.
This module separates the test reporting logic from conftest.py to improve maintainability.
"""

import base64
from pathlib import Path
from typing import Any, Optional

import pytest
from _pytest.nodes import Item
from _pytest.reports import TestReport
from _pytest.runner import CallInfo
from playwright.sync_api import Page

from html_reporter.report_handler import TestResult, save_test_result


class ResultHandler:
    """
    Handles the processing, tracking, and reporting of test results.

    This class encapsulates the logic previously contained in pytest_runtest_makereport,
    making it more maintainable and modular.
    """

    def __init__(self, config: Any) -> None:
        """
        Initialize the test result handler.

        Args:
            config: The pytest config object for storing state
        """
        self.config = config

        # Create a place to store test status data if it doesn't exist
        if not hasattr(self.config, '_aqa_test_status'):
            self.config._aqa_test_status = {}

        # Create a place to store test timing data if it doesn't exist
        if not hasattr(self.config, '_aqa_test_timing'):
            self.config._aqa_test_timing = {}

        # Keep track of how many screenshots we've taken
        if not hasattr(self.config, 'screenshots_amount'):
            self.config.screenshots_amount = 0

    def process_test_result(self, item: Item, call: CallInfo, report: TestReport) -> None:
        """
        Process a test result from the pytest_runtest_makereport hook.

        Main entry point for test result processing. This method orchestrates the entire
        result handling process.

        Args:
            item: The pytest test item being run
            call: Information about the test function call
            report: The pytest report object
        """
        # Get or create test status tracking
        status_key, status = self._get_test_status(item)

        # Track timing for this phase
        self._track_phase_timing(item, report, status_key)

        # Update phase information

        status[report.when] = report.outcome
        if report.outcome == "failed" and call.excinfo:
            if call.excinfo.type not in (AssertionError, pytest.fail.Exception):
                status[report.when] = "error"

        # Process xfail status in call phase
        if report.when == 'call' and hasattr(report, 'wasxfail'):
            self._process_xfail_status(status, report)

        # Process soft assertions in call phase
        if report.when == 'call' and hasattr(item, "_soft_assert"):
            self._process_soft_assertions(item, report, status)

        # Create report if test is complete
        is_test_complete = self._is_test_complete(report, status)
        if is_test_complete and not status['final_result_reported']:
            self._create_final_report(item, call, report, status, status_key)

        # Store the report for this phase with execution count in key
        self._store_phase_report(item, report)

    def _track_phase_timing(self, item: Item, report: TestReport, status_key: str) -> None:
        """
        Track timing information for each test phase as it occurs.

        This method runs during each phase of the test and records start time and duration.

        Args:
            item: The pytest test item
            report: The pytest report object
            status_key: The status key for this test
        """
        # Initialize timing tracking for this test if not already done
        if not self.config._aqa_test_timing.get(status_key):
            self.config._aqa_test_timing[status_key] = {
                'start_time': None,
                'total_duration': 0.0,
                'phase_durations': {
                    'setup': 0.0,
                    'call': 0.0,
                    'teardown': 0.0
                }
            }

        timing = self.config._aqa_test_timing[status_key]

        # Record start time if this is the first phase we've seen
        if hasattr(report, 'start'):
            if timing['start_time'] is None or report.start < timing['start_time']:
                timing['start_time'] = report.start

        # Add this phase's duration to the appropriate phase and total
        if hasattr(report, 'duration'):
            timing['phase_durations'][report.when] = report.duration
            timing['total_duration'] += report.duration

    def _get_test_status(self, item: Item) -> tuple[str, dict[str, Any]]:
        """
        Get or create test status tracking data.

        Creates a unique key for tracking test status based on the nodeid and execution count,
        and ensures a status dictionary exists for this test.

        Args:
            item: The pytest test item

        Returns:
            tuple: (status_key, status_dict) for the test
        """
        nodeid = item.nodeid
        execution_count = getattr(item, 'execution_count', 1)
        status_key = f"{nodeid}:{execution_count}"

        # Initialize tracking for this test attempt if not already done
        if not self.config._aqa_test_status.get(status_key):
            self.config._aqa_test_status[status_key] = {
                'setup': None,
                'call': None,
                'teardown': None,
                'final_result_reported': False,
                'execution_count': execution_count,
                'xfail_status': None  # Track xfail status separately
            }

        return status_key, self.config._aqa_test_status[status_key]

    @staticmethod
    def _process_xfail_status(status: dict[str, Any], report: TestReport) -> None:
        """
        Process and store xfail status information.

        This method runs during the call phase to capture and store the xfail status
        and reason for later use in reporting.

        Args:
            status: The test status dictionary
            report: The pytest report object
        """
        # Store xfail status based on whether the test passed unexpectedly or failed as expected
        status['xfail_status'] = 'xfailed' if report.outcome != 'passed' else 'xpassed'

        # Store xfail reason for later use in reporting
        status['xfail_reason'] = report.wasxfail

    @staticmethod
    def _process_soft_assertions(item: Item, report: TestReport, status: dict[str, Any]) -> None:
        """
        Process soft assertions and update report accordingly.

        This method runs during the call phase when soft assertions are present. It updates
        the report outcome and stores failure information for later use.

        Args:
            item: The pytest test item
            report: The pytest report object
            status: The test status dictionary
        """
        soft_assert = item._soft_assert
        if soft_assert.has_failures():
            # If this is also an xfail test, mark it appropriate
            if hasattr(report, "wasxfail"):
                status['xfail_status'] = 'xfailed'
                # Important: Modify the report to ensure pytest itself sees this as xfailed
                report.outcome = 'skipped'  # pytest internally uses 'skipped' for xfailed tests
            else:
                # Regular test with soft assertion failures
                report.outcome = 'failed'
                status['call'] = 'failed'

            # Add soft assert failures to report
            failures = "\n".join(soft_assert.get_failures())
            report.longrepr = f"Soft assert failures ({len(soft_assert.get_failures())}):\n{failures}"

    @staticmethod
    def _is_test_complete(report: TestReport, status: dict[str, Any]) -> bool:
        """
        Determine if a test is complete and ready for final reporting.

        A test is considered complete if any of the following are true:
        1. The teardown phase has completed (success or failure)
        2. The setup phase failed
        3. The call phase failed after a successful setup

        Args:
            report: The pytest report object
            status: The test status dictionary

        Returns:
            bool: True if the test is complete, False otherwise
        """
        return (
                report.when == 'teardown' or
                (report.when == 'setup' and report.outcome != 'passed') or
                (report.when == 'call' and status['setup'] == 'passed' and report.outcome != 'passed')
        )

    @staticmethod
    def _store_phase_report(item: Item, report: TestReport) -> None:
        """
        Store the phase report for later reference.

        Attaches the report to the test item with a phase-specific key
        to allow retrieving phase-specific data later.

        Args:
            item: The pytest test item
            report: The pytest report object
        """
        execution_count = getattr(item, 'execution_count', 1)
        phase_key = f"_report_{report.when}_{execution_count}"
        setattr(item, phase_key, report)

    def _create_final_report(self, item: Item, call: CallInfo, report: TestReport, status: dict[str, Any],
                             status_key: str) -> None:
        """
        Create the final test report when a test is complete.

        This method is the main orchestrator for creating the final test result.

        Args:
            item: The pytest test item being run
            call: Information about the test function call
            report: The pytest report object
            status: The test status dictionary
            status_key: The status key for this test
        """
        # Mark this attempt as reported
        status['final_result_reported'] = True

        # Determine outcome
        outcome, error_phase = self._determine_outcome(report, status)

        # Handle xfail status from soft assertions
        if hasattr(item, "_soft_assert"):
            outcome, error_phase = self._update_outcome_for_soft_assertions(
                item, report, status, outcome, error_phase)

        # Create a TestResult object
        result = self._create_test_result(item, outcome, report)
        result.error_phase = error_phase

        # Use the timing information we've tracked in real-time
        timing = self.config._aqa_test_timing.get(status_key, {})
        if timing.get('start_time') is not None:
            result.timestamp = timing['start_time']
        if 'phase_durations' in timing and timing['phase_durations'].get('call', 0) > 0:
            result.phase_durations = timing['phase_durations']
            result.duration = timing['total_duration']

        if report.outcome == 'skipped' and hasattr(report, 'wasxfail'):
            # Existing xfail handling
            status['xfail_status'] = 'xfailed'
            status['xfail_reason'] = report.wasxfail
        elif report.outcome == 'skipped':
            # New code to capture skip reason
            if hasattr(report, 'longrepr'):
                skip_reason = report.longrepr[-1].replace('Skipped: ', '')
                result.skip_reason = skip_reason

        # Process expected failures
        self._process_expected_failures(report, result, status, outcome)

        # Check for rerun status
        max_reruns = getattr(self.config.option, 'reruns', 0) or 0
        if status['execution_count'] <= max_reruns and outcome in ('failed', 'error') and outcome != 'xfailed':
            result.outcome = "rerun"

        # Process error information
        if result.outcome in ("failed", "error", "xfailed", "rerun"):
            self._process_error_info(item, call, report, result, result.outcome)

        # Collect all logs
        self._collect_logs(item, result, status)

        # Capture test metadata
        self._capture_metadata(item, result)

        # Save the test result
        save_test_result(result, self._get_report_dir())

    @staticmethod
    def _determine_outcome(report: TestReport, status: dict[str, Any]) -> tuple[str, Optional[str]]:
        """
        Determine the final outcome and error phase for a test.

        This method uses a series of rules to determine the final outcome based on
        the status of each test phase and any xfail status.

        Args:
            report: The pytest report object
            status: The test status dictionary

        Returns:
            tuple: (outcome, error_phase) where outcome is the test result
                  (passed, failed, skipped, xfailed, xpassed, etc.) and
                  error_phase is the phase where failure occurred (setup, call, teardown)
        """
        # Check for xfail status from call phase
        if status['xfail_status']:
            return status['xfail_status'], 'call'

        # Determine outcome and error phase based on test status
        for phase in ['setup', 'call', 'teardown']:
            if status[phase] in ['failed', 'error']:
                return status[phase], phase

        # Handle passed and skipped outcomes
        if status['call'] == 'passed':
            outcome = 'xpassed' if hasattr(report, 'wasxfail') else 'passed'
            return outcome, None
        if status['call'] == 'skipped':
            outcome = 'xfailed' if hasattr(report, 'wasxfail') else 'skipped'
            return outcome, None

        # Default case
        return report.outcome, report.when if report.outcome == 'failed' else None

    @staticmethod
    def _update_outcome_for_soft_assertions(
            item: Item, report: TestReport, status: dict[str, Any],
            outcome: str, error_phase: Optional[str]
    ) -> tuple[str, str]:
        """
        Update the outcome and error phase based on soft assertions.

        Modifies the outcome and error phase if there are soft assertion failures,
        taking into account xfail status.

        Args:
            item: The pytest test item
            report: The pytest report object
            status: The test status dictionary
            outcome: The current outcome
            error_phase: The current error phase

        Returns:
            tuple: (updated_outcome, updated_error_phase)
        """
        soft_assert = item._soft_assert
        if soft_assert.has_failures():
            failures = "\n".join(soft_assert.get_failures())
            report.longrepr = f"Soft assert failures ({len(soft_assert.get_failures())}):\n{failures}"
            report.error = f"Soft assert failures ({len(soft_assert.get_failures())}):\n{failures}"
            error_phase = "call"

            # Use the previously stored xfail status if available
            if status['xfail_status']:
                outcome = status['xfail_status']
            else:
                outcome = "failed"

        return outcome, error_phase

    @staticmethod
    def _create_test_result(item: Item, outcome: str, report: TestReport) -> TestResult:
        """
        Create a TestResult object for the test.

        Initializes and configures a TestResult object with the appropriate outcome
        and metadata.

        Args:
            item: The pytest test item
            outcome: The test outcome
            report: The pytest report object

        Returns:
            TestResult: The created test result object
        """
        # Create the result with the determined outcome
        result = TestResult(item, outcome, getattr(report, 'duration', 0), getattr(report, 'phase_durations', {}),
                            timestamp=report.start)
        result.execution_count = getattr(item, 'execution_count', 1)

        # Ensure xfail/xpass status is preserved in the result object
        if outcome in ('xfailed', 'xpassed'):
            result.was_xfail = True

        return result

    @staticmethod
    def _process_expected_failures(
            report: TestReport, result: TestResult, status: dict[str, Any], outcome: str
    ) -> None:
        """
        Process expected failures (xfail) metadata.

        Handles xfail and xpass status, setting appropriate metadata and ensuring
        the outcome is correctly reflected in the result.

        Args:
            report: The pytest report object
            result: The TestResult object
            status: The test status dictionary
            outcome: The test outcome
        """
        # Process expected failure metadata for reporting
        if hasattr(report, "wasxfail") or 'xfail_reason' in status:
            # Make sure the outcome is correctly set for xfail tests
            if outcome not in ('xfailed', 'xpassed') and (hasattr(report, "wasxfail") or status.get('xfail_status')):
                if outcome == 'passed':
                    result.outcome = 'xpassed'
                elif outcome in ('failed', 'skipped'):
                    result.outcome = 'xfailed'

            # Prefer xfail reason stored during call phase
            if 'xfail_reason' in status:
                result.wasxfail = status['xfail_reason']
            else:
                result.wasxfail = getattr(report, "wasxfail", None)

            if "reason" in result.metadata:
                result.metadata["xfail_reason"] = result.metadata["reason"]
            elif result.wasxfail and ": " in result.wasxfail:
                result.metadata["xfail_reason"] = result.wasxfail.split(": ", 1)[1]
            else:
                result.metadata["xfail_reason"] = result.wasxfail

    def _process_error_info(
            self, item: Item, call: CallInfo, report: TestReport,
            result: TestResult, outcome: str
    ) -> None:
        """
        Process error information for failed tests.

        Handles detailed error information, screenshots, and exception details
        for tests that have failed, errored, or been marked as xfailed.

        Args:
            item: The pytest test item
            call: The CallInfo object
            report: The pytest report object
            result: The TestResult object
            outcome: The test outcome
        """
        # Differentiate between assertion failures and infrastructure errors
        if outcome == "failed" and call.excinfo:
            if call.excinfo.type not in (AssertionError, pytest.fail.Exception):
                result.outcome = "error"

        # Capture screenshot for failures if using Playwright
        page = item.funcargs.get("page")
        if page and outcome != "rerun":
            self._capture_screenshot(page, result)

        # Record final page URL for Playwright tests
        if page and hasattr(page, 'url'):
            result.metadata["end_url"] = page.url

        # Extract detailed exception information
        if hasattr(report, "longrepr"):
            result.error = str(report.longrepr)
            try:
                if hasattr(report.longrepr, "reprtraceback") and hasattr(report.longrepr.reprtraceback,
                                                                         "reprentries"):
                    result.exception_type = report.longrepr.reprtraceback.reprentries[-1].reprfileloc.message
                elif hasattr(report.longrepr, "reprtraceback") and hasattr(report.longrepr.reprtraceback,
                                                                           "reprcrash"):
                    result.exception_type = report.longrepr.reprtraceback.reprcrash.typename
            except Exception:
                result.exception_type = ""

    def _capture_screenshot(self, page: Page, result: TestResult) -> None:
        """
        Capture a screenshot if available and add it to the result.

        Takes a screenshot of the current page state when a test fails and
        attaches it to the test result for debugging.

        Args:
            page: The Playwright page object
            result: The TestResult object
        """
        try:
            if self.config.screenshots_amount < 5:
                screenshot = page.screenshot(
                    type="jpeg",
                    quality=60,  # Reduce quality to decrease file size
                    scale="css",  # Use CSS pixels instead of device pixels
                    full_page=False  # Only capture the visible viewport
                )
                result.screenshot = base64.b64encode(screenshot).decode("utf-8")
                self.config.screenshots_amount += 1
            else:
                print('Too many screenshots')
        except Exception as e:
            result.error = f"Failed to capture screenshot: {str(e)}"

    def _collect_logs(self, item: Item, result: TestResult, status: dict[str, Any]) -> None:
        """
        Collect all logs from the test phases.

        Gathers logs, stderr, and stdout from all test phases and attaches them
        to the test result for debugging.

        Args:
            item: The pytest test item
            result: The TestResult object
            status: The test status dictionary
        """
        # Collect test logs
        if hasattr(item, "test_logs"):
            result.logs = getattr(item, "test_logs", [])
        else:
            result.logs = []

        if hasattr(item, "execution_log"):
            result.logs.extend([log[1] for log in sorted(item.execution_log, key=lambda x: x[0])])

        # Capture pytest's built-in log captures
        result.caplog = ""
        result.capstderr = ""
        result.capstdout = ""

        # Track logs we've already seen to avoid duplication
        seen_logs = set()
        seen_stderr = set()
        seen_stdout = set()

        # Now collect logs from all phases
        for when in ['setup', 'call', 'teardown']:

            # Get phase report
            phase_key = f"_report_{when}_{status['execution_count']}"

            if hasattr(item, phase_key):
                self._collect_phase_logs(when, getattr(item, phase_key), result,
                                         seen_logs, seen_stderr, seen_stdout)

        # Clean up empty log sections
        if not result.caplog.strip():
            result.caplog = None
        if not result.capstderr.strip():
            result.capstderr = None
        if not result.capstdout.strip():
            result.capstdout = None

    @staticmethod
    def _collect_phase_logs(
            phase: str, phase_report: TestReport, result: TestResult,
            seen_logs: set[str], seen_stderr: set[str], seen_stdout: set[str]
    ) -> None:
        """
        Collect logs from a specific test phase.

        Gathers logs, stderr, and stdout from a specific test phase,
        avoiding duplication.

        Args:
            phase: The test phase name
            phase_report: The report for the phase
            result: The TestResult object
            seen_logs: Set of already seen logs
            seen_stderr: Set of already seen stderr entries
            seen_stdout: Set of already seen stdout entries
        """
        # Process caplog if it exists and has content
        if hasattr(phase_report, "caplog") and phase_report.caplog:
            if phase_report.caplog.strip() and phase_report.caplog not in seen_logs:
                if result.caplog:
                    result.caplog += f"\n--- {phase} phase logs ---\n"
                else:
                    result.caplog = f"--- {phase} phase logs ---\n"
                result.caplog += phase_report.caplog
                seen_logs.add(phase_report.caplog)

        # Process stderr if it exists and has content
        if hasattr(phase_report, "capstderr") and phase_report.capstderr:
            if phase_report.capstderr.strip() and phase_report.capstderr not in seen_stderr:
                if result.capstderr:
                    result.capstderr += f"\n--- {phase} phase stderr ---\n"
                else:
                    result.capstderr = f"--- {phase} phase stderr ---\n"
                result.capstderr += phase_report.capstderr
                seen_stderr.add(phase_report.capstderr)

        # Process stdout if it exists and has content
        if hasattr(phase_report, "capstdout") and phase_report.capstdout:
            if phase_report.capstdout.strip() and phase_report.capstdout not in seen_stdout:
                if result.capstdout:
                    result.capstdout += f"\n--- {phase} phase stdout ---\n"
                else:
                    result.capstdout = f"--- {phase} phase stdout ---\n"
                result.capstdout += phase_report.capstdout
                seen_stdout.add(phase_report.capstdout)

    @staticmethod
    def _capture_metadata(item: Item, result: TestResult) -> None:
        """
        Capture test metadata.

        Adds test-specific metadata like case links and IDs to the test result.

        Args:
            item: The pytest test item
            result: The TestResult object
        """
        if hasattr(item, "test_case_link"):
            result.metadata["case_link"] = item.test_case_link
        if hasattr(item, "test_case_id"):
            result.metadata["case_id"] = item.test_case_id

    @staticmethod
    def _get_report_dir() -> Path:
        """
        Get the directory for storing reports.

        Creates the reports directory if it doesn't exist.

        Returns:
            Path: The report directory
        """
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)
        return report_dir

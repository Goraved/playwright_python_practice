import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module to test with the new naming convention
from html_reporter.result_handler import ResultHandler


@pytest.mark.unit
class TestResultHandler:
    """Unit tests for the ResultHandler class."""

    @pytest.fixture
    def mock_config(self):
        """Fixture for a mock pytest config."""
        config = MagicMock()
        config._aqa_test_status = {}
        config._aqa_test_timing = {}
        config.screenshots_amount = 0
        return config

    @pytest.fixture
    def handler(self, mock_config):
        """Fixture for a ResultHandler instance."""
        return ResultHandler(mock_config)

    @pytest.fixture
    def mock_item(self):
        """Fixture for a mock pytest item."""
        item = MagicMock()
        item.nodeid = "tests/test_example.py::test_function"
        item.execution_count = 1
        # Mock the test function
        test_func = MagicMock()
        test_func.__doc__ = "Test function docstring"
        item.obj = test_func
        item.function = test_func
        # For markers extraction
        marker1 = MagicMock()
        marker1.name = "smoke"
        item.iter_markers.return_value = [marker1]
        return item

    @pytest.fixture
    def mock_call(self):
        """Fixture for a mock pytest CallInfo."""
        call = MagicMock()
        call.excinfo = None
        return call

    @pytest.fixture
    def mock_report(self):
        """Fixture for a mock pytest TestReport."""
        report = MagicMock()
        report.when = "call"
        report.outcome = "passed"
        report.duration = 0.5
        report.start = time.time()
        return report

    def test_init(self, mock_config):
        """Test the initialization of ResultHandler."""
        handler = ResultHandler(mock_config)

        # Check that the handler is initialized with the config
        assert handler.config == mock_config

        # Check that the config properties are initialized
        assert hasattr(mock_config, '_aqa_test_status')
        assert hasattr(mock_config, '_aqa_test_timing')
        assert hasattr(mock_config, 'screenshots_amount')
        assert mock_config.screenshots_amount == 0

    def test_get_test_status(self, handler, mock_item):
        """Test the _get_test_status method."""
        # Call the method
        status_key, status = handler._get_test_status(mock_item)

        # Check that the key is correctly formed
        expected_key = f"{mock_item.nodeid}:{mock_item.execution_count}"
        assert status_key == expected_key

        # Check that the status dict is correctly initialized
        assert status['setup'] is None
        assert status['call'] is None
        assert status['teardown'] is None
        assert status['final_result_reported'] is False
        assert status['execution_count'] == mock_item.execution_count
        assert status['xfail_status'] is None

        # Check that the status is stored in the config
        assert handler.config._aqa_test_status[status_key] == status

    def test_track_phase_timing(self, handler, mock_item, mock_report):
        """Test the _track_phase_timing method."""
        # Setup
        status_key = f"{mock_item.nodeid}:{mock_item.execution_count}"
        test_start_time = time.time()
        mock_report.start = test_start_time
        mock_report.duration = 1.5

        # Call the method
        handler._track_phase_timing(mock_item, mock_report, status_key)

        # Check that the timing info is initialized and populated
        assert status_key in handler.config._aqa_test_timing
        timing = handler.config._aqa_test_timing[status_key]
        assert timing['start_time'] == test_start_time
        assert timing['total_duration'] == 1.5

        # Test adding another phase
        mock_report.start = test_start_time + 2
        mock_report.duration = 0.5

        # Call the method again
        handler._track_phase_timing(mock_item, mock_report, status_key)

        # The start time should remain the earlier one, but duration should accumulate
        timing = handler.config._aqa_test_timing[status_key]
        assert timing['start_time'] == test_start_time  # Unchanged
        assert timing['total_duration'] == 2.0  # 1.5 + 0.5

    def test_process_xfail_status(self, handler):
        """Test the _process_xfail_status method."""
        # Setup
        status = {
            'xfail_status': None,
            'xfail_reason': None
        }
        report = MagicMock()
        report.outcome = 'failed'
        report.wasxfail = 'expected to fail'

        # Call the method
        handler._process_xfail_status(status, report)

        # Check that the status and reason are set correctly
        assert status['xfail_status'] == 'xfailed'
        assert status['xfail_reason'] == 'expected to fail'

        # Test with passing test
        status = {
            'xfail_status': None,
            'xfail_reason': None
        }
        report.outcome = 'passed'

        # Call the method
        handler._process_xfail_status(status, report)

        # Check that it's marked as xpassed
        assert status['xfail_status'] == 'xpassed'
        assert status['xfail_reason'] == 'expected to fail'

    def test_soft_assert_failed(self, handler, mock_item, mock_report):
        """Test when a soft assert fails (non-xfail) with no wasxfail attribute on the report."""
        status = {'call': 'passed', 'xfail_status': None}
        soft_assert = MagicMock()
        soft_assert.has_failures.return_value = True
        soft_assert.get_failures.return_value = ["Failure: condition not met"]
        mock_item._soft_assert = soft_assert

        # Ensure that mock_report has no attribute 'wasxfail'
        if hasattr(mock_report, 'wasxfail'):
            delattr(mock_report, 'wasxfail')
        assert not hasattr(mock_report, 'wasxfail')

        handler._process_soft_assertions(mock_item, mock_report, status)

        assert status['call'] == 'failed'
        assert mock_report.outcome == 'failed'
        assert "Soft assert failures" in mock_report.longrepr

    def test_soft_assert_passed(self, handler, mock_item, mock_report):
        """Test when soft assertions pass (non-xfail)."""
        status = {'call': 'passed', 'xfail_status': None}
        soft_assert = MagicMock()
        soft_assert.has_failures.return_value = False
        soft_assert.get_failures.return_value = []
        mock_item._soft_assert = soft_assert

        handler._process_soft_assertions(mock_item, mock_report, status)

        assert status['call'] == 'passed'
        assert mock_report.outcome == 'passed'
        # Optionally, you can check that no failure messages appear:
        assert "Soft assert failures" not in mock_report.longrepr

    def test_soft_assert_failed_with_xfail(self, handler, mock_item, mock_report):
        """Test a soft assert failure in an xfail scenario."""
        status = {'call': 'passed', 'xfail_status': None}
        soft_assert = MagicMock()
        soft_assert.has_failures.return_value = True
        soft_assert.get_failures.return_value = ["Expected failure with xfail"]
        mock_item._soft_assert = soft_assert
        mock_report.wasxfail = 'expected to fail'

        handler._process_soft_assertions(mock_item, mock_report, status)

        # In an xfail scenario, a failure should mark the status as xfailed.
        assert status['xfail_status'] == 'xfailed'
        # Pytest normally reports xfailed tests as skipped.
        assert mock_report.outcome == 'skipped'

    def test_soft_assert_passed_with_xfail(self, handler, mock_item, mock_report):
        """Test when soft assertions pass but the test is marked as xfail (unexpected pass)."""
        status = {'call': 'passed', 'xfail_status': None}
        soft_assert = MagicMock()
        soft_assert.has_failures.return_value = False
        soft_assert.get_failures.return_value = []
        mock_item._soft_assert = soft_assert
        mock_report.wasxfail = 'expected to fail'

        handler._process_soft_assertions(mock_item, mock_report, status)

        # When a test is marked xfail but passes, it should be noted as an unexpected pass.
        assert not status['xfail_status']
        assert status['call'] == 'passed'
        # Typically, pytest will mark an xpass as a failure.
        assert mock_report.outcome == 'passed'

    def test_is_test_complete(self, handler):
        """Test the _is_test_complete method."""
        # Setup
        status = {'setup': 'passed', 'call': None, 'teardown': None}

        # Test teardown phase completion
        report = MagicMock()
        report.when = 'teardown'
        report.outcome = 'passed'
        assert handler._is_test_complete(report, status) is True

        # Test setup phase failure
        report.when = 'setup'
        report.outcome = 'failed'
        assert handler._is_test_complete(report, status) is True

        # Test failed call phase after successful setup
        report.when = 'call'
        report.outcome = 'failed'
        assert handler._is_test_complete(report, status) is True

        # Test incomplete test (setup passed, call passed)
        report.when = 'call'
        report.outcome = 'passed'
        assert handler._is_test_complete(report, status) is False

    def test_store_phase_report(self, handler, mock_item, mock_report):
        """Test the _store_phase_report method."""
        # Call the method
        handler._store_phase_report(mock_item, mock_report)

        # Check that the report is stored with the correct key
        phase_key = f"_report_{mock_report.when}_{mock_item.execution_count}"
        assert hasattr(mock_item, phase_key)
        assert getattr(mock_item, phase_key) == mock_report

    def test_determine_outcome(self, handler, mock_report):
        """Test the _determine_outcome method."""
        # Test xfail status
        status = {'xfail_status': 'xfailed', 'setup': 'passed', 'call': 'failed', 'teardown': None}
        outcome, error_phase = handler._determine_outcome(mock_report, status)
        assert outcome == 'xfailed'
        assert error_phase == 'call'

        # Test setup failure
        status = {'xfail_status': None, 'setup': 'failed', 'call': None, 'teardown': None}
        outcome, error_phase = handler._determine_outcome(mock_report, status)
        assert outcome == 'failed'
        assert error_phase == 'setup'

        # Test call failure
        status = {'xfail_status': None, 'setup': 'passed', 'call': 'failed', 'teardown': None}
        outcome, error_phase = handler._determine_outcome(mock_report, status)
        assert outcome == 'failed'
        assert error_phase == 'call'

        # Test teardown failure
        status = {'xfail_status': None, 'setup': 'passed', 'call': 'passed', 'teardown': 'failed'}
        outcome, error_phase = handler._determine_outcome(mock_report, status)
        assert outcome == 'failed'
        assert error_phase == 'teardown'

        # Test passing test
        status = {'xfail_status': None, 'setup': 'passed', 'call': 'passed', 'teardown': 'passed'}
        # Make sure the report doesn't have wasxfail attribute for this test case
        delattr(mock_report, 'wasxfail') if hasattr(mock_report, 'wasxfail') else None
        outcome, error_phase = handler._determine_outcome(mock_report, status)
        assert outcome == 'passed'
        assert error_phase is None

        # Test xpassed test
        status = {'xfail_status': None, 'setup': 'passed', 'call': 'passed', 'teardown': None}
        mock_report.wasxfail = 'expected to fail'
        outcome, error_phase = handler._determine_outcome(mock_report, status)
        assert outcome == 'xpassed'
        assert error_phase is None

        # Test skipped test
        status = {'xfail_status': None, 'setup': 'passed', 'call': 'skipped', 'teardown': None}
        # Ensure no wasxfail attribute
        delattr(mock_report, 'wasxfail') if hasattr(mock_report, 'wasxfail') else None
        outcome, error_phase = handler._determine_outcome(mock_report, status)
        assert outcome == 'skipped'
        assert error_phase is None

        # Test error status
        status = {'xfail_status': None, 'setup': 'passed', 'call': 'error', 'teardown': None}
        outcome, error_phase = handler._determine_outcome(mock_report, status)
        assert outcome == 'error'
        assert error_phase == 'call'

    @patch('html_reporter.result_handler.TestResult')
    def test_create_test_result(self, mock_test_result_class, handler, mock_item, mock_report):
        """Test the _create_test_result method."""
        # Setup
        outcome = 'passed'
        mock_test_result = MagicMock()
        mock_test_result_class.return_value = mock_test_result

        # Call the method
        result = handler._create_test_result(mock_item, outcome, mock_report)

        # Check that TestResult was called with the correct arguments
        mock_test_result_class.assert_called_once_with(
            mock_item, outcome, mock_report.duration, mock_report.phase_durations, timestamp=mock_report.start
        )

        # Check that the execution count is set
        assert result.execution_count == mock_item.execution_count

        # Test with xfailed outcome
        mock_test_result_class.reset_mock()
        outcome = 'xfailed'

        result = handler._create_test_result(mock_item, outcome, mock_report)

        # Check that was_xfail is set to True
        assert result.was_xfail is True

    def test_update_outcome_for_soft_assertions(self, handler, mock_item, mock_report):
        """Test the _update_outcome_for_soft_assertions method."""
        # Setup
        outcome = 'passed'
        error_phase = None
        status = {'xfail_status': None}

        # Mock the soft assert object with failures
        soft_assert = MagicMock()
        soft_assert.has_failures.return_value = True
        soft_assert.get_failures.return_value = ["Assertion 1 failed", "Assertion 2 failed"]
        mock_item._soft_assert = soft_assert

        # Call the method
        new_outcome, new_error_phase = handler._update_outcome_for_soft_assertions(
            mock_item, mock_report, status, outcome, error_phase
        )

        # Check that the outcome and error phase are updated
        assert new_outcome == "failed"
        assert new_error_phase == "call"
        assert "Soft assert failures" in mock_report.longrepr
        assert "Soft assert failures" in mock_report.error

        # Test with xfail status
        status = {'xfail_status': 'xfailed'}

        new_outcome, new_error_phase = handler._update_outcome_for_soft_assertions(
            mock_item, mock_report, status, outcome, error_phase
        )

        # Check that the outcome is updated to xfailed
        assert new_outcome == "xfailed"
        assert new_error_phase == "call"

    def test_process_expected_failures(self, handler, mock_report):
        """Test the _process_expected_failures method."""
        # Setup
        result = MagicMock()
        result.outcome = 'passed'
        result.metadata = {}
        status = {'xfail_reason': 'expected to fail for reason X'}
        outcome = 'passed'

        # Call the method with xfail status in status dict
        handler._process_expected_failures(mock_report, result, status, outcome)

        # Check that the outcome is updated to xpassed
        assert result.outcome == 'xpassed'
        assert result.wasxfail == 'expected to fail for reason X'
        assert result.metadata['xfail_reason'] == 'expected to fail for reason X'

        # Test with xfail reason in report
        result = MagicMock()
        result.outcome = 'failed'
        result.metadata = {}
        status = {}
        outcome = 'failed'
        mock_report.wasxfail = 'reason: test is expected to fail'

        # Call the method with wasxfail in report
        handler._process_expected_failures(mock_report, result, status, outcome)

        # Check that the outcome is updated to xfailed
        assert result.outcome == 'xfailed'
        assert result.wasxfail == 'reason: test is expected to fail'
        assert result.metadata['xfail_reason'] == 'test is expected to fail'

    @patch('html_reporter.result_handler.save_test_result')
    def test_create_final_report(self, mock_save, handler, mock_item, mock_call, mock_report):
        from types import SimpleNamespace
        from pathlib import Path
        import time

        # Setup common test data
        status_key = f"{mock_item.nodeid}:{mock_item.execution_count}"
        status = {
            'setup': 'passed',
            'call': 'passed',
            'teardown': 'passed',
            'final_result_reported': False,
            'execution_count': 1,
            'xfail_status': None
        }

        # Setup timing data and config for Test Case 1: Normal passing test
        handler.config = SimpleNamespace(
            _aqa_test_timing={status_key: {'start_time': time.time(), 'total_duration': 1.5}},
            option=SimpleNamespace(reruns=0)  # Use reruns=0 for passing test
        )

        # Test case 1: Normal passing test
        with patch('html_reporter.result_handler.TestResult') as MockTestResult:
            test_result = MagicMock()
            MockTestResult.return_value = test_result

            # Setup mocks for passing scenario
            handler._determine_outcome = MagicMock(return_value=('passed', None))
            handler._update_outcome_for_soft_assertions = MagicMock(return_value=('passed', None))
            handler._create_test_result = MagicMock(return_value=test_result)
            handler._process_expected_failures = MagicMock()
            handler._process_error_info = MagicMock()
            handler._collect_logs = MagicMock()
            handler._capture_metadata = MagicMock()
            handler._get_report_dir = MagicMock(return_value=Path("reports"))

            # Call the method
            handler._create_final_report(mock_item, mock_call, mock_report, status, status_key)

            # Verify expectations
            assert status['final_result_reported'] is True
            handler._determine_outcome.assert_called_once_with(mock_report, status)
            handler._create_test_result.assert_called_once()
            mock_save.assert_called_once_with(test_result, Path("reports"))
            handler._process_error_info.assert_not_called()

        # Test case 2: Rerun scenario
        mock_save.reset_mock()
        status['final_result_reported'] = False
        # Override config for rerun scenario with proper integer reruns value.
        handler.config.option = SimpleNamespace(reruns=3)

        with patch('html_reporter.result_handler.TestResult') as MockTestResult:
            test_result = MagicMock()
            MockTestResult.return_value = test_result

            # Setup mocks for failed scenario that should trigger a rerun
            handler._determine_outcome = MagicMock(return_value=('failed', 'call'))
            handler._update_outcome_for_soft_assertions = MagicMock(return_value=('failed', 'call'))
            handler._create_test_result = MagicMock(return_value=test_result)
            handler._process_expected_failures = MagicMock()
            handler._process_error_info = MagicMock()
            handler._collect_logs = MagicMock()
            handler._capture_metadata = MagicMock()
            handler._get_report_dir = MagicMock(return_value=Path("reports"))

            # Call the method
            handler._create_final_report(mock_item, mock_call, mock_report, status, status_key)

            # Verify that the outcome was set to rerun
            assert test_result.outcome == "rerun"
            handler._process_error_info.assert_called_once()
            mock_save.assert_called_once_with(test_result, Path("reports"))

        # Test case 3: Test with error status
        mock_save.reset_mock()
        status['final_result_reported'] = False
        # Set config for error scenario
        handler.config.option = SimpleNamespace(reruns=0)

        with patch('html_reporter.result_handler.TestResult') as MockTestResult:
            test_result = MagicMock()
            test_result.outcome = 'error'
            MockTestResult.return_value = test_result

            # Setup mocks for error scenario
            handler._determine_outcome = MagicMock(return_value=('error', 'call'))
            handler._update_outcome_for_soft_assertions = MagicMock(return_value=('error', 'call'))
            handler._create_test_result = MagicMock(return_value=test_result)
            handler._process_expected_failures = MagicMock()
            handler._process_error_info = MagicMock()
            handler._collect_logs = MagicMock()
            handler._capture_metadata = MagicMock()
            handler._get_report_dir = MagicMock(return_value=Path("reports"))

            # Call the method
            handler._create_final_report(mock_item, mock_call, mock_report, status, status_key)

            # Verify error processing was called with the right parameters
            handler._process_error_info.assert_called_once_with(
                mock_item, mock_call, mock_report, test_result, 'error'
            )
            mock_save.assert_called_once_with(test_result, Path("reports"))

        # Test case 4: xfailed test
        mock_save.reset_mock()
        status['final_result_reported'] = False
        status['xfail_status'] = 'xfailed'
        # Set config for xfailed scenario
        handler.config.option = SimpleNamespace(reruns=0)

        with patch('html_reporter.result_handler.TestResult') as MockTestResult:
            test_result = MagicMock()
            test_result.outcome = 'xfailed'
            MockTestResult.return_value = test_result

            # Setup mocks for xfailed scenario
            handler._determine_outcome = MagicMock(return_value=('xfailed', 'call'))
            handler._update_outcome_for_soft_assertions = MagicMock(return_value=('xfailed', 'call'))
            handler._create_test_result = MagicMock(return_value=test_result)
            handler._process_expected_failures = MagicMock()
            handler._process_error_info = MagicMock()
            handler._collect_logs = MagicMock()
            handler._capture_metadata = MagicMock()
            handler._get_report_dir = MagicMock(return_value=Path("reports"))

            # Call the method
            handler._create_final_report(mock_item, mock_call, mock_report, status, status_key)

            # Verify xfail was processed correctly
            handler._process_expected_failures.assert_called_once_with(
                mock_report, test_result, status, 'xfailed'
            )
            handler._process_error_info.assert_called_once()
            mock_save.assert_called_once_with(test_result, Path("reports"))

    @patch('base64.b64encode')
    def test_capture_screenshot(self, mock_b64encode, handler, mock_item):
        """Test the _capture_screenshot method."""
        # Setup
        page = MagicMock()
        screenshot_bytes = b'screenshot_data'
        page.screenshot.return_value = screenshot_bytes
        result = MagicMock()

        # Mock b64encode
        mock_b64encode.return_value = b'encoded_screenshot'

        # Call the method
        handler._capture_screenshot(page, result)

        # Check that screenshot was taken and encoded
        page.screenshot.assert_called_once_with(type='jpeg', quality=60, scale='css', full_page=False)
        mock_b64encode.assert_called_once_with(screenshot_bytes)
        assert result.screenshot == 'encoded_screenshot'
        assert handler.config.screenshots_amount == 1

        # Test with too many screenshots
        handler.config.screenshots_amount = 10
        result.screenshot = None

        # Call the method
        handler._capture_screenshot(page, result)

        # Check that no screenshot was taken
        assert result.screenshot is None

        # Test with exception
        handler.config.screenshots_amount = 0
        page.screenshot.side_effect = Exception("Screenshot error")

        # Call the method
        handler._capture_screenshot(page, result)

        # Check that error was captured
        assert "Failed to capture screenshot: Screenshot error" == result.error

    def test_collect_phase_logs(self, handler):
        """Test the _collect_phase_logs method."""
        # Setup
        phase = "call"
        phase_report = MagicMock()
        phase_report.caplog = "Log message from call phase"
        phase_report.capstderr = "Error from call phase"
        phase_report.capstdout = "Output from call phase"

        result = MagicMock()
        result.caplog = ""
        result.capstderr = ""
        result.capstdout = ""

        seen_logs = set()
        seen_stderr = set()
        seen_stdout = set()

        # Call the method
        handler._collect_phase_logs(phase, phase_report, result, seen_logs, seen_stderr, seen_stdout)

        # Check that logs were collected
        assert "--- call phase logs ---" in result.caplog
        assert "Log message from call phase" in result.caplog
        assert "--- call phase stderr ---" in result.capstderr
        assert "Error from call phase" in result.capstderr
        assert "--- call phase stdout ---" in result.capstdout
        assert "Output from call phase" in result.capstdout

        # Check that logs were added to seen sets
        assert phase_report.caplog in seen_logs
        assert phase_report.capstderr in seen_stderr
        assert phase_report.capstdout in seen_stdout

        # Test with existing log content
        result.caplog = "Previous log content\n"
        result.capstderr = "Previous stderr content\n"
        result.capstdout = "Previous stdout content\n"

        # Different phase logs
        phase = "teardown"
        phase_report.caplog = "Log message from teardown phase"
        phase_report.capstderr = "Error from teardown phase"
        phase_report.capstdout = "Output from teardown phase"

        # Call the method
        handler._collect_phase_logs(phase, phase_report, result, seen_logs, seen_stderr, seen_stdout)

        # Check that logs were appended
        assert "Previous log content" in result.caplog
        assert "--- teardown phase logs ---" in result.caplog
        assert "Log message from teardown phase" in result.caplog

        assert "Previous stderr content" in result.capstderr
        assert "--- teardown phase stderr ---" in result.capstderr
        assert "Error from teardown phase" in result.capstderr

        assert "Previous stdout content" in result.capstdout
        assert "--- teardown phase stdout ---" in result.capstdout
        assert "Output from teardown phase" in result.capstdout

    def test_capture_metadata(self, handler, mock_item):
        """Test the _capture_metadata method."""
        # Setup
        result = MagicMock()
        result.metadata = {}
        mock_item.test_case_link = "https://example.com/case/123"
        mock_item.test_case_id = "TEST-123"

        # Call the method
        handler._capture_metadata(mock_item, result)

        # Check that metadata was captured
        assert result.metadata["case_link"] == "https://example.com/case/123"
        assert result.metadata["case_id"] == "TEST-123"

    def test_get_report_dir(self, handler):
        """Test the _get_report_dir method."""
        # Setup
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            # Call the method
            report_dir = handler._get_report_dir()

            # Check that the directory was created
            mock_mkdir.assert_called_once_with(exist_ok=True)
            assert report_dir == Path("reports")

    def test_process_test_result_complete_test(self, handler, mock_item, mock_call, mock_report):
        """Test the process_test_result method with a complete test."""
        # Setup - this will be a complete test (teardown phase)
        mock_report.when = "teardown"
        mock_report.outcome = "passed"

        # Set up status
        status_key = f"{mock_item.nodeid}:1"
        handler.config._aqa_test_status[status_key] = {
            'setup': 'passed',
            'call': 'passed',
            'teardown': None,
            'final_result_reported': False,
            'execution_count': 1,
            'xfail_status': None
        }

        # Mock methods
        handler._track_phase_timing = MagicMock()
        handler._create_final_report = MagicMock()
        handler._store_phase_report = MagicMock()

        # Call the method
        handler.process_test_result(mock_item, mock_call, mock_report)

        # Check that methods were called
        handler._track_phase_timing.assert_called_once()
        assert handler.config._aqa_test_status[status_key]['teardown'] == 'passed'
        handler._create_final_report.assert_called_once()
        handler._store_phase_report.assert_called_once()

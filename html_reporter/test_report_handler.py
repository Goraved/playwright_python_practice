import json
from unittest.mock import MagicMock, patch
from unittest.mock import mock_open

import jinja2
import pytest

from html_reporter.report_handler import (
    TestResult,
    save_test_result,
    aggregate_results,
    calculate_stats,
    format_timestamp,
    get_pytest_metadata,
    generate_human_readable_summary,
    generate_html_report
)


@pytest.mark.unit
class TestTestResult:
    """Unit tests for the TestResult class."""

    @pytest.fixture
    def mock_item(self):
        """Create a mock pytest item for testing."""
        item = MagicMock()
        item.nodeid = "tests/test_example.py::test_function"
        item.obj = MagicMock()
        item.obj.__doc__ = "Test function docstring"
        item.function = MagicMock()
        item.function.__code__ = MagicMock()
        item.function.__code__.co_firstlineno = 42
        item.iter_markers = MagicMock(return_value=[])

        # Set up config to NOT have workerinput attribute
        item.config = MagicMock()
        # Remove the workerinput attribute to make hasattr return False
        del item.config.workerinput

        return item

    def test_init(self, mock_item):
        """Test initialization of TestResult."""
        result = TestResult(mock_item, "passed", 0.5, {'call': 27.3, 'setup': 16.1, 'teardown': 0.8})

        assert result.nodeid == mock_item.nodeid
        assert result.outcome == "passed"
        assert result.duration == 0.5
        assert result.phase_durations == {'call': 27.3, 'setup': 16.1, 'teardown': 0.8}
        assert result.description == "Test function docstring"
        assert result.markers == []
        assert isinstance(result.metadata, dict)
        assert isinstance(result.environment, dict)
        assert result.worker_id == "master"

    def test_init_with_timestamp(self, mock_item):
        """Test initialization with a custom timestamp."""
        custom_timestamp = 1623456789.0
        result = TestResult(mock_item, "passed", 0.5, {'call': 27.3, 'setup': 16.1, 'teardown': 0.8},
                            timestamp=custom_timestamp)

        assert result.timestamp == custom_timestamp

    def test_generate_github_link(self, mock_item):
        """Test GitHub link generation."""
        result = TestResult(mock_item, "passed", 0.5, {'call': 27.3, 'setup': 16.1, 'teardown': 0.8})

        expected_base_url = "https://github.com/Goraved/playwright_python_practice/blob/master/"
        expected_link = f"{expected_base_url}tests/test_example.py#L42"

        assert result.github_link == expected_link

    def test_generate_github_link_error_handling(self, mock_item):
        """Test GitHub link generation handles errors."""
        # Create a situation that will cause an error
        mock_item.function.__code__ = None

        result = TestResult(mock_item, "passed", 0.5, {'call': 27.3, 'setup': 16.1, 'teardown': 0.8})

        assert "Error generating GitHub link" in result.github_link

    def test_get_environment_info(self, mock_item):
        """Test environment info collection."""
        # Test with no page object
        env_info = TestResult._get_environment_info(mock_item)

        assert "python_version" in env_info
        assert "platform" in env_info
        assert "processor" in env_info

        # Test with a page object that has browser information
        page = MagicMock()
        browser = MagicMock()
        browser.browser_type.name = "chromium"
        browser.version = "1.0.0"
        page.context.browser = browser

        mock_item.funcargs = {"page": page}

        env_info = TestResult._get_environment_info(mock_item)

        assert env_info["browser"] == "Chromium"
        assert env_info["browser_version"] == "1.0.0"

        # Test with a page object that raises an exception
        browser.browser_type.name = None
        env_info = TestResult._get_environment_info(mock_item)

        assert env_info["browser"] == "Unknown"
        assert env_info["browser_version"] == "Unknown"

    def test_extract_metadata_with_meta_marker(self, mock_item):
        """Test metadata extraction with a meta marker."""
        # Create a meta marker
        meta_marker = MagicMock()
        meta_marker.name = "meta"
        meta_marker.kwargs = {"case_id": "TEST-123", "type_class": str}

        mock_item.own_markers = [meta_marker]

        metadata = TestResult._extract_metadata(mock_item)

        assert metadata["case_id"] == "TEST-123"
        assert metadata["type_class"] == "str"  # Class name as string

    def test_extract_metadata_with_parametrize(self, mock_item):
        """Test metadata extraction from parametrized tests."""
        # Create a parametrize marker with meta
        param_marker = MagicMock()
        param_marker.name = "parametrize"

        # Create a meta value within the parameter
        meta_value = MagicMock()
        meta_value.mark = MagicMock()
        meta_value.mark.name = "meta"
        meta_value.mark.kwargs = {"case_id": "PARAM-123"}

        # Create a parameter with values containing the meta
        param = MagicMock()
        param.id = "param1"
        param.values = [meta_value]

        param_marker.args = [[param]]

        mock_item.own_markers = [param_marker]
        mock_item.name = "test_name[param1]"

        metadata = TestResult._extract_metadata(mock_item)

        assert metadata["case_id"] == "PARAM-123"

    def test_to_dict(self, mock_item):
        """Test conversion of TestResult to dictionary."""
        result = TestResult(mock_item, "passed", 0.5, {'call': 27.3, 'setup': 16.1, 'teardown': 0.8})
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict['nodeid'] == mock_item.nodeid
        assert result_dict['outcome'] == "passed"
        assert result_dict['duration'] == 0.5
        assert result_dict['phase_durations'] == {'call': 27.3, 'setup': 16.1, 'teardown': 0.8}
        assert result_dict['worker_id'] == "master"
        assert isinstance(result_dict['timestamp'], float)
        assert isinstance(result_dict['logs'], list)

    def test_to_dict_with_execution_log(self, mock_item):
        """Test to_dict formats execution logs correctly."""
        result = TestResult(mock_item, "passed", 0.5, {'call': 27.3, 'setup': 16.1, 'teardown': 0.8})

        # Add execution log attribute with formatted logs
        result.execution_log = [
            "INFO - This is an info message",
            "  DEBUG - This is an indented debug message",
            "    ERROR - This is a double-indented error message"
        ]

        result_dict = result.to_dict()

        assert len(result_dict['logs']) >= 3
        assert "INFO - This is an info message" in result_dict['logs']
        # The formatting adds spaces based on the number of double spaces in the original
        assert any("DEBUG - This is an indented debug message" in log for log in result_dict['logs'])
        assert any("ERROR - This is a double-indented error message" in log for log in result_dict['logs'])


@pytest.mark.unit
class TestReportFunctions:
    """Unit tests for report handler functions."""

    @pytest.fixture
    def sample_results(self):
        """Create a list of sample test results."""
        return [
            {
                "nodeid": "test_1.py::test_func1",
                "outcome": "passed",
                "timestamp": 1623456789.0,
                "duration": 0.5
            },
            {
                "nodeid": "test_2.py::test_func2",
                "outcome": "failed",
                "timestamp": 1623456790.0,
                "duration": 1.2
            },
            {
                "nodeid": "test_3.py::test_func3",
                "outcome": "skipped",
                "timestamp": 1623456791.0,
                "duration": 0.1
            },
            {
                "nodeid": "test_4.py::test_func4",
                "outcome": "error",
                "timestamp": 1623456792.0,
                "duration": 0.8
            },
            {
                "nodeid": "test_5.py::test_func5",
                "outcome": "xfailed",
                "timestamp": 1623456793.0,
                "duration": 0.3
            },
            {
                "nodeid": "test_6.py::test_func6",
                "outcome": "xpassed",
                "timestamp": 1623456794.0,
                "duration": 0.4
            },
            {
                "nodeid": "test_7.py::test_func7",
                "outcome": "rerun",
                "timestamp": 1623456795.0,
                "duration": 0.6
            }
        ]

    def test_save_test_result(self, tmp_path):
        """Test saving test result to a file."""
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"test": "data"}
        mock_result.worker_id = "master"  # Ensure worker_id is set

        save_test_result(mock_result, tmp_path)

        report_file = tmp_path / "worker_master.json"
        assert report_file.exists(), f"File not created. Path: {report_file}"

        # Read and verify file contents
        with open(report_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1, f"Expected 1 line, got {len(lines)}"

            saved_data = json.loads(lines[0])
            assert saved_data == {"test": "data"}, f"Saved data does not match: {saved_data}"

        # Test appending multiple results
        another_result = MagicMock()
        another_result.to_dict.return_value = {"another": "test"}
        another_result.worker_id = "master"

        save_test_result(another_result, tmp_path)

        # Verify file now has two lines
        with open(report_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"

            # Verify both entries can be parsed as JSON
            first_data = json.loads(lines[0])
            second_data = json.loads(lines[1])
            assert first_data == {"test": "data"}
            assert second_data == {"another": "test"}

    def test_aggregate_results(self, tmp_path):
        """Test aggregation of test results with unique filtering."""
        # Create multiple worker result files with duplicate and unique tests
        with open(tmp_path / "worker_1.json", 'w') as f:
            # Duplicate test with same nodeid and timestamp
            json.dump({"nodeid": "test_1.py::test_func", "timestamp": 1623456789.0, "outcome": "failed"}, f)
            f.write('\n')
            json.dump({"nodeid": "test_1.py::test_func", "timestamp": 1623456789.0, "outcome": "passed"}, f)
            f.write('\n')

            # Different test with a unique timestamp
            json.dump({"nodeid": "test_2.py::test_func", "timestamp": 1623456790.0, "outcome": "passed"}, f)
            f.write('\n')

            # Completely different test
            json.dump({"nodeid": "test_3.py::test_func", "timestamp": 1623456791.0, "outcome": "failed"}, f)

        # Simulate another worker file
        with open(tmp_path / "worker_2.json", 'w') as f:
            # Attempt to add a duplicate test
            json.dump({"nodeid": "test_1.py::test_func", "timestamp": 1623456789.0, "outcome": "passed"}, f)
            f.write('\n')
            json.dump({"nodeid": "test_4.py::test_func", "timestamp": 1623456792.0, "outcome": "passed"}, f)

        # Aggregate results
        results = aggregate_results(tmp_path)

        # Verify unique results based on nodeid and timestamp
        assert len(results) == 4  # Unique test results (test_1, test_2, test_3, test_4)

        # Verify the first occurrence of test_1 is kept (which would be 'failed')
        test_1_result = next(r for r in results if r['nodeid'] == "test_1.py::test_func")
        assert test_1_result['outcome'] == 'failed'

    def test_aggregate_results_empty_directory(self, tmp_path):
        """Test aggregation with an empty directory."""
        results = aggregate_results(tmp_path)
        assert results == []

    def test_aggregate_results_empty_file(self, tmp_path):
        """Test aggregation with an empty file."""
        with open(tmp_path / "worker_1.json", 'w'):
            pass  # Create empty file

        results = aggregate_results(tmp_path)
        assert results == []

    def test_calculate_stats(self, sample_results):
        """Test calculation of test statistics."""
        stats = calculate_stats(sample_results)

        assert stats['total'] == 7
        assert stats['passed'] == 1
        assert stats['failed'] == 1
        assert stats['skipped'] == 1
        assert stats['error'] == 1
        assert stats['xfailed'] == 1
        assert stats['xpassed'] == 1
        assert stats['rerun'] == 1

        # Check timing calculations
        assert stats['start_time'] == 1623456789.0  # Earliest timestamp
        assert stats['end_time'] >= 1623456795.0 + 0.6  # Latest timestamp + duration
        assert stats['total_duration'] >= 0  # Should be positive

        # Check success rate
        assert stats['success_rate'] == round((1 / 7) * 100, 2)

    def test_calculate_stats_empty(self):
        """Test calculation of stats with empty results."""
        stats = calculate_stats([])

        assert stats['total'] == 0
        assert stats['passed'] == 0
        assert stats['success_rate'] == 0
        assert stats['start_time'] == 0
        assert stats['end_time'] == 0
        assert stats['total_duration'] == 0

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        timestamp = 1623456789.0  # 2021-06-12 00:39:49 UTC
        formatted = format_timestamp(timestamp)

        assert isinstance(formatted, str)
        assert "2021-06-12" in formatted  # Date part

        # Instead of checking for exact time values, just verify it has a valid time format
        import re
        assert re.search(r'\d{2}:\d{2}:\d{2}', formatted), f"Time format not found in {formatted}"

    def test_get_pytest_metadata(self):
        """Test pytest metadata collection."""
        with patch('importlib.metadata.version', return_value='1.0.0'):
            metadata = get_pytest_metadata()

            assert 'pytest_version' in metadata
            assert 'packages' in metadata
            assert isinstance(metadata['packages'], dict)

    @patch('time.strftime')
    def test_generate_human_readable_summary_empty(self, mock_strftime):
        """Test summary generation with empty results."""
        mock_strftime.return_value = "2023-06-12 10:00:00"

        summary = generate_human_readable_summary([], {})

        assert "CODE RED" in summary
        assert "no test results were found" in summary.lower()

    @patch('time.strftime')
    def test_generate_human_readable_summary(self, mock_strftime, sample_results):
        """Test generation of human-readable summary."""
        mock_strftime.return_value = "2023-06-12 10:00:00"

        stats = calculate_stats(sample_results)
        summary = generate_human_readable_summary(sample_results, stats)

        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "Test Execution Overview" in summary
        assert "Test Status Specifics" in summary
        assert "Performance Post-Mortem" in summary
        assert "Reruns Retrospective" in summary

    @patch('time.strftime')
    def test_generate_human_readable_summary_perfect_run(self, mock_strftime):
        """Test summary generation with perfect test run."""
        mock_strftime.return_value = "2023-06-12 10:00:00"

        perfect_results = [
            {"nodeid": "test_1.py::test_func1", "outcome": "passed", "timestamp": 1623456789.0, "duration": 0.5},
            {"nodeid": "test_2.py::test_func2", "outcome": "passed", "timestamp": 1623456790.0, "duration": 0.6}
        ]

        stats = calculate_stats(perfect_results)
        summary = generate_human_readable_summary(perfect_results, stats)

        assert "Perfection Achieved" in summary
        assert "100% Tests Passing" in summary

    @patch('time.strftime')
    def test_generate_human_readable_summary_slow_tests(self, mock_strftime):
        """Test summary generation with slow tests."""
        mock_strftime.return_value = "2023-06-12 10:00:00"

        slow_test_results = [
            {"nodeid": "test_1.py::test_func1", "outcome": "passed", "timestamp": 1623456789.0, "duration": 0.5},
            {"nodeid": "test_api.py::test_api_func", "outcome": "passed", "timestamp": 1623456790.0, "duration": 150}
        ]

        stats = calculate_stats(slow_test_results)
        summary = generate_human_readable_summary(slow_test_results, stats, slow_test_threshold_sec=120)

        assert "Sluggish Tests Detected" in summary
        assert "API Tests" in summary

    def test_generate_html_report(self, tmp_path):
        """Test HTML report generation."""
        report_path = str(tmp_path / "report.html")

        # Create simple mocks
        session = MagicMock()
        session.config = MagicMock(spec=["getoption"])  # Specify only the methods we need
        session.config.getoption.return_value = report_path

        # Mock essential functions
        with patch('html_reporter.report_handler.aggregate_results') as mock_aggregate, \
                patch('html_reporter.report_handler.calculate_stats') as mock_stats, \
                patch('html_reporter.report_handler.get_pytest_metadata') as mock_metadata, \
                patch('html_reporter.report_handler.generate_human_readable_summary') as mock_summary, \
                patch('builtins.open', mock_open(read_data="mock content")) as mock_file, \
                patch('jinja2.Environment') as mock_env, \
                patch('jinja2.FileSystemLoader'), \
                patch('jinja2.Template') as mock_template_class, \
                patch('time.strftime', return_value="2023-06-12 10:00:00"), \
                patch('html_reporter.report_handler.hasattr',
                      return_value=False):  # Key fix: force hasattr to return False

            # Set up return values
            results = [{"nodeid": "test_1.py::test_func1", "outcome": "passed",
                        "timestamp": 1623456789.0, "duration": 0.5,
                        "environment": {"python_version": "3.9.0"}}]

            mock_aggregate.return_value = results
            mock_stats.return_value = {
                "total": 1, "passed": 1, "failed": 0, "success_rate": 100,
                "start_time": 1623456789.0, "end_time": 1623456789.5,
                "total_duration": 0.5
            }
            mock_metadata.return_value = {"pytest_version": "7.0.0", "packages": {}}
            mock_summary.return_value = "Test summary"

            # Mock for JS template
            mock_js_template = MagicMock()
            mock_js_template.render.return_value = "rendered js content"
            mock_template_class.return_value = mock_js_template

            # Set up template
            mock_template = MagicMock()
            mock_template.render.return_value = "<html>Test Report</html>"
            mock_env.return_value.get_template.return_value = mock_template
            mock_env.return_value.filters = {}

            # Call the function
            generate_html_report(session, tmp_path)

            # Verify the file was opened for reading CSS and JS
            assert mock_file.call_args_list[0][0][0] == "html_reporter/static/css/styles.css"
            assert mock_file.call_args_list[1][0][0] == "html_reporter/static/js/report.js"

            # Verify JS template was rendered
            mock_js_template.render.assert_called_once()

            # Verify the HTML file was written
            assert mock_file.call_args_list[-1][0][0] == report_path
            assert mock_file.call_args_list[-1][0][1] == "w"
            mock_file.return_value.write.assert_called_with("<html>Test Report</html>")

    @patch('html_reporter.report_handler.aggregate_results')
    def test_generate_html_report_empty_results(self, mock_aggregate_results, tmp_path):
        """Test HTML report generation with empty results."""
        # Mock session
        session = MagicMock()
        report_path = str(tmp_path / "report.html")
        session.config.getoption.return_value = report_path

        # Make sure session.config doesn't have workerinput attribute
        session.config = MagicMock()
        session.config.getoption.return_value = report_path
        del session.config.workerinput

        # Mock empty results
        mock_aggregate_results.return_value = []

        # Call the function
        with patch('builtins.open', mock_open()) as mock_file:
            generate_html_report(session, tmp_path)

            # Check that the file was opened for writing
            mock_file.assert_called_with(report_path, "w")
            mock_file().write.assert_called_with("<html><body><h1>No tests were run</h1></body></html>")

    @patch('html_reporter.report_handler.aggregate_results')
    def test_generate_html_report_worker(self, mock_aggregate_results, tmp_path):
        """Test HTML report early termination on worker nodes."""
        # Mock session for a worker
        session = MagicMock()
        report_path = str(tmp_path / "report.html")
        session.config.getoption.return_value = report_path

        # Set up config to be a worker node (workerinput is present)
        session.config = MagicMock()
        session.config.workerinput = {'workerid': '1'}
        session.config.getoption.return_value = report_path

        # Setup aggregate_results to return something
        mock_aggregate_results.return_value = [{"test": "data"}]

        # Mock file operations to verify no file is written
        with patch('builtins.open', mock_open()) as mock_file:
            # Call the function
            generate_html_report(session, tmp_path)

            # Verify that aggregate_results IS called (current implementation)
            mock_aggregate_results.assert_called_once_with(tmp_path)

            # But verify no file operations happen (early return)
            mock_file.assert_not_called()

    @patch('html_reporter.report_handler.aggregate_results')
    @patch('html_reporter.report_handler.calculate_stats')
    @patch('html_reporter.report_handler.get_pytest_metadata')
    @patch('html_reporter.report_handler.generate_human_readable_summary')
    def test_generate_html_report_with_ci(self, mock_summary, mock_get_metadata, mock_calculate_stats,
                                          mock_aggregate_results, tmp_path):
        """Test HTML report generation with CI job ID."""
        # Mock session
        session = MagicMock()
        report_path = str(tmp_path / "report.html")

        # Mock config options
        session.config.getoption.side_effect = lambda \
                option: report_path if option == "--html-report" else "Test Report" if option == "--report-title" else None

        # Make sure session.config doesn't have workerinput attribute
        session.config = MagicMock()
        session.config.getoption.side_effect = lambda \
                option: report_path if option == "--html-report" else "Test Report" if option == "--report-title" else None
        del session.config.workerinput

        # Mock results and stats
        results = [
            {"nodeid": "test_1.py::test_func1", "outcome": "passed", "timestamp": 1623456789.0,
             "duration": 0.5, "environment": {"python_version": "3.9.0"}}
        ]
        stats = {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "success_rate": 100,
            "start_time": 1623456789.0,
            "end_time": 1623456789.5,
            "total_duration": 0.5
        }

        # Set up mocks
        mock_aggregate_results.return_value = results
        mock_calculate_stats.return_value = stats
        mock_get_metadata.return_value = {"pytest_version": "7.0.0", "packages": {}}
        mock_summary.return_value = "Test summary"

        # Mock CI environment
        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = "12345"  # CI_JOB_ID

            # Mock jinja2 environment
            with patch('jinja2.Environment') as mock_env:
                mock_template = MagicMock()
                mock_template.render.return_value = "<html>Test Report</html>"
                mock_env.return_value.get_template.return_value = mock_template
                mock_env.return_value.filters = {}

                # Mock FileSystemLoader
                with patch('jinja2.FileSystemLoader'):
                    # Mock time.strftime
                    with patch('time.strftime', return_value="2023-06-12 10:00:00"):
                        # Call the function with all mocks in place
                        with patch('builtins.open', mock_open()) as mock_file:
                            generate_html_report(session, tmp_path)

                            # Check that the template was rendered with job URL
                            render_kwargs = mock_template.render.call_args[1]
                            assert render_kwargs["job_id"] == "12345"

                            # Verify the file was written
                            mock_file.assert_called_with(report_path, "w", encoding='utf-8')


@pytest.mark.unit
class TestJinja2Exceptions:
    """Unit tests for handling Jinja2 exceptions during template rendering."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock pytest session."""
        session = MagicMock()
        session.config = MagicMock()
        session.config.getoption.side_effect = lambda option: {
            "--html-report": "report.html",
            "--report-title": "Test Report"
        }.get(option)

        # Ensure session.config doesn't have workerinput attribute
        del session.config.workerinput

        return session

    @pytest.fixture
    def mock_results(self):
        """Create mock test results."""
        return [{
            "timestamp": 1623456789.0,
            "nodeid": "test_example.py::test_function",
            "outcome": "passed",
            "duration": 0.5,
            "phase_durations": {"call": 0.3, "setup": 0.1, "teardown": 0.1},
            "environment": {"python_version": "3.9.0"},
            "metadata": {"case_id": "TEST-123"},
            "github_link": "https://github.example.com/test_example.py"
        }]

    @pytest.fixture
    def mock_stats(self):
        """Create mock stats with all required keys."""
        return {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "error": 0,
            "xfailed": 0,
            "xpassed": 0,
            "rerun": 0,
            "start_time": 1623456789.0,
            "end_time": 1623456790.0,
            "total_duration": 1.0,
            "success_rate": 100.0,
            "summary": "Test summary"
        }

    @patch('html_reporter.report_handler.aggregate_results')
    @patch('html_reporter.report_handler.calculate_stats')
    @patch('html_reporter.report_handler.get_pytest_metadata')
    @patch('html_reporter.report_handler.os.path.exists')
    def test_template_not_found_error(self, mock_path_exists, mock_get_metadata,
                                      mock_calculate_stats, mock_aggregate_results,
                                      mock_session, mock_results, mock_stats):
        """Test handling TemplateNotFound error."""
        mock_aggregate_results.return_value = mock_results
        mock_calculate_stats.return_value = mock_stats
        mock_get_metadata.return_value = {"pytest_version": "7.0.0", "packages": {}}
        mock_path_exists.return_value = True  # Make os.path.exists return True

        # Create a function that will be called by our mocked get_template
        def raise_template_not_found(*args, **kwargs):
            raise jinja2.exceptions.TemplateNotFound("report_template.html")

        # Patch Environment and its methods
        with patch('jinja2.Environment') as mock_env_class, \
                patch('jinja2.FileSystemLoader'):
            mock_env = MagicMock()
            mock_env_class.return_value = mock_env
            mock_env.filters = {}
            mock_env.get_template = raise_template_not_found

            # Set up open mock
            with patch('builtins.open', create=True) as mock_file:
                # Run the function - expect AssertionError according to your implementation
                with pytest.raises(AssertionError):
                    generate_html_report(mock_session, MagicMock())

                # Verify error handling - file should still be written
                mock_file.assert_called_once()
                mock_file.return_value.__enter__.return_value.write.assert_called_once()
                # Check that the error message is included in the written content
                args = mock_file.return_value.__enter__.return_value.write.call_args[0][0]
                assert "Error" in args
                assert "Template" in args

    @patch('html_reporter.report_handler.aggregate_results')
    @patch('html_reporter.report_handler.calculate_stats')
    @patch('html_reporter.report_handler.get_pytest_metadata')
    @patch('html_reporter.report_handler.os.path.exists')
    def test_template_syntax_error(self, mock_path_exists, mock_get_metadata,
                                   mock_calculate_stats, mock_aggregate_results,
                                   mock_session, mock_results, mock_stats):
        """Test handling TemplateSyntaxError."""
        mock_aggregate_results.return_value = mock_results
        mock_calculate_stats.return_value = mock_stats
        mock_get_metadata.return_value = {"pytest_version": "7.0.0", "packages": {}}
        mock_path_exists.return_value = True  # Make os.path.exists return True

        # Setup template mocks
        mock_template = MagicMock()
        mock_template.render.side_effect = jinja2.exceptions.TemplateSyntaxError(
            "Unexpected end of template", 1, "report_template.html"
        )

        # Track file operations
        open_calls = []
        write_calls = []

        # Create mock file handlers
        css_mock = MagicMock()
        css_mock.read.return_value = "/* CSS content */"

        js_mock = MagicMock()
        js_mock.read.return_value = "// JS content with {{ results }}"

        html_mock = MagicMock()

        # Custom open side effect
        def mock_open_side_effect(filename, mode='r', *args, **kwargs):
            open_calls.append((filename, mode))

            if 'styles.css' in filename:
                return css_mock
            elif 'report.js' in filename:
                return js_mock
            else:
                # For HTML output file
                return html_mock

        # Track write calls
        html_mock.__enter__ = MagicMock(return_value=html_mock)
        html_mock.__exit__ = MagicMock(return_value=None)
        html_mock.write = MagicMock(side_effect=lambda content: write_calls.append(content))

        # Patch all required components
        with patch('jinja2.Environment') as mock_env_class, \
                patch('jinja2.FileSystemLoader'), \
                patch('jinja2.Template') as mock_template_class, \
                patch('builtins.open', side_effect=mock_open_side_effect):

            # Setup environment mock
            mock_env = MagicMock()
            mock_env_class.return_value = mock_env
            mock_env.filters = {}
            mock_env.get_template.return_value = mock_template

            # Setup JS template mock
            mock_js_template = MagicMock()
            mock_js_template.render.return_value = "rendered js content"
            mock_template_class.return_value = mock_js_template

            # Run the function - expect AssertionError
            with pytest.raises(AssertionError):
                generate_html_report(mock_session, MagicMock())

            # Verify CSS and JS files were read
            css_file_read = any('styles.css' in call[0] and call[1] == 'r' for call in open_calls)
            js_file_read = any('report.js' in call[0] and call[1] == 'r' for call in open_calls)
            assert css_file_read, "CSS file was not read"
            assert js_file_read, "JS file was not read"

            # Verify HTML file was written with error message
            html_file_written = any(call[1] == 'w' for call in open_calls)
            assert html_file_written, "HTML file was not opened for writing"

            # Verify error content was written
            assert len(write_calls) > 0, "No content was written to the file"
            written_content = ''.join(write_calls)
            assert "Error" in written_content
            assert "Template" in written_content

    @patch('html_reporter.report_handler.aggregate_results')
    @patch('html_reporter.report_handler.calculate_stats')
    @patch('html_reporter.report_handler.get_pytest_metadata')
    @patch('html_reporter.report_handler.os.path.exists')
    def test_undefined_error(self, mock_path_exists, mock_get_metadata,
                             mock_calculate_stats, mock_aggregate_results,
                             mock_session, mock_results, mock_stats):
        """Test handling UndefinedError (missing variable in template)."""
        mock_aggregate_results.return_value = mock_results
        mock_calculate_stats.return_value = mock_stats
        mock_get_metadata.return_value = {"pytest_version": "7.0.0", "packages": {}}
        mock_path_exists.return_value = True  # Make os.path.exists return True

        # Setup template mocks
        mock_template = MagicMock()
        mock_template.render.side_effect = jinja2.exceptions.UndefinedError(
            "Variable 'missing_variable' is undefined"
        )

        # Track file operations
        open_calls = []
        write_calls = []

        # Create mock file handlers
        css_mock = MagicMock()
        css_mock.read.return_value = "/* CSS content */"

        js_mock = MagicMock()
        js_mock.read.return_value = "// JS content with {{ results }}"

        html_mock = MagicMock()

        # Custom open side effect
        def mock_open_side_effect(filename, mode='r', *args, **kwargs):
            open_calls.append((filename, mode))

            if 'styles.css' in filename:
                return css_mock
            elif 'report.js' in filename:
                return js_mock
            else:
                # For HTML output file
                return html_mock

        # Track write calls
        html_mock.__enter__ = MagicMock(return_value=html_mock)
        html_mock.__exit__ = MagicMock(return_value=None)
        html_mock.write = MagicMock(side_effect=lambda content: write_calls.append(content))

        # Patch all required components
        with patch('jinja2.Environment') as mock_env_class, \
                patch('jinja2.FileSystemLoader'), \
                patch('jinja2.Template') as mock_template_class, \
                patch('builtins.open', side_effect=mock_open_side_effect):

            # Setup environment mock
            mock_env = MagicMock()
            mock_env_class.return_value = mock_env
            mock_env.filters = {}
            mock_env.get_template.return_value = mock_template

            # Setup JS template mock
            mock_js_template = MagicMock()
            mock_js_template.render.return_value = "rendered js content"
            mock_template_class.return_value = mock_js_template

            # Run the function - expect AssertionError
            with pytest.raises(AssertionError):
                generate_html_report(mock_session, MagicMock())

            # Verify CSS and JS files were read
            css_file_read = any('styles.css' in call[0] and call[1] == 'r' for call in open_calls)
            js_file_read = any('report.js' in call[0] and call[1] == 'r' for call in open_calls)
            assert css_file_read, "CSS file was not read"
            assert js_file_read, "JS file was not read"

            # Verify HTML file was written with error message
            html_file_written = any(call[1] == 'w' for call in open_calls)
            assert html_file_written, "HTML file was not opened for writing"

            # Verify error content was written
            assert len(write_calls) > 0, "No content was written to the file"
            written_content = ''.join(write_calls)
            assert "Error" in written_content
            assert "Template" in written_content

    @patch('html_reporter.report_handler.aggregate_results')
    @patch('html_reporter.report_handler.calculate_stats')
    @patch('html_reporter.report_handler.get_pytest_metadata')
    @patch('html_reporter.report_handler.os.path.exists')
    def test_template_runtime_error(self, mock_path_exists, mock_get_metadata,
                                    mock_calculate_stats, mock_aggregate_results,
                                    mock_session, mock_results, mock_stats):
        """Test handling TemplateRuntimeError."""
        mock_aggregate_results.return_value = mock_results
        mock_calculate_stats.return_value = mock_stats
        mock_get_metadata.return_value = {"pytest_version": "7.0.0", "packages": {}}
        mock_path_exists.return_value = True  # Make os.path.exists return True

        # Setup template mocks
        mock_template = MagicMock()
        mock_template.render.side_effect = jinja2.exceptions.TemplateRuntimeError(
            "Runtime error in template"
        )

        # Track file operations
        open_calls = []
        write_calls = []

        # Create mock file handlers
        css_mock = MagicMock()
        css_mock.read.return_value = "/* CSS content */"

        js_mock = MagicMock()
        js_mock.read.return_value = "// JS content with {{ results }}"

        html_mock = MagicMock()

        # Custom open side effect
        def mock_open_side_effect(filename, mode='r', *args, **kwargs):
            open_calls.append((filename, mode))

            if 'styles.css' in filename:
                return css_mock
            elif 'report.js' in filename:
                return js_mock
            else:
                # For HTML output file
                return html_mock

        # Track write calls
        html_mock.__enter__ = MagicMock(return_value=html_mock)
        html_mock.__exit__ = MagicMock(return_value=None)
        html_mock.write = MagicMock(side_effect=lambda content: write_calls.append(content))

        # Patch all required components
        with patch('jinja2.Environment') as mock_env_class, \
                patch('jinja2.FileSystemLoader'), \
                patch('jinja2.Template') as mock_template_class, \
                patch('builtins.open', side_effect=mock_open_side_effect):

            # Setup environment mock
            mock_env = MagicMock()
            mock_env_class.return_value = mock_env
            mock_env.filters = {}
            mock_env.get_template.return_value = mock_template

            # Setup JS template mock
            mock_js_template = MagicMock()
            mock_js_template.render.return_value = "rendered js content"
            mock_template_class.return_value = mock_js_template

            # Run the function - expect AssertionError
            with pytest.raises(AssertionError):
                generate_html_report(mock_session, MagicMock())

            # Verify CSS and JS files were read
            css_file_read = any('styles.css' in call[0] and call[1] == 'r' for call in open_calls)
            js_file_read = any('report.js' in call[0] and call[1] == 'r' for call in open_calls)
            assert css_file_read, "CSS file was not read"
            assert js_file_read, "JS file was not read"

            # Verify HTML file was written with error message
            html_file_written = any(call[1] == 'w' for call in open_calls)
            assert html_file_written, "HTML file was not opened for writing"

            # Verify error content was written
            assert len(write_calls) > 0, "No content was written to the file"
            written_content = ''.join(write_calls)
            assert "Error" in written_content
            assert "Template" in written_content

    @patch('html_reporter.report_handler.aggregate_results')
    @patch('html_reporter.report_handler.calculate_stats')
    @patch('html_reporter.report_handler.get_pytest_metadata')
    @patch('html_reporter.report_handler.os.path.exists')
    def test_general_jinja2_error(self, mock_path_exists, mock_get_metadata,
                                  mock_calculate_stats, mock_aggregate_results,
                                  mock_session, mock_results, mock_stats):
        """Test handling general Jinja2 error."""
        mock_aggregate_results.return_value = mock_results
        mock_calculate_stats.return_value = mock_stats
        mock_get_metadata.return_value = {"pytest_version": "7.0.0", "packages": {}}
        mock_path_exists.return_value = True  # Make os.path.exists return True

        # Setup template mocks
        mock_template = MagicMock()
        mock_template.render.side_effect = jinja2.exceptions.TemplateError(
            "General template error"
        )

        # Track file operations
        open_calls = []
        write_calls = []

        # Create mock file handlers
        css_mock = MagicMock()
        css_mock.read.return_value = "/* CSS content */"

        js_mock = MagicMock()
        js_mock.read.return_value = "// JS content with {{ results }}"

        html_mock = MagicMock()

        # Custom open side effect
        def mock_open_side_effect(filename, mode='r', *args, **kwargs):
            open_calls.append((filename, mode))

            if 'styles.css' in filename:
                return css_mock
            elif 'report.js' in filename:
                return js_mock
            else:
                # For HTML output file
                return html_mock

        # Track write calls
        html_mock.__enter__ = MagicMock(return_value=html_mock)
        html_mock.__exit__ = MagicMock(return_value=None)
        html_mock.write = MagicMock(side_effect=lambda content: write_calls.append(content))

        # Patch all required components
        with patch('jinja2.Environment') as mock_env_class, \
                patch('jinja2.FileSystemLoader'), \
                patch('jinja2.Template') as mock_template_class, \
                patch('builtins.open', side_effect=mock_open_side_effect):

            # Setup environment mock
            mock_env = MagicMock()
            mock_env_class.return_value = mock_env
            mock_env.filters = {}
            mock_env.get_template.return_value = mock_template

            # Setup JS template mock
            mock_js_template = MagicMock()
            mock_js_template.render.return_value = "rendered js content"
            mock_template_class.return_value = mock_js_template

            # Run the function - expect AssertionError
            with pytest.raises(AssertionError):
                generate_html_report(mock_session, MagicMock())

            # Verify CSS and JS files were read
            css_file_read = any('styles.css' in call[0] and call[1] == 'r' for call in open_calls)
            js_file_read = any('report.js' in call[0] and call[1] == 'r' for call in open_calls)
            assert css_file_read, "CSS file was not read"
            assert js_file_read, "JS file was not read"

            # Verify HTML file was written with error message
            html_file_written = any(call[1] == 'w' for call in open_calls)
            assert html_file_written, "HTML file was not opened for writing"

            # Verify error content was written
            assert len(write_calls) > 0, "No content was written to the file"
            written_content = ''.join(write_calls)
            assert "Error" in written_content
            assert "Template" in written_content

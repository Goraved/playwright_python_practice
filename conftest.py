"""
conftest.py

Pytest configuration file that sets up Playwright testing, database connections, and test metadata.
Most report-related logic has been moved to html_reporter/report_handler.py.
"""

import os
from pathlib import Path

import pytest
from _pytest.runner import CallInfo
from playwright.sync_api import Playwright, sync_playwright, Browser, BrowserContext, Page

from html_reporter.report_handler import generate_html_report
from utils.soft_assert import SoftAssertContextManager

# Constants
REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)


# Pytest Configuration
def pytest_addoption(parser):
    """Add custom command-line options"""
    parser.addoption("--headless", action="store", default="false", help="Run tests in headless mode (true/false)")
    parser.addoption("--html-report", action="store", default="reports/test_report.html",
                     help="Path to HTML report file")
    parser.addoption("--report-title", action="store", default="Test Automation Report",
                     help="Title for the HTML report")


@pytest.hookimpl
def pytest_configure(config):
    config.screenshots_amount = 0  # Limit the number of screenshots attached to reports.

    os.environ["HEADLESS"] = config.getoption("headless")


# Playwright Fixtures
@pytest.fixture(scope="session")
def playwright_instance() -> Playwright:
    """
    Set up the Playwright instance for the test session.
    This fixture initializes Playwright and yields the instance.

    Returns:
        Playwright: A configured Playwright instance with browser engines.
    """
    with sync_playwright() as playwright:
        # The sync_playwright context manager handles initialization and cleanup
        yield playwright
        # Playwright is automatically closed after all tests complete


@pytest.fixture(scope="session")
def browser(playwright_instance) -> Browser:
    """
    Launch a Chromium browser instance.
    The browser stays active for the entire session and closes after tests complete.

    Args:
        playwright_instance: The Playwright instance from the playwright_instance fixture

    Returns:
        Browser: A configured Chromium browser instance

    Environment Variables:
        HEADLESS: When 'true', runs the browser without a visible UI
    """
    if os.getenv('HEADLESS', 'false') == 'true' or os.getenv('GITHUB_RUN') is not None:
        # Launch in headless mode (no visible browser window)
        browser = playwright_instance.chromium.launch(headless=True)
    else:
        # Launch with visible browser window and maximize it
        browser = playwright_instance.chromium.launch(headless=os.getenv('HEADLESS', 'false') == 'true',
                                                      args=["--start-maximized"])
    yield browser
    # Ensure browser is closed after all tests complete
    browser.close()


@pytest.fixture(scope="session")
def browser_context(browser) -> BrowserContext:
    """
    Create a new browser context for the test module.
    Each context has isolated sessions, cookies, and storage to avoid test interference.

    Args:
        browser: The Browser instance from the browser fixture

    Returns:
        BrowserContext: An isolated browser context with its own cookies/storage

    Environment Variables:
        HEADLESS: When 'true', configures viewport dimensions for headless mode
    """
    if os.getenv('HEADLESS', 'false') == 'true':
        # Fixed viewport size for consistent testing in headless mode
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, screen={"width": 1920, "height": 1080})
    else:
        # Use system's native viewport size (maximized browser)
        context = browser.new_context(no_viewport=True)
    yield context
    # Clean up the context after module tests complete
    context.close()


@pytest.fixture(scope="session")
def page(request, browser_context) -> Page:
    """
    Create a new page within the browser context for testing.

    Args:
        request: The pytest request object for test metadata access
        browser_context: The BrowserContext instance from the browser_context fixture

    Returns:
        Page: A new browser page for test automation

    Notes:
        - Attaches the page to the request node for access in other fixtures/hooks
        - Automatically handles logout before closing the page
    """
    # Create a new page in the current browser context
    page = browser_context.new_page()
    # Attach page to pytest request for access in other fixtures/hooks
    request.node.page = page
    yield page
    # Close the page to clean up resources
    page.close()


# Pytest Hooks
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call: CallInfo) -> None:
    """
    Create detailed test reports with rich metadata for all test phases.

    This hook captures test outcomes, screenshots, logs, and exception details for reporting
    during setup, call, and teardown phases. The implementation has been refactored to use
    the TestResultHandler class for improved maintainability.

    Args:
        item: The pytest test item being run
        call: Information about the test function call
    """
    # Import the handler here to avoid circular imports
    from html_reporter.result_handler import ResultHandler

    # Yield to allow pytest to generate the report first
    outcome = yield
    report = outcome.get_result()

    # Use the handler class to process the test result
    handler = ResultHandler(item.config)
    handler.process_test_result(item, call, report)


@pytest.hookimpl
def pytest_sessionfinish(session):
    """
    Generate final HTML report and clean up resources after all tests finish.

    This hook runs after all tests have completed execution to:
    1. Clean up orphaned Playwright browser processes
    2. Generate a consolidated HTML report from individual test results
    3. Remove temporary JSON files after report generation

    Args:
        session: The pytest session object containing test information
    """
    # Force cleanup of any remaining browser processes to prevent resource leaks
    import psutil
    current_pid = os.getpid()

    # Only clean processes related to current worker to avoid affecting other test runs
    for proc in psutil.process_iter():
        try:
            # Check if process is child of current process and is a Playwright browser
            if proc.ppid() == current_pid and 'playwright' in proc.name().lower():
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Skip processes we can't access or that no longer exist
            pass

    # Skip report generation on worker nodes in distributed testing
    if hasattr(session.config, "workerinput"):
        return  # Skip on worker nodes - only master node generates the report

    # Generate the consolidated HTML report from all collected test results
    generate_html_report(session, REPORT_DIR)

    # Clean up individual test result JSON files after the report is generated
    # This happens last to ensure report generation completes successfully
    for json_file in REPORT_DIR.glob("*.json"):
        json_file.unlink(missing_ok=True)


# Test logging helper
@pytest.fixture
def test_logger(request):
    """
    Fixture to add logs to test results that will be included in the final report.

    Args:
        request: The pytest request object

    Returns:
        callable: A function that adds messages to the test logs
    """

    def _log_message(message: str):
        if not hasattr(request.node, "test_logs"):
            request.node.test_logs = []
        request.node.test_logs.append(message)

    return _log_message


@pytest.fixture
def soft_assert(request):
    """
    Provides a soft assertion mechanism that collects failures without stopping test execution.

    Creates a SoftAssertContextManager and attaches it to the test item for later
    access during test result processing. This allows multiple assertions to be checked
    within a single test while collecting all failures.

    Args:
        request: The pytest request object

    Returns:
        SoftAssertContextManager: Soft assertion context for collecting multiple failures
    """
    context = SoftAssertContextManager()
    request.node._soft_assert = context  # Attach to the pytest item for later access
    return context


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """
    Hook to track the currently running test item throughout the test framework.

    Sets a global reference to the current test item that can be accessed
    by utilities that don't receive the test item directly.

    Args:
        item: The current test item being executed
        nextitem: The next test item to be executed
    """
    pytest.current_item = item
    yield
    pytest.current_item = None


@pytest.hookimpl(tryfirst=True)
def pytest_configure_node(node):
    """
    Logs when a worker node is configured in distributed testing mode.

    This provides visibility into test distribution and parallel execution status.

    Args:
        node: The worker node being configured
    """
    node.log.info(f"Worker {node.gateway.id} is configured and starting")


@pytest.hookimpl(tryfirst=True)
def pytest_testnodedown(node, error):
    """
    Logs the status of a worker node when it completes testing.

    Provides error details if the node failed or a success message if it completed normally.

    Args:
        node: The worker node that has finished
        error: Error information if the node failed, None otherwise
    """
    if error:
        node.log.error(f"Worker {node.gateway.id} failed: {error}")
    else:
        node.log.info(f"Worker {node.gateway.id} finished successfully")

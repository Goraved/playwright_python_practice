import asyncio
import os

import allure
import pytest
from playwright import sync_playwright


# Will mark all the tests as async
def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.asyncio)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session')
def page():
    with sync_playwright() as play:
        if os.getenv('DOCKER_RUN'):
            browser = play.chromium.launch(headless=True, args=['--no-sandbox'])
        else:
            browser = play.firefox.launch(headless=False)
        page = browser.newPage()
        global PAGE
        PAGE = page
        yield page
        browser.close()


PAGE = None


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport():
    outcome = yield
    test_result = outcome.get_result()

    if test_result.when in ["setup", "call"]:
        xfail = hasattr(test_result, 'wasxfail')
        if test_result.failed or (test_result.skipped and xfail):
            loop = asyncio.get_event_loop()
            screenshot = loop.run_until_complete(get_screenshot())
            allure.attach(screenshot, name='screenshot', attachment_type=allure.attachment_type.PNG)


def get_screenshot():
    global PAGE
    return PAGE.screenshot()

from typing import Optional

from playwright.sync_api import Locator, Page, expect

from utils.track_time import track_execution_time


class BaseElement:
    """
    BaseElement is a wrapper class for Playwright's Locator object, providing
    common interaction methods for web elements like clicking, typing, and uploading files.

    :param locator: Locator to target the specific web element.
    :param page: Playwright Page object, representing the browser tab.
    :param default_timeout: Default timeout for element interactions in milliseconds (default is 5000 ms).
    """

    def __init__(self, locator: Locator, page: Page, default_timeout: int = 10000):
        """
        Initialize BaseElement with the provided locator, page, and default timeout.

        :param locator: Locator to target the web element.
        :param page: Playwright Page object.
        :param default_timeout: Default timeout for element interactions (default is 5000 ms).
        """
        self.raw: Locator = locator  # The actual located web element
        self.page = page
        self._default_timeout = default_timeout

    @property
    def text(self) -> str:
        """
        Get the text content of the element.

        :return: The text content as a string.
        """
        return self.raw.text_content(timeout=self._default_timeout).strip()

    @property
    def value(self) -> str:
        """
        Get the value of the element, usually for input elements.

        :return: The value attribute of the element.
        """
        return self.raw.input_value(timeout=self._default_timeout)

    @property
    def is_enabled(self) -> bool:
        """
        Check if the element is both visible and enabled (clickable).

        :return: True if the element is clickable, False otherwise.
        """
        return not self.raw.is_disabled() and self.raw.is_visible()

    @property
    def is_visible(self) -> bool:
        """
        Check if the element is visible.

        :return: True if the element is visible, False otherwise.
        """
        return self.raw.is_visible()

    @track_execution_time
    def click(self, force: bool = False) -> None:
        """
        Click the element. Optionally force the click, bypassing visibility and interaction constraints.

        :param force: If True, forces the click even if the element is not interactable (default is False).
        """
        self.raw.click(timeout=self._default_timeout, force=force)

    def click_using_js(self) -> None:
        """
        Click the element using JavaScript by evaluating a JS function on the element.
        This can be used to bypass Playwright's default behavior when an element is overlapped.

        :raises Exception: If the element handle is not found.
        """
        element_handle = self.raw.element_handle()  # Get the actual DOM element handle
        if element_handle:  # Ensure that the handle is found
            self.page.evaluate("(element) => element.click()", element_handle)

    def double_click(self, force: bool = False) -> None:
        """
        Perform a double-click on the element.

        :param force: If True, forces the double-click even if the element is not interactable (default is False).
        """
        self.raw.dblclick(timeout=self._default_timeout, force=force)

    @track_execution_time
    def fill(self, text: str) -> None:
        """
        Clear any existing content and fill the element with the provided text.

        This method ensures that the input field is cleared before typing the new text.

        Args:
            text (str): The text to fill into the element.

        Raises:
            playwright._impl._api_types.TimeoutError: If the action cannot be completed within the default timeout.
        """
        self.raw.fill(text, timeout=self._default_timeout)

    def type(self, text: str) -> None:
        """
        Type the provided text into the element, one character at a time.

        Unlike `fill`, this method simulates typing, which triggers events like `keydown`, `keypress`, and `keyup`.

        Args:
            text (str): The text to type into the element.

        Raises:
            playwright._impl._api_types.TimeoutError: If the action cannot be completed within the default timeout.
        """
        self.raw.type(text, timeout=self._default_timeout)

    def press(self, button: str) -> None:
        """
        Simulate a key press action on the element.

        Args:
            button (str): The key to press, e.g., "Enter", "Tab", "ArrowDown".

        Raises:
            playwright._impl._api_types.TimeoutError: If the action cannot be completed within the default timeout.
        """
        self.raw.press(button, timeout=self._default_timeout)

    def clear(self) -> None:
        """
        Clear input
        """
        self.raw.clear()

    def upload_files(self, file_paths: list[str]) -> None:
        """
        Upload files to an <input type="file"> element.

        :param file_paths: A list of file paths to upload.
        """
        self.raw.set_input_files(file_paths, timeout=self._default_timeout)

    def get_attribute(self, name: str) -> Optional[str]:
        """
        Get the value of a specified attribute of the element.

        :param name: The name of the attribute to retrieve.
        :return: The attribute value as a string or None if not found.
        """
        return self.raw.get_attribute(name, timeout=self._default_timeout)

    def hover(self, force: bool = False) -> None:
        """
        Hover over the element. Optionally force the hover, bypassing constraints.

        :param force: If True, forces the hover even if the element is not interactable (default is False).
        """
        self.raw.hover(timeout=self._default_timeout, force=force)

    def save_screenshot(self, path: str) -> None:
        """
        Save a screenshot of the current state of the element.

        :param path: The file path where the screenshot will be saved.
        """
        self.raw.screenshot(path=path)

    @track_execution_time
    def wait_until_hidden(self, timeout: int = 15000) -> None:
        """
        Wait until the element is hidden, either removed from the DOM or made invisible.

        :param timeout: Time to wait in milliseconds (default is 10000 ms).
        """
        self.raw.wait_for(state="hidden", timeout=timeout)

    @track_execution_time
    def wait_until_visible(self, timeout: int = 15000):
        """
        Wait until the element becomes visible on the page.

        This method ensures that the element is present in the DOM and is not hidden
        (e.g., has `display: none` or `visibility: hidden` styles applied).

        Args:
            timeout (int): Maximum time to wait for the element to become visible, in milliseconds.
                           Defaults to 15000 (15 seconds).

        Raises:
            playwright._impl._api_types.TimeoutError: If the element does not become visible within the specified timeout.
        """
        self.raw.wait_for(state="visible", timeout=timeout)
        return self

    @track_execution_time
    def wait_until_enabled(self, timeout: int = 15000) -> None:
        """
        Wait until the element becomes enabled (interactive) using Playwright's expect logic.

        Args:
            timeout (int): Maximum time to wait in milliseconds. Defaults to 15000 (15 seconds).

        Raises:
            playwright._impl._api_types.TimeoutError: If the element does not become enabled within the timeout.
        """
        expect(self.raw).to_be_enabled(timeout=timeout)

    @track_execution_time
    def wait_until_disabled(self, timeout: int = 15000) -> None:
        """
        Wait until the element becomes disabled (non-interactive) using Playwright's expect logic.

        Args:
            timeout (int): Maximum time to wait in milliseconds. Defaults to 15000 (15 seconds).

        Raises:
            playwright._impl._api_types.TimeoutError: If the element does not become disabled within the timeout.
        """
        expect(self.raw).to_be_disabled(timeout=timeout)

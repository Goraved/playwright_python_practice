from typing import Union, Any, Optional

from playwright._impl._sync_base import EventContextManager
from playwright.sync_api import Page, Locator

from pages.common.base_element import BaseElement
from pages.common.intercept import RequestResponseModifier
from utils.track_time import track_execution_time


class BasePage:
    """
    A base class for handling common web page actions in Playwright.
    Provides methods for navigation, finding elements, reloading the page, and handling asynchronous responses.
    """

    def __init__(self, page: Page):
        """
        Initialize the BasePage with a given Playwright page object.

        Args:
            page (Page): The Playwright page object.
        """
        self.page = page

    @property
    def intercept(self) -> RequestResponseModifier:
        """
        Provides an instance of the RequestResponseModifier class, allowing the modification
        of requests and responses for the current page.

        Returns:
            RequestResponseModifier: An object that facilitates request and response interception,
                                     enabling modifications to URL parameters, request bodies,
                                     and response bodies as needed.
        """
        return RequestResponseModifier(self.page)

    @track_execution_time
    def open(self, url: str, wait: bool = True) -> None:
        """
        Navigate to the specified URL and optionally wait for the page to fully load.

        Args:
            url (str): The URL of the page to open.
            wait (bool): Whether to wait for the page to fully load. Default is True.
        """
        self.page.goto(url)
        if wait:
            self.wait_for_page_load()

    def find_element(self, selector: Union[str, Locator]) -> BaseElement:
        """
        Find a single element on the page.

        Args:
            selector (Union[str, Locator]): CSS or XPath selector, or a Playwright Locator object.

        Returns:
            BaseElement: A BaseElement object wrapping the located element.
        """
        if type(selector) is str:
            return BaseElement(self.page.locator(selector), self.page)
        else:
            return BaseElement(selector, self.page)

    def find_elements(self, selector: str, wait: bool = True) -> list[BaseElement]:
        """
        Find multiple elements on the page using the given selector.

        Args:
            selector (str): CSS or XPath selector.
            wait (bool): Whether to wait for the first element to become visible before proceeding. Default is True.

        Returns:
            list[BaseElement]: A list of BaseElement objects wrapping the located elements.
        """
        if wait:
            self.page.locator(selector).nth(0).wait_for(state='visible')
        locators = self.page.locator(selector).all()
        return [BaseElement(locator, self.page) for locator in locators]

    def get_list_of_components(self, selector: str, component: Any) -> list:
        """
        Return a list of component objects found using the provided selector.

        Args:
            selector (str): CSS or XPath selector to locate components on the page.
            component (Any): The component class to instantiate for each located element.

        Returns:
            list: A list of component objects.

        Usage example:
            self.get_list_of_components('//div[contains(@class,"chart-card")]', Chart)
        """
        return [component(locator=locator, page=self.page) for locator in self.page.locator(selector).all()]

    def reload(self) -> None:
        """
        Reload the current page.
        """
        self.page.reload()

    @track_execution_time
    def wait_for_page_load(self, anchor_selector: Optional[str] = None) -> None:
        """
        Wait for the page to fully load and check for the presence of an optional anchor element.

        Args:
            anchor_selector (Optional[str]): CSS or XPath selector for an anchor element to wait for. Default is None.
        """
        self.page.wait_for_load_state(state="load")
        self.wait_for_loader()
        if anchor_selector:
            self.find_element(anchor_selector).wait_until_visible(timeout=30000)

    @track_execution_time
    def wait_for_loader(self) -> None:
        """
        Wait for a loader element on the page to become hidden.
        The loader is identified by the XPath '//div[@data-xpath="component-loader"]'.
        """
        self.find_element('//div[@data-xpath="component-loader"]').wait_until_hidden(timeout=30000)

    @track_execution_time
    def catch_response(self, url_pattern: str, timeout: int = 10) -> EventContextManager:
        """
        Wait for a network response that matches the given URL pattern.

        Args:
            url_pattern (str): The URL pattern to match the response.
            timeout (int): The maximum time to wait for the response in seconds. Default is 10 seconds.

        Returns:
            EventContextManager: The Playwright event context manager for handling the response.
        """
        return self.page.expect_response(url_pattern, timeout=timeout * 1000)

    def scroll_to_bottom(self) -> None:
        """
        Scroll to the bottom of the page.

        This method uses JavaScript to scroll the window to the bottom of the document body.
        It can be useful for loading content that appears when the user scrolls down.
        """
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

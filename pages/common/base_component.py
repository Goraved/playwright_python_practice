from functools import lru_cache
from typing import Union, Any, Optional

from playwright.sync_api import Locator, Page, FrameLocator

from pages.common.base_element import BaseElement
from pages.common.base_page import BasePage


class BaseComponent(BasePage):
    def __init__(self, locator: Union[Locator, FrameLocator], page: Page):
        """
        :param locator: The root element that defines the component's scope.
        :param page: The Playwright Page instance (optional, as the component could exist without explicit page context).
        """
        self.root = locator  # The root locator of the component
        self.page = page
        super().__init__(page)

    @property
    def element(self) -> BaseElement:
        """
        Get the root base element of the component.

        Returns:
        BaseElement: The base element representing the component's root.
        """
        return BaseElement(self.root, self.page)

    @property
    def is_enabled(self) -> bool:
        """
        Check if the root element of the component is clickable.
        """
        return self.element.is_enabled

    @property
    def is_visible(self) -> bool:
        """
        Check if the component is visible.

        :return: True if visible, False otherwise.
        """
        return self.root.is_visible()

    @lru_cache(maxsize=32)
    def child_el(self, selector: Optional[str] = None, component: Optional[Any] = None,
                 label: Optional[str] = None) -> Union[BaseElement, Any]:
        """
        Find an element within the component's scope.
        """
        assert selector or label
        if component:
            if not label:
                return component(page=self.page, selector=selector, root=self.root)
            else:
                return component(label=label, page=self.page, selector=selector, root=self.root)
        else:
            return BaseElement(self.root.locator(selector), self.page)

    def child_elements(self, selector: str) -> list[BaseElement]:
        """
        Find multiple elements within the component's scope.

        :param selector: CSS or XPath selector for elements within the component.
        :return: A list of BaseElement objects.
        """
        locators = self.root.locator(selector).all()
        return [BaseElement(locator, self.page) for locator in locators]

    def get_list_of_components(self, selector: str, component: Any, index: bool = False) -> list:
        """
        Return list of component objects.

        Usage example:
            self.get_list_of_components('//div[contains(@class,"chart-card")]', Chart)
        """
        if not index:
            return [component(locator=locator, page=self.page) for locator in self.element.raw.locator(selector).all()]
        else:
            return [component(locator=locator, page=self.page, index=index) for index, locator in
                    enumerate(self.element.raw.locator(selector).all())]

    def wait_for_visibility(self, timeout: int = 5000) -> None:
        """
        Wait until the component's root element is visible.

        :param timeout: Timeout in milliseconds.
        """
        self.root.wait_for(state="visible", timeout=timeout)

    def wait_for_invisibility(self, timeout: int = 5000) -> None:
        """
        Wait until the component's root element is hidden.

        :param timeout: Timeout in milliseconds.
        """
        self.root.wait_for(state="hidden", timeout=timeout)

    def scroll_into_view(self) -> None:
        """
        Scroll the component's root element into view.
        """
        self.root.scroll_into_view_if_needed()

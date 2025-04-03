from typing import Optional

from playwright.sync_api import Page, Locator

from pages.common.base_component import BaseComponent
from pages.common.base_element import BaseElement
from pages.common.base_page import BasePage


class CartItem(BaseComponent):
    selector = '//div[@data-test="inventory-item"]'

    def __init__(self, page: Page, selector: str = selector, locator: Optional[Locator] = None):
        """
        Initialize a CartItem component.

        Args:
            page (Page): The Playwright page object.
            selector (str): The selector used to locate this component. Defaults to the class selector.
            locator (Optional[Locator]): An existing locator for this component. If provided,
                                         selector will be ignored. Defaults to None.
        """
        if not locator:
            super().__init__(page.locator(selector), page)
        else:
            super().__init__(locator, page)

    @property
    def title(self) -> str:
        return self.child_el('//div[@data-test="inventory-item-name"]').text

    @property
    def description(self) -> str:
        return self.child_el('//div[@data-test="inventory-item-desc"]').text

    @property
    def price(self) -> str:
        return self.child_el('//div[@data-test="inventory-item-price"]').text

    @property
    def quantity(self) -> str:
        return self.child_el('//div[@data-test="item-quantity"]').text

    @property
    def remove_button(self) -> BaseElement:
        return self.child_el('//button[@data-test="remove-sauce-labs-backpack"]')

    @property
    def link(self) -> BaseElement:
        return self.child_el('//a[contains(@data-test, "title-link")]')


class CartPage(BasePage):

    @property
    def continue_shopping_button(self) -> BaseElement:
        return self.find_element('//button[@data-test="continue-shopping"]')

    @property
    def checkout_button(self) -> BaseElement:
        return self.find_element('//button[@data-test="checkout"]')

    @property
    def cart_items(self) -> list[CartItem]:
        """
        Get a list of CartItem components on the page.

        :return: List of CartItem components.
        """
        return self.get_list_of_components(selector=CartItem.selector, component=CartItem)

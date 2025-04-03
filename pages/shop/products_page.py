from typing import Optional

from playwright.sync_api import Page, Locator

from pages.common.base_component import BaseComponent
from pages.common.base_element import BaseElement
from pages.common.base_page import BasePage


class ProductCard(BaseComponent):
    selector = '//div[@data-test="inventory-item"]'

    def __init__(self, page: Page, selector: str = selector, locator: Optional[Locator] = None):
        """
        Initialize a ProductCard component.

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
        return self.child_el('//div[@class="inventory_item_desc"]').text

    @property
    def price(self) -> str:
        return self.child_el('//div[@class="inventory_item_price"]').text

    @property
    def link(self) -> BaseElement:
        return self.child_el('//div[@class="inventory_item_label"]/a')

    @property
    def add_to_cart_button(self) -> BaseElement:
        return self.child_el('//button[text()="Add to cart"]')

    @property
    def remove_from_cart_button(self) -> BaseElement:
        return self.child_el('//button[text()="Remove"]')

    @property
    def is_added_to_cart(self) -> bool:
        """
        Check if the product is added to the cart.

        :return: True if the product is added to the cart, False otherwise.
        """
        return self.remove_from_cart_button.is_visible and not self.add_to_cart_button.is_visible


class ProductsPage(BasePage):
    @property
    def cart_button(self) -> BaseElement:
        return self.find_element('//a[@data-test="shopping-cart-link"]')

    @property
    def sort_dropdown(self) -> BaseElement:
        return self.find_element('//select[@data-test="product-sort-container"]')

    @property
    def cart_badge(self) -> BaseElement:
        return self.find_element('//span[@data-test="shopping-cart-badge"]')

    @property
    def product_cards(self) -> list[ProductCard]:
        """
        Get all product cards on the page.

        :return: List of ProductCard objects.
        """
        return self.get_list_of_components(selector=ProductCard.selector, component=ProductCard)

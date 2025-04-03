from functools import cached_property

from playwright.sync_api import Page

from pages.login.login_page import LoginPage
from pages.shop.cart_page import CartPage
from pages.shop.checkout_form import CheckoutForm
from pages.shop.products_page import ProductsPage


class Pages:
    """
    Provides access to all pages and components, grouped by logical sections.
    """

    def __init__(self, page: Page):
        self.page = page

    # Top-level pages
    @cached_property
    def products_page(self) -> ProductsPage:
        return ProductsPage(self.page)

    @cached_property
    def cart_page(self) -> CartPage:
        return CartPage(self.page)

    @cached_property
    def checkout_form(self) -> CheckoutForm:
        return CheckoutForm(self.page)

    @cached_property
    def login_page(self) -> LoginPage:
        return LoginPage(self.page)

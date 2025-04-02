from functools import cached_property

from playwright.sync_api import Page

from pages.registation.registration_object import RegistrationPage
from pages.shop.shop_object import ShopPage


class Pages:
    """
    Provides access to all pages and components, grouped by logical sections.
    """

    def __init__(self, page: Page):
        self.page = page

    # Top-level pages
    @cached_property
    def shop_page(self) -> ShopPage:
        return ShopPage(self.page)

    @cached_property
    def registration_page(self) -> RegistrationPage:
        return RegistrationPage(self.page)
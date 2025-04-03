from pages.common.base_element import BaseElement
from pages.common.base_page import BasePage


class LoginPage(BasePage):

    def open_page(self) -> None:
        """
        Open the login page.
        """
        self.open('https://www.saucedemo.com/')

    @property
    def username_input(self) -> BaseElement:
        return self.find_element('//input[@data-test="username"]')

    @property
    def password_input(self) -> BaseElement:
        return self.find_element('//input[@data-test="password"]')

    @property
    def login_button(self) -> BaseElement:
        return self.find_element('//input[@data-test="login-button"]')

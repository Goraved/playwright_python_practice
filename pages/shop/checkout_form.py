from pages.common.base_element import BaseElement
from pages.common.base_page import BasePage


class CheckoutForm(BasePage):
    @property
    def first_name_input(self) -> BaseElement:
        return self.find_element('//input[@data-test="firstName"]')

    @property
    def last_name_input(self) -> BaseElement:
        return self.find_element('//input[@data-test="lastName"]')

    @property
    def zip_code_input(self) -> BaseElement:
        return self.find_element('//input[@data-test="postalCode"]')

    @property
    def cancel_button(self) -> BaseElement:
        return self.find_element('//button[@data-test="cancel"]')

    @property
    def continue_button(self) -> BaseElement:
        return self.find_element('//input[@data-test="continue"]')

    @property
    def finish_button(self) -> BaseElement:
        return self.find_element('//button[@data-test="finish"]')

    @property
    def pony_express_image(self) -> BaseElement:
        return self.find_element('//img[@data-test="pony-express"]')

    @property
    def complete_header(self) -> BaseElement:
        return self.find_element('//h2[@data-test="complete-header"]')

    @property
    def complete_text(self) -> BaseElement:
        return self.find_element('//div[@data-test="complete-text"]')

    @property
    def back_to_products_button(self) -> BaseElement:
        return self.find_element('//button[@data-test="back-to-products"]')

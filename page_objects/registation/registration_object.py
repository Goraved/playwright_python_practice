from random import randint

from page_objects.base_page import BasePage
from page_objects.registation.registration_locators import RegistrationLocators


class RegistrationPage(BasePage):
    async def register_account(self):
        await self.type(RegistrationLocators.EMAIL_INPUT, f'goraved@{randint(1000, 99999)}.com')
        await self.click(RegistrationLocators.CREATE_BTN)
        await self.click(RegistrationLocators.GENDER_OPTION)
        await self.type(RegistrationLocators.CUSTOMER_FIRST_NAME_INPUT, "Test")
        await self.type(RegistrationLocators.CUSTOMER_LAST_NAME_INPUT, "Goraved")
        await self.type(RegistrationLocators.PASSWORD_INPUT, "123asd")
        await self.select_option(RegistrationLocators.DAYS_SELECTOR, "1")
        await self.select_option(RegistrationLocators.MONTHS_SELECTOR, "1")
        await self.select_option(RegistrationLocators.YEARS_SELECTOR, "2020")
        await self.click(RegistrationLocators.AGREE_CHECKBOX)
        await self.click(RegistrationLocators.NEWSLETTER_CHECKBOX)
        await self.type(RegistrationLocators.FIRST_NAME_INPUT, 'Test')
        await self.type(RegistrationLocators.LAST_NAME_INPUT, 'Goraved')
        await self.type(RegistrationLocators.ADDRESS_INPUT, "street")
        await self.type(RegistrationLocators.CITY_INPUT, "test")
        await self.select_option(RegistrationLocators.STATE_SELECT, "1")
        await self.type(RegistrationLocators.POSTCODE_INPUT, "11111")
        await self.type(RegistrationLocators.OTHER_INPUT, "123")
        await self.type(RegistrationLocators.PHONE_INPUT, "123")
        await self.click(RegistrationLocators.ALIAS_BTN)
        await self.click(RegistrationLocators.SUBMIT_ACCOUNT_BTN)

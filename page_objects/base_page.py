import allure
from playwright.helper import TimeoutError as TE
from playwright.page import Page


class BasePage:
    def __init__(self, page: Page):
        self.page = page

    @allure.step('Click locator - {locator}')
    async def click(self, locator):
        await self.page.click(locator)

    @allure.step('Check checkbox locator - {locator}')
    async def check(self, locator):
        await self.page.check(locator)

    @allure.step('Uncheck checkbox locator - {locator}')
    async def uncheck(self, locator):
        await self.page.check(locator)

    @allure.step('Hover locator - {locator}')
    async def hover(self, locator):
        await self.page.hover(locator)

    @allure.step('Go to url - {url}')
    async def go_to_url(self, url):
        await self.page.goto(url)

    @allure.step('Type text - {text} into locator - {locator}')
    async def type(self, locator, text):
        await self.click(locator)
        await self.page.fill(locator, text)

    @allure.step('Select option - {option} in locator - {locator}')
    async def select_option(self, locator, option):
        await self.page.selectOption(locator, option)

    @allure.step('Is element - {locator} present')
    async def is_element_present(self, locator):
        try:
            await self.page.waitForSelector(locator)
            return True
        except TE:
            return False

    @allure.step('Is element - {locator} hidden')
    async def is_element_present(self, locator):
        try:
            await self.page.waitForSelector(locator, {'state': 'hidden'})
            return True
        except TE:
            return False

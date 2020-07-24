from page_objects.base_page import BasePage
from page_objects.shop.shop_locators import ShopLocators


class ShopPage(BasePage):
    async def open_site(self):
        await self.go_to_url('http://automationpractice.com/index.php')

    async def open_t_shirt_category(self):
        await self.click(ShopLocators.T_SHIRT_CATEGORY_BTN)

    async def add_item_to_cart_and_proceed(self):
        await self.hover(ShopLocators.ITEM_NAME_LBL)
        await self.click(ShopLocators.ITEM_NAME_LBL)
        await self.click(ShopLocators.ADD_TO_CART_BTN)
        await self.click(ShopLocators.PROCEED_TO_CHECKOUT_BTN)

    async def go_to_the_second_cart_step(self):
        await self.click(ShopLocators.SECOND_CART_STEP_BTN)

    async def finish_order_after_registration(self):
        await self.click('#center_column > form > p > button')
        await self.click(ShopLocators.TERMS_CHECKBOX)
        await self.click('#form > p > button')
        await self.click(ShopLocators.PAY_WITH_BANK_BTN)
        await self.click(ShopLocators.CONFIRM_ORDER_BTN)

    async def open_profile_order_page(self):
        await self.click(ShopLocators.PROFILE_BTN)
        await self.click(ShopLocators.ORDERS_BTN)

    async def is_order_present(self):
        return await self.is_element_present(ShopLocators.ORDER_ROW)

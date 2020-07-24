import allure
from allure_commons._allure import step

from page_objects.registation.registration_object import RegistrationPage
from page_objects.shop.shop_object import ShopPage


@allure.story('Shop')
class TestShop:
    @allure.title('Order T-Shirt')
    async def test_order_t_shirt(self, page):
        shop_page = ShopPage(page)
        registration_page = RegistrationPage(page)
        with step('Open site'):
            await shop_page.open_site()
        with step('Open T-Shirt category'):
            await shop_page.open_t_shirt_category()
        with step('Add item to cart and proceed'):
            await shop_page.add_item_to_cart_and_proceed()
        with step("Go to the second cart step"):
            await shop_page.go_to_the_second_cart_step()
        with step('Register new account'):
            await registration_page.register_account()
        with step('Finish order after registration'):
            await shop_page.finish_order_after_registration()
        with step('Open profile orders page'):
            await shop_page.open_profile_order_page()
        with step('Check at least 1 order present'):
            assert await shop_page.is_order_present(), 'Order missed'

    @allure.title('Negative to check attachments')
    async def test_negative(self, page):
        shop_page = ShopPage(page)
        with step('Open site'):
            await shop_page.open_site()
        with step('Fail test'):
            assert False

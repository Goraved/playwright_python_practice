import os

import allure
import pytest
from allure_commons._allure import step

from pages import Pages


class TestShop:
    def test_order_t_shirt(self, page):
        """
        Steps:
        1. Open site
        2. Open T-Shirt category
        3. Add item to cart and proceed
        4. Go to the second cart step
        5. Register new account
        6. Finish order after registration
        7. Open profile orders page
        8. Check at least 1 order present
        """
        pages = Pages(page)
        # Step 1
        pages.shop_page.open_site()
        # Step 2
        pages.shop_page.open_t_shirt_category()
        # Step 3
        pages.shop_page.add_item_to_cart_and_proceed()
        # Step 4
        pages.shop_page.go_to_the_second_cart_step()
        # Step 5
        pages.registration_page.register_account()
        # Step 6
        pages.shop_page.finish_order_after_registration()
        # Step 7
        pages.shop_page.open_profile_order_page()
        # Step 8
        assert pages.shop_page.is_order_present(), 'Order missed'

    @pytest.mark.skipif(os.getenv('GITHUB_RUN') is not None, reason='GitHub actions')
    def test_negative(self, page):
        pages = Pages(page)
        with step('Open site'):
            pages.shop_page.open_site()
        with step('Fail test'):
            assert False

import os

import pytest

from pages import Pages
from utils.track_time import track_execution_time


class TestShop:

    @pytest.fixture(scope='class')
    @track_execution_time
    def login(self, page):
        pages = Pages(page)
        pages.login_page.open_page()
        pages.login_page.username_input.fill('standard_user')
        pages.login_page.password_input.fill('secret_sauce')
        pages.login_page.login_button.click()
        pages.products_page.sort_dropdown.wait_until_visible()

    @pytest.mark.meta(case_id='AQA-1', case_title='Order T-Shirt Test', case_link='http://testcase.link/AQA-1')
    def test_order_t_shirt(self, page, login):
        """
        Steps:
        1. Verify the number of products displayed.
        2. Verify the details of the first product.
        3. Verify the description of the first product.
        4. Verify the price of the first product.
        5. Add the first product to the cart and verify.
        6. Remove the product from the cart and verify.
        7. Add the product to the cart again and proceed to the cart page.
        8. Verify the cart item details.
        9. Proceed to the checkout form.
        10. Fill in the checkout form and continue.
        11. Complete the checkout process and verify the confirmation.
        12. Return to the products page.
        """
        pages = Pages(page)
        # Step 1
        products = pages.products_page.product_cards
        assert len(products) == 6

        # Step 2
        product = products[0]
        assert product.title == 'Sauce Labs Backpack'
        # Step 3
        assert product.description == ('carry.allTheThings() with the sleek, streamlined Sly Pack that melds '
                                       'uncompromising style with unequaled laptop and tablet protection.')
        # Step 4
        assert product.price == '$29.99'

        # Step 5
        assert not product.is_added_to_cart
        product.add_to_cart_button.click()
        assert product.is_added_to_cart
        assert pages.products_page.cart_badge.is_visible
        assert pages.products_page.cart_badge.text == '1'

        # Step 6
        product.remove_from_cart_button.click()
        assert not product.is_added_to_cart
        assert not pages.products_page.cart_badge.is_visible

        # Step 7
        product.add_to_cart_button.click()
        pages.products_page.cart_button.click()
        pages.cart_page.checkout_button.wait_until_visible()

        # Step 8
        assert len(pages.cart_page.cart_items) == 1
        cart_item = pages.cart_page.cart_items[0]
        assert cart_item.title == 'Sauce Labs Backpack'
        assert cart_item.description == ('carry.allTheThings() with the sleek, streamlined Sly Pack that melds '
                                         'uncompromising style with unequaled laptop and tablet protection.')
        assert cart_item.price == '$29.99'
        assert cart_item.quantity == '1'

        # Step 9
        pages.cart_page.checkout_button.click()
        pages.checkout_form.first_name_input.wait_until_visible()

        # Step 10
        pages.checkout_form.first_name_input.fill('John')
        pages.checkout_form.last_name_input.fill('Doe')
        pages.checkout_form.zip_code_input.fill('12345')
        pages.checkout_form.continue_button.click()

        # Step 11
        pages.checkout_form.finish_button.click()
        pages.checkout_form.pony_express_image.wait_until_visible()
        assert pages.checkout_form.complete_header.text == 'Thank you for your order!'
        assert pages.checkout_form.complete_text.text == 'Your order has been dispatched, and will arrive just as fast as the pony can get there!'
        assert pages.checkout_form.back_to_products_button.is_visible

        # Step 12
        pages.checkout_form.back_to_products_button.click()
        pages.products_page.sort_dropdown.wait_until_visible()

    @pytest.mark.skipif(os.getenv('GITHUB_RUN') is not None, reason='GitHub actions')
    @pytest.mark.meta(case_id='AQA-2', case_title='Negative Test Case', case_link='http://testcase.link/AQA-2')
    def test_negative(self, login):
        """
        Steps:
        1. Fail test to verify the html report
        """
        # Step 1
        pytest.fail('This test is not implemented yet')

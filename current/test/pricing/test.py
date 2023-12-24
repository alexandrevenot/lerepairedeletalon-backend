import unittest
import os
import sys

from fastapi import FastAPI

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../bin/')))

import app.pricing.router as pricing_router
import app.pricing.utils as pricing_utils

config = pricing_utils.load_config()

server = FastAPI()

server.include_router(pricing_router.router)

client = TestClient(server)

class PricingTest(unittest.TestCase):
    def test(self):
        subtotal = 200
        fees_coeff = 0.5
        fees_offset = 13

        fees_ht = pricing_utils.calculate_fees_ht(subtotal, fees_coeff, fees_offset)
        self.assertEqual(fees_ht, 113)

        tva_coeff = 0.2
        price_with_fees = pricing_utils.calculate_checkout(subtotal, fees_ht,  tva_coeff)
        self.assertEqual(price_with_fees.total, 336)
        self.assertEqual(price_with_fees.subtotal, 200)
        self.assertEqual(price_with_fees.service_fees, 136)

        price_with_fees = pricing_utils.calculate_income(subtotal, fees_ht, tva_coeff)
        self.assertEqual(price_with_fees.total, 64)
        self.assertEqual(price_with_fees.subtotal, 200)
        self.assertEqual(price_with_fees.service_fees, 136)

        subtotal = 13
        fees_coeff = 0.06
        fees_offset = 13
        fees_ht = pricing_utils.calculate_fees_ht(subtotal, fees_coeff, fees_offset)
        price_with_fees = pricing_utils.calculate_checkout(subtotal, fees_ht, tva_coeff)
        self.assertEqual(price_with_fees.total, 30)
        self.assertEqual(price_with_fees.service_fees, 17)

        subtotal = 200
        advance_percentage = 50
        self.assertEqual(pricing_utils.calculate_advance(subtotal, advance_percentage, True), 100)
        self.assertEqual(pricing_utils.calculate_balance(subtotal, advance_percentage, True), 100)

        subtotal = 117
        advance_percentage = 53
        self.assertEqual(pricing_utils.calculate_advance(subtotal, advance_percentage, True) + pricing_utils.calculate_balance(subtotal, advance_percentage, True), subtotal)

        required_price = 117
        fees_coeff = 0.06
        fees_offset = 13
        corresponding_subtotal = pricing_utils.calculate_corresponding_subtotal(required_price, fees_coeff, fees_offset, 0.2)
        self.assertTrue(corresponding_subtotal <= 95)
        self.assertTrue(corresponding_subtotal >= 94)

        response = client.get('/pricing/checkout-simulation?subtotal=117')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 126)

if __name__ == '__main__':
    os.chdir('../bin')
    unittest.main()
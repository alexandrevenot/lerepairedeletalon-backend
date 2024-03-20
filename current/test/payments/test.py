import unittest
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.payments.router as payments_router
import app.payments.utils as payments_utils

config = payments_utils.load_config()

server = FastAPI()

server.include_router(payments_router.router)

client = TestClient(server)

class paymentsTest(unittest.TestCase):
    def test(self):
        subtotal_ht = 200
        fees_coeff = 0.5
        fees_offset = 13

        fees_ht = payments_utils.calculate_fees_ht(subtotal_ht, fees_coeff, fees_offset)
        self.assertEqual(fees_ht, 113)

        tva_coeff = 0.2
        tva_cover_coeff = 0.055
        price_with_fees = payments_utils.calculate_checkout(subtotal_ht, fees_ht,  tva_coeff, tva_cover_coeff)
        self.assertEqual(price_with_fees.total, 346.6)
        self.assertEqual(price_with_fees.subtotal, 211)
        self.assertEqual(price_with_fees.service_fees, 135.6)

        price_with_fees = payments_utils.calculate_income(subtotal_ht, tva_cover_coeff)
        self.assertEqual(price_with_fees, 211)

        subtotal_ht = 13
        fees_coeff = 0.06
        fees_offset = 13
        fees_ht = payments_utils.calculate_fees_ht(subtotal_ht, fees_coeff, fees_offset)
        price_with_fees = payments_utils.calculate_checkout(subtotal_ht, fees_ht, tva_coeff, tva_cover_coeff)
        self.assertEqual(price_with_fees.total, 30.25)
        self.assertEqual(price_with_fees.service_fees, 16.54)

        subtotal_ht = 200
        advance_percentage = 50
        self.assertEqual(payments_utils.calculate_advance(subtotal_ht, advance_percentage), 100)
        self.assertEqual(payments_utils.calculate_balance(subtotal_ht, advance_percentage), 100)

        subtotal_ht = 117
        advance_percentage = 53
        self.assertEqual(payments_utils.calculate_advance(subtotal_ht, advance_percentage) + payments_utils.calculate_balance(subtotal_ht, advance_percentage), subtotal_ht)

        required_price = 117
        fees_coeff = 0.06
        fees_offset = 13
        corresponding_subtotal = payments_utils.calculate_corresponding_subtotal(required_price, fees_coeff, fees_offset, 0.2, 0.055)
        self.assertTrue(corresponding_subtotal <= 90)
        self.assertTrue(corresponding_subtotal >= 89)

        response = client.get('/payments/checkout-simulation?subtotal=117')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 131.85)

if __name__ == '__main__':
    os.chdir('../bin')
    unittest.main()

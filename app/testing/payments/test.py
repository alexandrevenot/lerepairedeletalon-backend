import unittest
import os
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from testing.context import fake_db, get_db, SMTPDummySession, get_db_client
import routers.payments.router as payments_router
import routers.payments.utils as payments_utils
import routers.auth.router as auth_router
import routers.users.router as users_router

config = payments_utils.load_config()

server = FastAPI()

server.dependency_overrides[payments_router.get_db] = get_db
server.dependency_overrides[auth_router.get_db] = get_db
server.dependency_overrides[users_router.get_db] = get_db

server.dependency_overrides[auth_router.get_db_client] = get_db_client
server.dependency_overrides[users_router.get_db_client] = get_db_client
server.dependency_overrides[users_router.get_cover_in_db] = lambda: unittest.mock.Mock()

auth_router.mailing_utils.smtplib.SMTP = SMTPDummySession
auth_router.monitoring_tools.send_telegram_message = Mock()
payments_router.monitoring_tools.send_telegram_message = Mock()

server.include_router(payments_router.router)
server.include_router(auth_router.router)
server.include_router(users_router.router)

client = TestClient(server)

class PaymentsTest(unittest.TestCase):
    def test(self):
        subtotal = 200
        fees_coeff = 0.5
        price_with_fees = payments_utils.calculate_checkout(subtotal, fees_coeff)
        self.assertEqual(price_with_fees.total, 300)
        self.assertEqual(price_with_fees.subtotal, 200)
        self.assertEqual(price_with_fees.fees, 100)

        advance_percentage = 50
        self.assertEqual(payments_utils.calculate_advance(subtotal, advance_percentage), 100)
        self.assertEqual(payments_utils.calculate_balance(subtotal, advance_percentage), 100)

        subtotal = 117
        advance_percentage = 53
        self.assertEqual(payments_utils.calculate_advance(subtotal, advance_percentage) + payments_utils.calculate_balance(subtotal, advance_percentage), subtotal)

        required_price = 117
        fees_coeff = 0.06
        corresponding_subtotal = payments_utils.calculate_corresponding_subtotal(required_price, fees_coeff)
        self.assertTrue(corresponding_subtotal <= 111)
        self.assertTrue(corresponding_subtotal >= 110)

        response = client.get('/payments/checkout-simulation?subtotal=117')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 126.36)

        # test stripe functions
        response = client.post('/auth/register', json={
            "firstname": "Michel",
            "lastname": "Dupont",
            "email": "lrdeservice@gmail.com",
            "phone_number": "0665824651",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)

        response = client.post('/auth/login', json={
            "email": "lrdeservice@gmail.com",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue("accessToken" in response.json())
        self.assertTrue("refreshToken" in response.json())
        access_token = response.json()["accessToken"]
        headers = {"Authorization": f"Bearer {access_token}"}

        with patch('routers.payments.router.stripe', new_callable=Mock), \
        patch('routers.payments.router.stripe.Account.create', new_callable=Mock) as mock1, \
        patch('routers.payments.router.stripe.Account.create_person', new_callable=Mock) as mock2, \
        patch('routers.payments.router.stripe.Account.create_external_account', new_callable=Mock) as mock3, \
        patch('routers.payments.router.stripe.Webhook.construct_event', new_callable=Mock) as mock4:
            mock1.return_value={"id": "acct"}
            mock2.return_value={"id": "pers"}
            mock3.return_value={"last4": "2606"}

            # when account does not exist yet
            response = client.get('/payments/stripe-account', headers=headers)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["detail"], "no stripe account found")

            # unavailable business type
            body = {
                "business_type": "wtf",
                "account_token": "token",
                "bank_account_token": "token2",
                "additional_account_token": "token3"
            }
            response = client.post('/payments/stripe-account', json=body, headers=headers)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["detail"], 'business_type has to be "company" or "individual"')

            # working json but legal identity is too low
            body = {
                "business_type": "individual",
                "account_token": "token",
                "bank_account_token": "token2",
                "additional_account_token": "token3"
            }
            response = client.post('/payments/stripe-account', json=body, headers=headers)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"], "legal identity level has to be 2")

            # put legal identity with working body
            working_json = {
                "business_type": "individual",
                "gender": "Monsieur",
                "address_postal_code": "Whatever",
                "address_line1": "Whatever",
                "address_city": "Whatever",
                "birthdate": "12/12/1998",
                "birthplace": "Là",
                "citizenship": "Fr eheh"
            }
            response = client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"}, json=working_json)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["new_level"], 2)

            # working json
            body = {
                "business_type": "individual",
                "account_token": "token",
                "bank_account_token": "token2"
            }
            response = client.post('/payments/stripe-account', json=body, headers=headers)
            self.assertEqual(response.status_code, 200)

            response = client.get('/users/account-information', headers=headers)
            self.assertEqual(response.status_code, 200)
            response_content = response.json()
            self.assertEqual(response_content["legal_identity"]["level"], 3)
            self.assertEqual(response_content["legal_identity"]["business_type"], "individual")
            self.assertEqual(response_content["legal_identity"]["iban_last4"], "2606")

            user_in_db = fake_db.users.find_one({})
            self.assertEqual(user_in_db["stripe_account"]["account"]["id"], "acct")
            self.assertEqual(user_in_db["stripe_account"]["account"]["individual"]["verification"]["status"], "pending")
            self.assertEqual(user_in_db["stripe_account"]["account"]["individual"]["verification"]["document"]["details_code"], None)
            self.assertEqual(user_in_db["stripe_account"]["account"]["individual"]["verification"]["additional_document"]["details_code"], None)
            self.assertEqual(user_in_db["stripe_account"]["account"]["requirements"]["currently_due"], [])

            response = client.get('/payments/stripe-account', headers=headers)
            self.assertEqual(response.status_code, 200)
            response_content = response.json()
            self.assertEqual(response_content["currently_due_is_empty"], True)
            self.assertEqual(response_content["identity_document_status"], "pending")
            self.assertEqual(response_content["proof_of_residence_status"], "pending")
            self.assertEqual(response_content["proof_of_company_status"], None)

            # working json but stripe account already exists
            body = {
                "business_type": "individual",
                "account_token": "token",
                "bank_account_token": "token2",
                "additional_account_token": "token3"
            }
            response = client.post('/payments/stripe-account', json=body, headers=headers)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"], "legal identity level has to be 2")

            # webhooks
            mock4.return_value = {
                "type": "account.updated",
                "data": {
                    "object": {
                        "id": "acct",
                        "business_type": "individual",
                        "individual": {
                            "verification": {
                                "additional_document": {
                                    "details_code": "err_ugly_document"
                                },
                                "document": {
                                    "details_code": None
                                },
                                "status": "unverified"
                            }
                        },
                        "requirements": {
                            "currently_due": [
                                "individual.verification.additional_document.front"
                            ]
                        }
                    }
                }
            }

            response = client.post('/payments/stripe-accounts-webhook', json={"this json": "is mocked anyways"}, headers={"stripe-signature": "osef"})
            self.assertEqual(response.status_code, 200)

            user_in_db = fake_db.users.find_one({})
            self.assertEqual(user_in_db["stripe_account"]["account"]["id"], "acct")
            self.assertEqual(user_in_db["stripe_account"]["account"]["individual"]["verification"]["status"], "unverified")
            self.assertEqual(user_in_db["stripe_account"]["account"]["individual"]["verification"]["document"]["details_code"], None)
            self.assertEqual(user_in_db["stripe_account"]["account"]["individual"]["verification"]["additional_document"]["details_code"], "err_ugly_document")
            self.assertEqual(user_in_db["stripe_account"]["account"]["requirements"]["currently_due"], ["individual.verification.additional_document.front"])

if __name__ == '__main__':
    unittest.main()

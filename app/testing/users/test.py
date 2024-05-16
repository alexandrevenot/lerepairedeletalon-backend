import unittest
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from testing.context import fake_db, get_db, get_db_client, SMTPDummySession
import routers.auth.router as auth_router
import routers.users.router as users_router

server = FastAPI()

server.dependency_overrides[auth_router.get_db] = get_db
server.dependency_overrides[users_router.get_db] = get_db

server.dependency_overrides[auth_router.get_db_client] = get_db_client
server.dependency_overrides[users_router.get_db_client] = get_db_client
auth_router.mailing_utils.smtplib.SMTP = SMTPDummySession
server.dependency_overrides[users_router.get_admin_files_bucket] = lambda: unittest.mock.Mock()

server.include_router(auth_router.router)
server.include_router(users_router.router)

client = TestClient(server)

class UsersTest(unittest.TestCase):
    def test(self):
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

        # get firstname and lastname
        response = client.get("/users/user-name", headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firstname"], "Michel")
        self.assertEqual(response.json()["lastname"], "Dupont")

        # get firstname and lastname without token
        response = client.get("/users/user-name", headers={"Authorization": "ounga bounga"})
        self.assertEqual(response.status_code, 401)

        # look for account information when legal identity when it has not been created yet
        response = client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)
        returned_json = response.json()
        self.assertEqual(returned_json["firstname"], "Michel")
        self.assertEqual(returned_json["lastname"], "Dupont")
        self.assertEqual(returned_json["email"], "lrdeservice@gmail.com")
        self.assertEqual(returned_json["phone_number"], "0665824651")
        self.assertEqual(returned_json["legal_identity"], None)

        # try to put legal identity but bad date format
        response = client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"},
                              json={
                                  "business_type": "individual",
                                  "gender": "Monsieur",
                                  "address_postal_code": "Whatever",
                                  "address_line1": "Whatever",
                                  "address_city": "Whatever",
                                  "birthdate": "12/24",
                                  "birthplace": "Là",
                                  "citizenship": "Fr eheh"
                              })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], 'incorrect birthdate date format')

        # try to get legal identity when it does not exist because precedent tries failed
        response = client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)
        returned_json = response.json()
        self.assertEqual(returned_json["firstname"], "Michel")
        self.assertEqual(returned_json["lastname"], "Dupont")
        self.assertEqual(returned_json["email"], "lrdeservice@gmail.com")
        self.assertEqual(returned_json["phone_number"], "0665824651")
        self.assertEqual(returned_json["legal_identity"], None)

        # put legal identity with incomplete body (should still return 200)
        working_json = {
            "business_type": "individual",
            "address_postal_code": "Whatever",
            "address_line1": "Whatever",
            "address_city": "Whatever",
            "birthdate": "12/12/1998",
            "birthplace": "Là",
            "citizenship": "Fr eheh"
        }
        response = client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"}, json=working_json)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["new_level"], 0)

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

        # check that it can be obtained with the GET route
        response = client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)

        response_json = response.json()
        for key, value in working_json.items():
            self.assertEqual(value, response_json["legal_identity"][key])
        self.assertEqual(response_json["legal_identity"]["level"], 2)

        # update legal identity with incomplete company info
        response = client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"},
                              json={
                                  "business_type": "company",
                                  "gender": "Monsieur",
                                  "company_name": "LRDE",
                                  "postal_address": "Whatever"
                              })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["new_level"], 0)

        # update legal identity with complete company info
        working_json = {
            "business_type": "company",
            "gender": "Monsieur",
            "company_name": "LRDE",
            "company_structure": "SAS",
            "capital": "1500",
            "siren": "123456789",
            "head_office_address_line1": "Whatever",
            "head_office_address_postal_code": "Whatever",
            "head_office_address_city": "Whatever",
            "role_in_company": "President"
        }
        response = client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"}, json=working_json)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["new_level"], 2)

        # check that it appears in db
        response = client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)

        response_json = response.json()
        for key, value in working_json.items():
            self.assertEqual(value, response_json["legal_identity"][key])
        self.assertEqual(response_json["legal_identity"]["level"], 2)

        # adding fake stripe account to test lvl 3
        fake_db.users.update_one(
            {"email": "lrdeservice@gmail.com"},
            {
                "$set": {
                    "stripe_account": {},
                    "legal_identity.level": 3
                }
            }
        )

        response = client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"}, json={"business_type": "company"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["new_level"], 3)

        # try to put legal identity with working body for individual: should 409
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
        self.assertEqual(response.status_code, 403)

if __name__ == '__main__':
    unittest.main()

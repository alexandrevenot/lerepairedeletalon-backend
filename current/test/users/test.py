import unittest
import os
import sys

from fastapi import FastAPI

import mongomock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../bin/')))

import app.auth.router as auth_router
import app.users.router as users_router

fake_client = mongomock.MongoClient()
fake_db = fake_client.main

server = FastAPI()

server.dependency_overrides[auth_router.get_db] = lambda: fake_db
server.dependency_overrides[users_router.get_db] = lambda: fake_db

server.include_router(auth_router.router)
server.include_router(users_router.router)

client = TestClient(server)

class UsersTest(unittest.TestCase):
    def test(self):
        response = client.post('/auth/register', json={
            "firstname": "Michel",
            "lastname": "Dupont",
            "email": "lrdeservice@gmail.com",
            "phone_number": "+33665824651",
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
        refresh_token = response.json()["refreshToken"]
        access_token = response.json()["accessToken"]

        # get firstname and lastname
        response = client.get("/users/user-name", headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firstname"], "Michel")
        self.assertEqual(response.json()["lastname"], "Dupont")

        # get firstname and lastname without token
        response = client.get("/users/user-name", headers={"Authorization": "ounga bounga"})
        self.assertEqual(response.status_code, 401)

        # look for account information when contractual identity when it has not been created yet
        response = client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)
        returned_json = response.json()
        self.assertEqual(returned_json["firstname"], "Michel")
        self.assertEqual(returned_json["lastname"], "Dupont")
        self.assertEqual(returned_json["email"], "lrdeservice@gmail.com")
        self.assertEqual(returned_json["phone_number"], "+33665824651")
        self.assertEqual(returned_json["contractual_identity"], None)

        # try to put contracts identity but bad date format
        response = client.put('/users/contractual-identity', headers={"Authorization": f"Bearer {access_token}"},
                              json={
                                  "type": "individual",
                                  "gender": "Monsieur",
                                  "postal_address": "Whatever",
                                  "birthdate": "12/24",
                                  "birthplace": "Là",
                                  "citizenship": "Fr eheh"
                              })
        self.assertEqual(response.status_code, 422)

        # try to put contracts identity but incomplete body
        response = client.put('/users/contractual-identity', headers={"Authorization": f"Bearer {access_token}"},
                              json={
                                  "type": "individual",
                                  "gender": "Monsieur",
                                  "postal_address": "Whatever",
                                  "birthdate": "28/10/1998",
                                  "birthplace": "Là",
                              })
        self.assertEqual(response.status_code, 422)

        # try to get contracts identity when it does not exist because precedent tries failed
        response = client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)
        returned_json = response.json()
        self.assertEqual(returned_json["firstname"], "Michel")
        self.assertEqual(returned_json["lastname"], "Dupont")
        self.assertEqual(returned_json["email"], "lrdeservice@gmail.com")
        self.assertEqual(returned_json["phone_number"], "+33665824651")
        self.assertEqual(returned_json["contractual_identity"], None)

        # put contracts identity when the body is right
        working_json = {
            "type": "individual",
            "gender": "Monsieur",
            "postal_address": "Whatever",
            "birthdate": "28/10/1998",
            "birthplace": "Là",
            "citizenship": "Fr eheh"
        }
        response = client.put('/users/contractual-identity', headers={"Authorization": f"Bearer {access_token}"}, json=working_json)
        self.assertEqual(response.status_code, 200)

        # check that it is in db
        user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(user_in_db is not None)
        for field in ["company_name", "company_status", "capital", "head_office_address", "siret"]:
            self.assertTrue(field not in user_in_db["contractual_identity"])

        # check that it can be obtained with the GET route aswell
        response = client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)

        for key, value in working_json.items():
            self.assertEqual(value, response.json()["contractual_identity"][key])

        # update contracts identity with incomplete company info
        response = client.put('/users/contractual-identity', headers={"Authorization": f"Bearer {access_token}"},
                              json={
                                  "type": "company",
                                  "gender": "Monsieur",
                                  "postal_address": "Whatever",
                                  "birthdate": "28/10/1998",
                                  "birthplace": "Là",
                                  "citizenship": "Fr eheh"
                              })
        self.assertEqual(response.status_code, 422)

        # update contracts identity with less but still incomplete company info
        response = client.put('/users/contractual-identity', headers={"Authorization": f"Bearer {access_token}"},
                              json={
                                  "type": "company",
                                  "gender": "Monsieur",
                                  "postal_address": "Whatever 2",
                                  "birthdate": "28/10/1998",
                                  "birthplace": "Là",
                                  "citizenship": "Fr eheh",
                                  "company_name": "la boite",
                                  "company_status": "a status",
                                  "capital": 18.75,
                                  "head_office_address": "par là",
                              })
        self.assertEqual(response.status_code, 422)

        # update contracts identity with complete company info
        working_json = {
            "type": "company",
            "gender": "Monsieur",
            "postal_address": "Whatever 2",
            "birthdate": "28/10/1998",
            "birthplace": "Là",
            "citizenship": "Fr eheh",
            "company_name": "la boite",
            "company_status": "a status",
            "capital": 18.75,
            "head_office_address": "par là",
            "siret": "AYIHBYIUN"
        }
        response = client.put('/users/contractual-identity', headers={"Authorization": f"Bearer {access_token}"}, json=working_json)
        self.assertEqual(response.status_code, 200)

        # check that it appears in db
        response = client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)

        for key, value in working_json.items():
            self.assertEqual(value, response.json()["contractual_identity"][key])

        self.assertEqual(response.json()["contractual_identity"]["postal_address"], "Whatever 2")
        self.assertEqual(response.json()["contractual_identity"]["siret"], "AYIHBYIUN")

        # put back individual contracts identity
        working_json = {
            "type": "individual",
            "gender": "Madame",
            "postal_address": "Whatever 3",
            "birthdate": "29/10/1998",
            "birthplace": "Ici",
            "citizenship": "Pas fr meh"
        }
        response = client.put('/users/contractual-identity', headers={"Authorization": f"Bearer {access_token}"}, json=working_json)
        self.assertEqual(response.status_code, 200)

        # check that it is in db and that no more company info is left
        user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(user_in_db is not None)
        for field in ["company_name", "company_status", "capital", "head_office_address", "siret"]:
            self.assertTrue(field not in user_in_db["contractual_identity"])

        for key, value in working_json.items():
            self.assertEqual(value, user_in_db["contractual_identity"][key])

if __name__ == '__main__':
    os.chdir('../bin')
    unittest.main()

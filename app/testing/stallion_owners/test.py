import unittest
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from testing.context import fake_db, get_db, get_db_client, SMTPDummySession
import routers.auth.router as auth_router
import routers.stallion_owners.router as stallion_owners_router

server = FastAPI()

server.dependency_overrides[auth_router.get_db] = get_db
server.dependency_overrides[stallion_owners_router.get_db] = get_db

server.dependency_overrides[auth_router.get_db_client] = get_db_client
auth_router.mailing_utils.smtplib.SMTP = SMTPDummySession

server.include_router(auth_router.router)
server.include_router(stallion_owners_router.router)

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
        headers = {"Authorization": f"Bearer {access_token}"}

        # wrong business type
        query = {
            "business_type": "wtf",
            "firstname": "Georgelin",
            "lastname": "Marcellin",
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
        response = client.post('/stallion-owners/stallion-owner', json=query, headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], 'business_type has to be either "individual" or "company"')

        # wrong gender
        query = {
            "business_type": "company",
            "firstname": "Georgelin",
            "lastname": "Marcellin",
            "gender": "wtf",
            "company_name": "LRDE",
            "company_structure": "SAS",
            "capital": "1500",
            "siren": "123456789",
            "head_office_address_line1": "Whatever",
            "head_office_address_postal_code": "Whatever",
            "head_office_address_city": "Whatever",
            "role_in_company": "President"
        }
        response = client.post('/stallion-owners/stallion-owner', json=query, headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], 'gender has to be either "Monsieur" or "Madame"')

        # wrong birthdate
        query = {
            "business_type": "company",
            "firstname": "Georgelin",
            "lastname": "Marcellin",
            "gender": "Monsieur",
            "company_name": "LRDE",
            "company_structure": "SAS",
            "capital": "1500",
            "siren": "123456789",
            "head_office_address_line1": "Whatever",
            "head_office_address_postal_code": "Whatever",
            "head_office_address_city": "Whatever",
            "role_in_company": "President",
            "birthdate": "wtf"
        }
        response = client.post('/stallion-owners/stallion-owner', json=query, headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "incorrect birthdate date format")

        # working query
        query = {
            "business_type": "company",
            "firstname": "Georgelin",
            "lastname": "Marcellin",
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
        response = client.post('/stallion-owners/stallion-owner', json=query, headers=headers)
        self.assertEqual(response.status_code, 200)
        stallion_owner_id_1 = response.json()["id"]

        response = client.get('/stallion-owners/stallion-owner-names', headers=headers)
        self.assertEqual(response.status_code, 200)
        stallion_owners = response.json()["stallion_owners"]
        self.assertEqual(len(stallion_owners), 1)
        stallion_owner = stallion_owners[0]
        self.assertEqual(stallion_owner["id"], stallion_owner_id_1)
        for key, value in query.items():
            self.assertEqual(stallion_owner[key], value)

        query = {
            "business_type": "individual",
            "firstname": "Georgelin",
            "lastname": "Marcellin",
            "gender": "Monsieur",
            "address_line1": "Whatever",
            "address_postal_code": "Whatever",
            "address_city": "Whatever",
            "birthplace": "Toulouse",
            "birthdate": "01/01/2000"
        }
        response = client.put(f'/stallion-owners/stallion-owner/{stallion_owner_id_1}', json=query, headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.delete(f'/stallion-owners/stallion-owner/{stallion_owner_id_1}?stallion_id=', headers=headers)
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()

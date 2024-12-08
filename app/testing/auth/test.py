import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from testing.context import fake_db, get_db, get_db_client, SMTPDummySession
import routers.auth.router as auth_router

server = FastAPI()

server.dependency_overrides[auth_router.get_db] = get_db
server.dependency_overrides[auth_router.get_db_client] = get_db_client
auth_router.mailing_utils.smtplib.SMTP = SMTPDummySession
auth_router.monitoring_tools.send_telegram_message = Mock()

server.include_router(auth_router.router)

client = TestClient(server)

class AuthTest(unittest.TestCase):
    def test(self):
        # wrong json
        response = client.post('/auth/register', json={"ounga": "bounga"})
        self.assertEqual(response.status_code, 422)

        # bad email format
        response = client.post('/auth/register', json={
            "firstname": "Michel",
            "lastname": "Dupont",
            "email": "oungabounga",
            "phone_number": "0654321457",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 422)

        # wrong phone number format
        response = client.post('/auth/register', json={
            "firstname": "Michel",
            "lastname": "Dupont",
            "email": "lrdeservice@gmail.com",
            "phone_number": "86543214579",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 422)

        # working json
        response = client.post('/auth/register', json={
            "firstname": "Michel",
            "lastname": "Dupont",
            "email": "lrdeservice@gmail.com",
            "phone_number": "0665824651",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)

        user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(user_in_db is not None)

        email_verification_code_in_db = fake_db.email_verification_codes.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(email_verification_code_in_db is not None)

        # when the account already exists
        response = client.post('/auth/register', json={
            "firstname": "Michel",
            "lastname": "Dupont",
            "email": "lrdeservice@gmail.com",
            "phone_number": "0665824651",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 400)

        # when the password is wrong
        response = client.post('/auth/login', json={
            "email": "lrdeservice@gmail.com",
            "password": "acjiodfehyx"
        })
        self.assertEqual(response.status_code, 401)

        # when the password is right
        response = client.post('/auth/login', json={
            "email": "lrdeservice@gmail.com",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue("accessToken" in response.json())
        self.assertTrue("refreshToken" in response.json())
        refresh_token = response.json()["refreshToken"]

        # asking to refresh token without refresh token
        response = client.post('/auth/refresh-token', json={
            "token": "ounga bounga"
        })

        self.assertEqual(response.status_code, 401)

        # asking to refresh token with the right refresh token
        response = client.post('/auth/refresh-token', json={
            "token": f"Bearer {refresh_token}"
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue("accessToken" in response.json())
        self.assertTrue("refreshToken" in response.json())

if __name__ == '__main__':
    unittest.main()

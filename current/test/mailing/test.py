import unittest
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from context import fake_db, get_db, get_db_client, SMTPDummySession
import app.auth.router as auth_router
import app.mailing.router as mailing_router
from app.auth.utils import verify_password

server = FastAPI()

server.dependency_overrides[auth_router.get_db] = get_db
server.dependency_overrides[mailing_router.get_db] = get_db

server.dependency_overrides[auth_router.get_db_client] = get_db_client
server.dependency_overrides[mailing_router.get_db_client] = get_db_client
mailing_router.utils.smtplib.SMTP = SMTPDummySession

server.include_router(auth_router.router)
server.include_router(mailing_router.router)

client = TestClient(server)

class MailingTest(unittest.TestCase):
    def test(self):
        # register a new user
        response = client.post('/auth/register', json={
            "firstname": "Michel",
            "lastname": "Dupont",
            "email": "lrdeservice@gmail.com",
            "phone_number": "0665824651",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)

        # login to get access token
        response = client.post('/auth/login', json={
            "email": "lrdeservice@gmail.com",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue("accessToken" in response.json())
        access_token = response.json()["accessToken"]

        # check that an email verification code has been generated and that email_is_verified is False
        email_verification_code_in_db = fake_db.email_verification_codes.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(email_verification_code_in_db is not None)

        user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(user_in_db is not None)
        self.assertFalse(user_in_db["email_is_verified"])

        # verify the email address manually
        response = client.put('/mailing/verify-email-address', json = {"code": email_verification_code_in_db["code"]})
        self.assertEqual(response.status_code, 200)

        # assert that the code no longer exists
        document = fake_db.email_verification_codes.find_one({'code': email_verification_code_in_db["code"]})
        self.assertTrue(document is None)

        # assert that email_is_verified is now at True for the user
        user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(user_in_db is not None)
        self.assertTrue(user_in_db["email_is_verified"])

        # ask to send email verification email again
        response = client.post("/mailing/send-email-verification-email", headers={"Authorization": f"Bearer {access_token}"})

        # assert that when the email is already verified, HTTP 400 is returned
        self.assertEqual(response.status_code, 400)

        # registering a new user and instantly resending verification email
        fake_db.users.delete_one({"email": "lrdeservice@gmail.com"})
        response = client.post('/auth/register', json={
            "firstname": "Michel",
            "lastname": "Dupont",
            "email": "lrdeservice@gmail.com",
            "phone_number": "0665824651",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)

        first_code = fake_db.email_verification_codes.find_one({"email": "lrdeservice@gmail.com"})["code"]

        # getting accessToken to be able to send email verification email again
        response = client.post('/auth/login', json={
            "email": "lrdeservice@gmail.com",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue("accessToken" in response.json())
        self.assertTrue("refreshToken" in response.json())
        access_token = response.json()["accessToken"]

        # ask to send email verification email again and check that the code has changed
        response = client.post("/mailing/send-email-verification-email", headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 200)
        second_code = fake_db.email_verification_codes.find_one({"email": "lrdeservice@gmail.com"})["code"]
        self.assertFalse(second_code == first_code)

        # verify the email address manually
        response = client.put('/mailing/verify-email-address', json = {"code": second_code})
        self.assertEqual(response.status_code, 200)

        # assert that the code no longer exists
        document = fake_db.email_verification_codes.find_one({'code': second_code})
        self.assertTrue(document is None)

        # assert that email_is_verified is now at True for the user
        user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(user_in_db is not None)
        self.assertTrue(user_in_db["email_is_verified"])

        # send password update email when the email is not in the db
        response = client.post("/mailing/send-password-update-email", json={"email": "ounga bounga"})
        self.assertEqual(response.status_code, 404)

        response = client.post("/mailing/send-password-update-email", json={"email": "lrdeservice@gmail.com"})
        self.assertEqual(response.status_code, 200)

        code_in_db = fake_db.password_update_codes.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(code_in_db is not None)

        # updating the password

        # assert that when the code is wrong, 403 is returned, the code document is still here and the password remains the same
        response = client.put("/mailing/update-password", json={
            "new_password": "eheh",
            "code": "not the right code"
        })
        self.assertEqual(response.status_code, 403)

        user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
        self.assertFalse(verify_password('eheh', user_in_db["hashedpassword"]))

        code_in_db = fake_db.password_update_codes.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(code_in_db is not None)

        # assert that when the code is the right one, the password has actually changed and the code document is gone
        response = client.put("/mailing/update-password", json={
            "new_password": "eheh",
            "code": code_in_db["code"]
        })

        self.assertEqual(response.status_code, 200)

        user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(verify_password('eheh', user_in_db["hashedpassword"]))

        code_in_db = fake_db.password_update_codes.find_one({"email": "lrdeservice@gmail.com"})
        self.assertTrue(code_in_db is None)

if __name__ == '__main__':
    os.chdir('../bin')
    unittest.main()

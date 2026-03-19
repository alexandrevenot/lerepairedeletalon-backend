from app.routers.auth.utils import verify_password


def test(auth_client, mailing_client, fake_db):
    # register a new user
    response = auth_client.post('/auth/register', json={
        "firstname": "Michel",
        "lastname": "Dupont",
        "email": "lrdeservice@gmail.com",
        "phone_number": "0665824651",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200

    # login to get access token
    response = auth_client.post('/auth/login', json={
        "email": "lrdeservice@gmail.com",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200
    assert "accessToken" in response.json()
    access_token = response.json()["accessToken"]

    # check that an email verification code has been generated and that email_is_verified is False
    email_verification_code_in_db = fake_db.email_verification_codes.find_one({"email": "lrdeservice@gmail.com"})
    assert email_verification_code_in_db is not None

    user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
    assert user_in_db is not None
    assert not user_in_db["email_is_verified"]

    # verify the email address manually
    response = mailing_client.put('/mailing/verify-email-address', json = {"code": email_verification_code_in_db["code"]})
    assert response.status_code == 200

    # assert that the code no longer exists
    document = fake_db.email_verification_codes.find_one({'code': email_verification_code_in_db["code"]})
    assert document is None

    # assert that email_is_verified is now at True for the user
    user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
    assert user_in_db is not None
    assert user_in_db["email_is_verified"]

    # ask to send email verification email again
    response = mailing_client.post("/mailing/send-email-verification-email", headers={"Authorization": f"Bearer {access_token}"})

    # assert that when the email is already verified, HTTP 400 is returned
    assert response.status_code == 400

    # registering a new user and instantly resending verification email
    fake_db.users.delete_one({"email": "lrdeservice@gmail.com"})
    response = auth_client.post('/auth/register', json={
        "firstname": "Michel",
        "lastname": "Dupont",
        "email": "lrdeservice@gmail.com",
        "phone_number": "0665824651",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200

    first_code = fake_db.email_verification_codes.find_one({"email": "lrdeservice@gmail.com"})["code"]

    # getting accessToken to be able to send email verification email again
    response = auth_client.post('/auth/login', json={
        "email": "lrdeservice@gmail.com",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200
    assert "accessToken" in response.json()
    assert "refreshToken" in response.json()
    access_token = response.json()["accessToken"]

    # ask to send email verification email again and check that the code has changed
    response = mailing_client.post("/mailing/send-email-verification-email", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    second_code = fake_db.email_verification_codes.find_one({"email": "lrdeservice@gmail.com"})["code"]
    assert not second_code == first_code

    # verify the email address manually
    response = mailing_client.put('/mailing/verify-email-address', json = {"code": second_code})
    assert response.status_code == 200

    # assert that the code no longer exists
    document = fake_db.email_verification_codes.find_one({'code': second_code})
    assert document is None

    # assert that email_is_verified is now at True for the user
    user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
    assert user_in_db is not None
    assert user_in_db["email_is_verified"]

    # send password update email when the email is not in the db
    response = mailing_client.post("/mailing/send-password-update-email", json={"email": "ounga bounga"})
    assert response.status_code == 404

    response = mailing_client.post("/mailing/send-password-update-email", json={"email": "lrdeservice@gmail.com"})
    assert response.status_code == 200

    code_in_db = fake_db.password_update_codes.find_one({"email": "lrdeservice@gmail.com"})
    assert code_in_db is not None

    # updating the password

    # assert that when the code is wrong, 403 is returned, the code document is still here and the password remains the same
    response = mailing_client.put("/mailing/update-password", json={
        "new_password": "eheh",
        "code": "not the right code"
    })
    assert response.status_code == 403

    user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
    assert not verify_password('eheh', user_in_db["hashedpassword"])

    code_in_db = fake_db.password_update_codes.find_one({"email": "lrdeservice@gmail.com"})
    assert code_in_db is not None

    # assert that when the code is the right one, the password has actually changed and the code document is gone
    response = mailing_client.put("/mailing/update-password", json={
        "new_password": "eheh",
        "code": code_in_db["code"]
    })

    assert response.status_code == 200

    user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
    assert verify_password('eheh', user_in_db["hashedpassword"])

    code_in_db = fake_db.password_update_codes.find_one({"email": "lrdeservice@gmail.com"})
    assert code_in_db is None
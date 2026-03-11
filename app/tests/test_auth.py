def test(auth_client, fake_db):
    # wrong json
    response = auth_client.post('/auth/register', json={"ounga": "bounga"})
    assert response.status_code == 422

    # bad email format
    response = auth_client.post('/auth/register', json={
        "firstname": "Michel",
        "lastname": "Dupont",
        "email": "oungabounga",
        "phone_number": "0654321457",
        "password": "acjiodfehy"
    })
    assert response.status_code == 422

    # wrong phone number format
    response = auth_client.post('/auth/register', json={
        "firstname": "Michel",
        "lastname": "Dupont",
        "email": "lrdeservice@gmail.com",
        "phone_number": "86543214579",
        "password": "acjiodfehy"
    })
    assert response.status_code == 422

    # working json
    response = auth_client.post('/auth/register', json={
        "firstname": "Michel",
        "lastname": "Dupont",
        "email": "lrdeservice@gmail.com",
        "phone_number": "0665824651",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200

    user_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
    assert user_in_db is not None

    email_verification_code_in_db = fake_db.email_verification_codes.find_one({"email": "lrdeservice@gmail.com"})
    assert email_verification_code_in_db is not None

    # when the account already exists
    response = auth_client.post('/auth/register', json={
        "firstname": "Michel",
        "lastname": "Dupont",
        "email": "lrdeservice@gmail.com",
        "phone_number": "0665824651",
        "password": "acjiodfehy"
    })
    assert response.status_code == 400

    # when the password is wrong
    response = auth_client.post('/auth/login', json={
        "email": "lrdeservice@gmail.com",
        "password": "acjiodfehyx"
    })
    assert response.status_code == 401

    # when the password is right
    response = auth_client.post('/auth/login', json={
        "email": "lrdeservice@gmail.com",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200
    assert "accessToken" in response.json()
    assert "refreshToken" in response.json()
    refresh_token = response.json()["refreshToken"]

    # asking to refresh token without refresh token
    response = auth_client.post('/auth/refresh-token', json={
        "token": "ounga bounga"
    })
    assert response.status_code == 401

    # asking to refresh token with the right refresh token
    response = auth_client.post('/auth/refresh-token', json={
        "token": f"Bearer {refresh_token}"
    })
    assert response.status_code == 200
    assert "accessToken" in response.json()
    assert "refreshToken" in response.json()
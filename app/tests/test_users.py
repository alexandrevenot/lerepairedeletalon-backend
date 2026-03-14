def test(auth_client, users_client, fake_db):
    response = auth_client.post('/auth/register', json={
        "firstname": "Michel",
        "lastname": "Dupont",
        "email": "lrdeservice@gmail.com",
        "phone_number": "0665824651",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200

    response = auth_client.post('/auth/login', json={
        "email": "lrdeservice@gmail.com",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200
    assert "accessToken" in response.json()
    assert "refreshToken" in response.json()
    access_token = response.json()["accessToken"]

    # get firstname and lastname
    response = users_client.get("/users/user-name", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["firstname"] == "Michel"
    assert response.json()["lastname"] == "Dupont"

    # get firstname and lastname without token
    response = users_client.get("/users/user-name", headers={"Authorization": "ounga bounga"})
    assert response.status_code == 401

    # look for account information when legal identity when it has not been created yet
    response = users_client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    returned_json = response.json()
    assert returned_json["firstname"] == "Michel"
    assert returned_json["lastname"] == "Dupont"
    assert returned_json["email"] == "lrdeservice@gmail.com"
    assert returned_json["phone_number"] == "0665824651"
    assert returned_json["legal_identity"] == None

    # try to put legal identity but bad date format
    response = users_client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"},
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
    assert response.status_code == 422
    assert response.json()["detail"] == 'incorrect birthdate date format'

    # try to get legal identity when it does not exist because precedent tries failed
    response = users_client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    returned_json = response.json()
    assert returned_json["firstname"] == "Michel"
    assert returned_json["lastname"] == "Dupont"
    assert returned_json["email"] == "lrdeservice@gmail.com"
    assert returned_json["phone_number"] == "0665824651"
    assert returned_json["legal_identity"] == None

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
    response = users_client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"}, json=working_json)
    assert response.status_code == 200
    assert response.json()["new_level"] == 0

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
    response = users_client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"}, json=working_json)
    assert response.status_code == 200
    assert response.json()["new_level"] == 2

    # check that it can be obtained with the GET route
    response = users_client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200

    response_json = response.json()
    for key, value in working_json.items():
        assert value == response_json["legal_identity"][key]
    assert response_json["legal_identity"]["level"] == 2

    # update legal identity with incomplete company info
    response = users_client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"},
                            json={
                                "business_type": "company",
                                "gender": "Monsieur",
                                "company_name": "LRDE",
                                "postal_address": "Whatever"
                            })
    assert response.status_code == 200
    assert response.json()["new_level"] == 0

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
    response = users_client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"}, json=working_json)
    assert response.status_code == 200
    assert response.json()["new_level"] == 2

    # check that it appears in db
    response = users_client.get('/users/account-information', headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200

    response_json = response.json()
    for key, value in working_json.items():
        assert value == response_json["legal_identity"][key]
    assert response_json["legal_identity"]["level"] == 2

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

    response = users_client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"}, json={"business_type": "company"})
    assert response.status_code == 200
    assert response.json()["new_level"] == 3

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
    response = users_client.put('/users/legal-identity', headers={"Authorization": f"Bearer {access_token}"}, json=working_json)
    assert response.status_code == 403
from unittest.mock import Mock, patch
from app.routers.payments.utils import calculate_checkout, calculate_balance, calculate_advance, calculate_corresponding_subtotal

def test(auth_client, users_client, payments_client, fake_db):
    subtotal = 200
    fees_coeff = 0.5
    price_with_fees = calculate_checkout(subtotal, fees_coeff)
    assert price_with_fees.total == 300
    assert price_with_fees.subtotal == 200
    assert price_with_fees.fees == 100

    advance_percentage = 50
    assert calculate_advance(subtotal, advance_percentage) == 100
    assert calculate_balance(subtotal, advance_percentage) == 100

    subtotal = 117
    advance_percentage = 53
    assert calculate_advance(subtotal, advance_percentage) + calculate_balance(subtotal, advance_percentage) == subtotal

    required_price = 117
    fees_coeff = 0.06
    corresponding_subtotal = calculate_corresponding_subtotal(required_price, fees_coeff)
    assert corresponding_subtotal <= 111
    assert corresponding_subtotal >= 110

    response = payments_client.get('/payments/checkout-simulation?subtotal=117')
    assert response.status_code == 200
    assert response.json()["total"] == 126.36

    # test stripe functions
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
    headers = {"Authorization": f"Bearer {access_token}"}

    with patch('app.routers.payments.router.stripe', new_callable=Mock), \
    patch('app.routers.payments.router.stripe.Account.create', new_callable=Mock) as mock1, \
    patch('app.routers.payments.router.stripe.Account.create_person', new_callable=Mock) as mock2, \
    patch('app.routers.payments.router.stripe.Account.create_external_account', new_callable=Mock) as mock3, \
    patch('app.routers.payments.router.stripe.Webhook.construct_event', new_callable=Mock) as mock4:
        mock1.return_value={"id": "acct"}
        mock2.return_value={"id": "pers"}
        mock3.return_value={"last4": "2606"}

        # when account does not exist yet
        response = payments_client.get('/payments/stripe-account', headers=headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "no stripe account found"

        # unavailable business type
        body = {
            "business_type": "wtf",
            "account_token": "token",
            "bank_account_token": "token2",
            "additional_account_token": "token3"
        }
        response = payments_client.post('/payments/stripe-account', json=body, headers=headers)
        assert response.status_code == 422
        assert response.json()["detail"] == 'business_type has to be "company" or "individual"'

        # working json but legal identity is too low
        body = {
            "business_type": "individual",
            "account_token": "token",
            "bank_account_token": "token2",
            "additional_account_token": "token3"
        }
        response = payments_client.post('/payments/stripe-account', json=body, headers=headers)
        assert response.status_code == 409
        assert response.json()["detail"] == "legal identity level has to be 2"

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

        # working json
        body = {
            "business_type": "individual",
            "account_token": "token",
            "bank_account_token": "token2"
        }
        response = payments_client.post('/payments/stripe-account', json=body, headers=headers)
        assert response.status_code == 200

        response = users_client.get('/users/account-information', headers=headers)
        assert response.status_code == 200
        response_content = response.json()
        assert response_content["legal_identity"]["level"] == 3
        assert response_content["legal_identity"]["business_type"] == "individual"
        assert response_content["legal_identity"]["iban_last4"] == "2606"

        user_in_db = fake_db.users.find_one({})
        assert user_in_db["stripe_account"]["account"]["id"] == "acct"
        assert user_in_db["stripe_account"]["account"]["individual"]["verification"]["status"] == "pending"
        assert user_in_db["stripe_account"]["account"]["individual"]["verification"]["document"]["details_code"] == None
        assert user_in_db["stripe_account"]["account"]["individual"]["verification"]["additional_document"]["details_code"] == None
        assert user_in_db["stripe_account"]["account"]["requirements"]["currently_due"] == []

        response = payments_client.get('/payments/stripe-account', headers=headers)
        assert response.status_code == 200
        response_content = response.json()
        assert response_content["currently_due_is_empty"] == True
        assert response_content["identity_document_status"] == "pending"
        assert response_content["proof_of_residence_status"] == "pending"
        assert response_content["proof_of_company_status"] == None

        # working json but stripe account already exists
        body = {
            "business_type": "individual",
            "account_token": "token",
            "bank_account_token": "token2",
            "additional_account_token": "token3"
        }
        response = payments_client.post('/payments/stripe-account', json=body, headers=headers)
        assert response.status_code == 409
        assert response.json()["detail"] == "legal identity level has to be 2"

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

        response = payments_client.post('/payments/stripe-accounts-webhook', json={"this json": "is mocked anyways"}, headers={"stripe-signature": "osef"})
        assert response.status_code == 200

        user_in_db = fake_db.users.find_one({})
        assert user_in_db["stripe_account"]["account"]["id"] == "acct"
        assert user_in_db["stripe_account"]["account"]["individual"]["verification"]["status"] == "unverified"
        assert user_in_db["stripe_account"]["account"]["individual"]["verification"]["document"]["details_code"] == None
        assert user_in_db["stripe_account"]["account"]["individual"]["verification"]["additional_document"]["details_code"] == "err_ugly_document"
        assert user_in_db["stripe_account"]["account"]["requirements"]["currently_due"] == ["individual.verification.additional_document.front"]
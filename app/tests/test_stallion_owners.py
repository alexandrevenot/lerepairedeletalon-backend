def test(auth_client, stallion_owners_client):
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
    response = stallion_owners_client.post('/stallion-owners/stallion-owner', json=query, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == 'business_type has to be either "individual" or "company"'

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
    response = stallion_owners_client.post('/stallion-owners/stallion-owner', json=query, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == 'gender has to be either "Monsieur" or "Madame"'

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
    response = stallion_owners_client.post('/stallion-owners/stallion-owner', json=query, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "incorrect birthdate date format"

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
    response = stallion_owners_client.post('/stallion-owners/stallion-owner', json=query, headers=headers)
    assert response.status_code == 200
    stallion_owner_id_1 = response.json()["id"]

    response = stallion_owners_client.get('/stallion-owners/stallion-owner-names', headers=headers)
    assert response.status_code == 200
    stallion_owners = response.json()["stallion_owners"]
    assert len(stallion_owners) == 1
    stallion_owner = stallion_owners[0]
    assert stallion_owner["id"] == stallion_owner_id_1
    for key, value in query.items():
        assert stallion_owner[key] == value

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
    response = stallion_owners_client.put(f'/stallion-owners/stallion-owner/{stallion_owner_id_1}', json=query, headers=headers)
    assert response.status_code == 200

    response = stallion_owners_client.delete(f'/stallion-owners/stallion-owner/{stallion_owner_id_1}?stallion_id=', headers=headers)
    assert response.status_code == 200
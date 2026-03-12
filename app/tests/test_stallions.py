import datetime

from bson.objectid import ObjectId

from app.routers.stallions.utils import calculate_age
from app.routers.payments.utils import calculate_checkout

def test(auth_client, stallions_client, stallion_owners_client, fake_db):
    with open('tests/resources/sellefrançais.jpg', 'rb') as f:
        ph = f.read()
    with open('tests/resources/photo_too_large.jpg', 'rb') as f:
        phtl = f.read()

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

    headers = {"Authorization": f"Bearer {access_token}"}

    # add a stallion owner first
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
    stallion_owner_id = response.json()["id"]

    body = {}

    body["final_fields_body"] = {
        "name": "Michel du Rouet",
        "breed": "Selle Français",
        "n_sire": "8461684685X",
        "birthdate": "28/10/1998"
    }

    body["editable_fields_body"] = {
        "stallion_owner_id": stallion_owner_id,
        "main_desc": "desc",
        "color": "Bai tâcheté",
        "height": 170.5,
        "lat": 0.1,
        "lng": 0.6,
        "city": "Toulouse",
        "postal_code": "31000",
        "production_breeds": [
            "Selle Français"
        ],
        "cover_specs": {
            "hand": {
                "price": 750,
                "balance_payment_condition": "living_foal_48",
                "advance_percentage": 50,
                "cover_place": "ici",
                "maximum_nb_of_attempts": 3,
                "demanded_std_negative_tests": {
                    "arterite": {
                        "test_oldness": 28
                    }
                },
                "demanded_vaccines": ["tetanos"]
            }
        },
        "pedigree": [
            "Popa"
            ],
        "pedigree_po": "pedigree po",
        "cover_additional_info": "cover additional info",
        "performance": "perf",
        "stallion_additional_info": "stallion additional info",
        "offspring": "the offspring",
        "crossbreeding_advice": "que des juments cools",
        "stallion_std_negative_tests": {
            "metrite": {
                "test_date": "08/10/2023"
            },
            "arterite": {
                "test_date": "08/10/2023"
            }
        },
        "stallion_vaccines": [
            "rhino"
        ]
    }

    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 200

    stallion_id = response.json()["stallion_id"]

    files = (
        ("photos", ("photo.jpg", ph, "image/jpg")),
        ("photos", ("photo2.jpg", ph, "image/jpg"))
    )

    response = stallions_client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
    assert response.status_code == 200

    response = stallions_client.get('/stallions/my-stallions', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1
    assert str(response.json()["content"][0]["id"]) == stallion_id
    assert str(response.json()["content"][0]["name"]) == "Michel du Rouet"
    assert str(response.json()["content"][0]["breed"]) == "Selle Français"
    stallion_in_db = fake_db.stallions.find_one({"_id": ObjectId(stallion_id)})
    assert str(response.json()["content"][0]["photo_url"]) == stallion_in_db["thumbnail_photo"]
    assert response.json()["content"][0]["profile_status"] == "to_be_validated"
    assert len(response.json()["content"][0].keys()) == 6

    response = stallions_client.get('/stallions/available-stallion-breeds')
    assert response.status_code == 200
    assert response.json()['breeds'] == []

    response = stallions_client.get('/stallions/available-stallion-production-breeds')
    assert response.status_code == 200
    assert response.json()['breeds'] == []

    fake_db.stallions.update_one({"_id": ObjectId(stallion_id)}, {"$set": {"profile_status": "visible"}})

    response = stallions_client.get('/stallions/available-stallion-breeds')
    assert response.status_code == 200
    assert response.json()['breeds'] == ["Selle Français"]

    response = stallions_client.get('/stallions/available-stallion-production-breeds')
    assert response.status_code == 200
    assert response.json()['breeds'] == ['Selle Français']

    response = stallions_client.get(f'/stallions/stallion/{stallion_id}?mode=profile', headers=headers)
    assert response.status_code == 200
    content = response.json()

    handler_id = str(fake_db.users.find_one({"email": "lrdeservice@gmail.com"})["_id"])
    assert content["handler_id"] == handler_id
    assert content["name"] == "Michel du Rouet"
    assert content["breed"] == "Selle Français"
    assert content["n_sire"] == "8461684685X"
    assert content["age"] == calculate_age(datetime.datetime.strptime("28/10/1998","%d/%m/%Y"))
    assert content["main_desc"] == "desc"
    assert content["color"] == "Bai tâcheté"
    assert content["height"] == 170.5
    assert content["city"] == "Toulouse"
    assert content["dep_name"] == "Haute-Garonne"
    assert content["reg_name"] == "Occitanie"
    assert content["production_breeds"] == ["Selle Français"]
    assert content["cover_specs"]["hand"]["price"] == 750
    assert content["cover_specs"]["hand"]["balance_payment_condition"] == "living_foal_48"
    assert content["cover_specs"]["hand"]["advance_percentage"] == 50
    assert content["cover_specs"]["hand"]["cover_place"] == "ici"
    assert content["cover_specs"]["hand"]["maximum_nb_of_attempts"] == 3
    assert content["cover_specs"]["hand"]["demanded_std_negative_tests"]["arterite"]["test_oldness"] == 28
    assert content["cover_specs"]["hand"]["demanded_vaccines"] == ["tetanos"]
    assert content["pedigree"] == ['Popa'] + ['']*13
    assert content["pedigree_po"] == "pedigree po"
    assert content["cover_additional_info"] == "cover additional info"
    assert content["performance"] == "perf"
    assert content["stallion_additional_info"] == "stallion additional info"
    assert content["offspring"] == "the offspring"
    assert content["crossbreeding_advice"] == "que des juments cools"
    assert content["stallion_std_negative_tests"]["metrite"]['test_date'] == "08/10/2023"
    assert content["stallion_std_negative_tests"]["arterite"]['test_date'] == "08/10/2023"
    assert content["stallion_vaccines"] == [
            "rhino"
        ]


    body = {
        "stallion_owner_id": stallion_owner_id,
        "main_desc": "other desc",
        "color": "Bai plus tâcheté",
        "height": 171,
        "lat": 0.1,
        "lng": 0.7,
        "city": "Rodez",
        "postal_code": "12000",
        "production_breeds": [
            "Selle Français",
            "Boulonnais"
        ],
        "cover_specs": {
            "hand": {
                "price": 780,
                "balance_payment_condition": "living_foal",
                "advance_percentage": 40,
                "cover_place": "là",
                "maximum_nb_of_attempts": 4,
                "demanded_std_negative_tests": {
                    "arterite": {
                        "test_oldness": 27
                    }
                },
                "demanded_vaccines": ["grippe"]
            }
        },
        "pedigree": [
            "Popa",
            "Moman"
            ],
        "cover_additional_info": "other cover additional info",
        "performance": "other perf",
        "pedigree_po": "other pedigree po",
        "stallion_additional_info": "other stallion additional info",
        "offspring": "other the offspring",
        "crossbreeding_advice": "other que des juments cools",
        "stallion_std_negative_tests": {
            "metrite": {
                "test_date": "08/10/2023"
            },
            "arterite": {
                "test_date": "08/10/2023"
            },
            "anemie": {
                "test_date": "08/10/2023"
            }
        },
        "stallion_vaccines": [
            "rhino",
            "grippe"
        ]
    }

    response = stallions_client.put(f'/stallions/stallion/{stallion_id}', json=body, headers=headers)
    assert response.status_code == 200

    files = (
        ("kept_photos", (None, "1")),
        ("new_photos", ("photo.jpg", ph, "image/jpg"))
    )

    response = stallions_client.put(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
    assert response.status_code == 200

    response = stallions_client.get(f'/stallions/stallion/{stallion_id}?mode=profile', headers=headers)
    assert response.status_code == 200
    content = response.json()

    handler_id = str(fake_db.users.find_one({"email": "lrdeservice@gmail.com"})["_id"])
    assert content["handler_id"] == handler_id
    assert content["name"] == "Michel du Rouet"
    assert content["breed"] == "Selle Français"
    assert content["n_sire"] == "8461684685X"
    assert content["age"] == calculate_age(datetime.datetime.strptime("28/10/1998","%d/%m/%Y"))
    assert content["main_desc"] == "other desc"
    assert content["color"] == "Bai plus tâcheté"
    assert content["height"] == 171
    assert content["city"] == "Rodez"
    assert content["dep_name"] == "Aveyron"
    assert content["reg_name"] == "Occitanie"
    assert sorted(content["production_breeds"]), sorted(["Selle Français" == "Boulonnais"])
    assert content["cover_specs"]["hand"]["price"] == 780
    assert content["cover_specs"]["hand"]["balance_payment_condition"] == "living_foal"
    assert content["cover_specs"]["hand"]["advance_percentage"] == 40
    assert content["cover_specs"]["hand"]["maximum_nb_of_attempts"] == 4
    assert content["cover_specs"]["hand"]["cover_place"] == "là"
    assert content["cover_specs"]["hand"]["demanded_std_negative_tests"]["arterite"]["test_oldness"] == 27
    assert content["pedigree"], ['Popa' == 'Moman'] + ['']*12
    assert content["pedigree_po"] == "other pedigree po"
    assert content["cover_additional_info"] == "other cover additional info"
    assert content["performance"] == "other perf"
    assert content["stallion_additional_info"] == "other stallion additional info"
    assert content["offspring"] == "other the offspring"
    assert content["crossbreeding_advice"] == "other que des juments cools"
    assert content["stallion_std_negative_tests"]["metrite"]["test_date"] == "08/10/2023"
    assert content["stallion_std_negative_tests"]["arterite"]["test_date"] == "08/10/2023"
    assert content["stallion_std_negative_tests"]["anemie"]["test_date"] == "08/10/2023"
    assert content["stallion_vaccines"] == [
            "rhino",
            "grippe"
        ]

    response = stallions_client.delete(f'/stallions/stallion/{stallion_id}', headers=headers)
    assert response.status_code == 200

    assert 0 == len([_ for _ in fake_db.stallions.find()])

    # test invalid bodies for post stallion

    body = {}

    body["final_fields_body"] = {
        "name": "Michel du Rouet",
        "breed": "Selle Français",
        "n_sire": "8461684685X",
        "birthdate": "2810/1998"
    }

    body["editable_fields_body"] = {
        "stallion_owner_id": stallion_owner_id,
        "main_desc": "desc",
        "color": "Bai tâcheté",
        "height": 170.5,
        "lat": 0.1,
        "lng": 0.6,
        "city": "Toulouse",
        "postal_code": "31000",
        "production_breeds": [
            "Selle Français"
        ],
        "cover_specs": {
            "hand": {
                "price": 750,
                "balance_payment_condition": "living_foal_48",
                "advance_percentage": 50,
                "cover_place": "ici",
                "maximum_nb_of_attempts": 3,
                "demanded_std_negative_tests": {
                    "arterite": {
                        "test_oldness": 28
                    }
                },
                "demanded_vaccines": ["tetanos"]
            }
        },
        "pedigree": [
            "Popa"
            ],
        "pedigree_po": "pedigree po",
        "cover_additional_info": "cover additional info",
        "performance": "perf",
        "stallion_additional_info": "stallion additional info",
        "offspring": "the offspring",
        "crossbreeding_advice": "que des juments cools",
        "stallion_std_negative_tests": {
            "metrite": {
                "test_date": "08/10/2023"
            },
            "arterite": {
                "test_date": "08/10/2023"
            }
        },
        "stallion_vaccines": [
            "rhino"
        ]
    }

    # bad birthdate format
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "incorrect birth_date date format"

    # cover_specs
    body["final_fields_body"]["birthdate"] = "28/10/1998"
    body["editable_fields_body"]["cover_specs"]["hand"] = {
        "price": 750,
        "balance_payment_condition": "living_foal_485",
        "advance_percentage": 50,
        "cover_place": "ici",
        "maximum_nb_of_attempts": 3,
        "demanded_std_negative_tests": {
            "arterite": {
                "test_oldness": 28
            }
        },
        "demanded_vaccines": ["tetanos"]
    }
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "unallowed balance payment condition"

    # cover_specs
    body["editable_fields_body"]["cover_specs"]["hand"] = {
        "price": 750,
        "balance_payment_condition": "living_foal_48",
        "advance_percentage": 52,
        "cover_place": "ici",
        "maximum_nb_of_attempts": 3,
        "demanded_std_negative_tests": {
            "arterite": {
                "test_oldness": 28
            }
        },
        "demanded_vaccines": ["tetanos"]
    }
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "less_than_equal"

    # cover_specs
    body["editable_fields_body"]["cover_specs"]["hand"] = {
        "price": 750,
        "balance_payment_condition": "living_foal_48",
        "advance_percentage": 50,
        "cover_place": "ici",
        "maximum_nb_of_attempts": -1,
        "demanded_std_negative_tests": {
            "arterite": {
                "test_oldness": 28
            }
        },
        "demanded_vaccines": ["tetanos"]
    }
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "greater_than_equal"

    # cover_specs
    body["editable_fields_body"]["cover_specs"]["hand"] = {
        "price": 750,
        "balance_payment_condition": "living_foal_48",
        "advance_percentage": 50,
        "cover_place": "ici",
        "maximum_nb_of_attempts": 3,
        "demanded_std_negative_tests": {
            "arterite": {
                "test_oldness": None
            }
        },
        "demanded_vaccines": ["tetanos"]
    }
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "int_type"

    # cover_specs
    body["editable_fields_body"]["cover_specs"] = {}
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "atleast one cover type has to be offered"

    # pedigree
    body["editable_fields_body"]["cover_specs"]["hand"] = {
        "price": 750,
        "balance_payment_condition": "living_foal_48",
        "advance_percentage": 50,
        "cover_place": "ici",
        "maximum_nb_of_attempts": 3,
        "demanded_std_negative_tests": {
            "arterite": {
                "test_oldness": 28
            }
        },
        "demanded_vaccines": ["tetanos"]
    }
    body["editable_fields_body"]["pedigree"] = [""] * 15
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "too many items in pedigree"

    body["editable_fields_body"]["pedigree"] = ["Popa"]
    body["editable_fields_body"]["stallion_std_negative_tests"] = ["not a disease"]
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "model_attributes_type"

    body["editable_fields_body"]["stallion_std_negative_tests"] = {
        "anemie": {
            "test_date": "08/10/2023"
        }
    }
    body["editable_fields_body"]["stallion_vaccines"] = ["covid15"]
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "unallowed vaccines"

    # put stallion in db to test next routes 422
    body["editable_fields_body"]["stallion_vaccines"] = ["grippe"]
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    stallion_id = response.json()["stallion_id"]
    assert response.status_code == 200

    files = (
        ("photos", ("photo.jpg", ph, "image/jpg")),
        ("photos", ("photo2.jpg", phtl, "image/jpg"))
    )
    response = stallions_client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "a photo is too large"

    # register another user
    response = auth_client.post('/auth/register', json={
        "firstname": "Joris",
        "lastname": "Lagraphe",
        "email": "lrdeservice2@gmail.com",
        "phone_number": "0665824651",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200

    # login to get access token
    response = auth_client.post('/auth/login', json={
        "email": "lrdeservice2@gmail.com",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200
    assert "accessToken" in response.json()
    access_token = response.json()["accessToken"]

    other_headers = {"Authorization": f"Bearer {access_token}"}

    files = (
        ("photos", ("photo.jpg", ph, "image/jpg")),
        ("photos", ("photo2.jpg", ph, "image/jpg"))
    )

    response = stallions_client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=other_headers)
    assert response.status_code == 403

    response = stallions_client.post('/stallions/stallion-files/651bd0779fdb7d78aecf9ef3', files=files, headers=headers)
    assert response.status_code == 404

    response = stallions_client.post('/stallions/stallion-files/651bd0779fdb7d78aec', files=files, headers=headers)
    assert response.status_code == 422

    response = stallions_client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
    assert response.status_code == 200

    response = stallions_client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
    assert response.status_code == 403

    response = stallions_client.put(f'/stallions/stallion/{stallion_id}', json=body["editable_fields_body"], headers=other_headers)
    assert response.status_code == 403

    files = (
        ("photos", ("photo.jpg", ph, "image/jpg")),
        ("photos", ("photo2.jpg", ph, "image/jpg"))
    )

    response = stallions_client.put(f'/stallions/stallion-files/{stallion_id}', files=files, headers=other_headers)
    assert response.status_code == 403

    response = stallions_client.delete(f"/stallions/stallion/{stallion_id}", headers=headers)
    assert response.status_code == 200

    # add stallions for search
    # add a 2nd stallion owner
    query = {
        "business_type": "company",
        "firstname": "Georgelinette",
        "lastname": "Marcellinette",
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
    stallion_owner_id_2 = response.json()["id"]

    body = {}

    body["final_fields_body"] = {
        "name": "Joris",
        "breed": "Arabe",
        "n_sire": "65234871X",
        "birthdate": "28/10/1998"
    }

    body["editable_fields_body"] = {
        "stallion_owner_id": stallion_owner_id,
        "main_desc": "desc",
        "color": "Bai",
        "height": 170,
        "lat": 43.6,
        "lng": 1.433333,
        "city": "Toulouse",
        "postal_code": "31000",
        "production_breeds": [
            "Arabe",
            "Boulonnais"
        ],
        "cover_specs": {
            "lib": {
                "price": 750,
                "balance_payment_condition": "living_foal_48",
                "advance_percentage": 50,
                "cover_place": "ici",
                "maximum_nb_of_attempts": 3,
                "demanded_std_negative_tests": {
                    "arterite": {
                        "test_oldness": 28
                    }
                },
                "demanded_vaccines": ["tetanos"]
            },
            "hand": {
                "price": 1278,
                "balance_payment_condition": "living_foal_48",
                "advance_percentage": 50,
                "cover_place": "ici",
                "maximum_nb_of_attempts": 3,
                "demanded_std_negative_tests": {
                    "arterite": {
                        "test_oldness": 28
                    }
                },
                "demanded_vaccines": ["tetanos"]
            }
        },
        "pedigree": [
            "Popa"
            ],
        "pedigree_po": "pedigree po",
        "cover_additional_info": "cover additional info",
        "performance": "perf",
        "stallion_additional_info": "stallion additional info",
        "offspring": "the offspring",
        "crossbreeding_advice": "que des juments cools",
        "stallion_std_negative_tests": {
            "metrite": {
                "test_date": "08/10/2023"
            },
            "arterite": {
                "test_date": "08/10/2023"
            }
        },
        "stallion_vaccines": [
            "rhino"
        ]
    }
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 200
    joris_id = response.json()["stallion_id"]
    files = (
        ("photos", ("photo.jpg", ph, "image/jpg")),
        ("photos", ("photo2.jpg", ph, "image/jpg"))
    )
    response = stallions_client.post(f'/stallions/stallion-files/{joris_id}', files=files, headers=headers)
    assert response.status_code == 200

    body = {}

    body["final_fields_body"] = {
        "name": "Bertrand",
        "breed": "Fjord",
        "n_sire": "74566523X",
        "birthdate": "28/10/1998"
    }

    body["editable_fields_body"] = {
        "stallion_owner_id": stallion_owner_id,
        "main_desc": "desc",
        "color": "Blanc",
        "height": 177,
        "lat": 44.841225,
        "lng": -0.5800364,
        "city": "Bordeaux",
        "postal_code": "33000",
        "production_breeds": [
            "Fjord"
        ],
        "cover_specs": {
            "lib": {
                "price": 425,
                "balance_payment_condition": "living_foal_48",
                "advance_percentage": 50,
                "cover_place": "ici2",
                "maximum_nb_of_attempts": 3,
                "hosting_specs": {
                    "meadow": {
                        "price": 6
                    }
                },
                "demanded_std_negative_tests": {
                    "metrite": {
                        "test_oldness": 30
                    },
                    "arterite": {
                        "test_oldness": 30
                    }
                },
                "demanded_vaccines": []
            },
            "hand": {
                "price": 570,
                "balance_payment_condition": "living_foal_48",
                "advance_percentage": 50,
                "cover_place": "là2",
                "maximum_nb_of_attempts": 3,
                "hosting_specs": {
                    "meadow": {
                        "price": 6
                    }
                },
                "demanded_std_negative_tests": {
                    "metrite": {
                        "test_oldness": 30
                    },
                    "arterite": {
                        "test_oldness": 30
                    }
                },
                "demanded_vaccines": []
            }
        },
        "pedigree": [
            "Popa"
            ],
        "pedigree_po": "pedigree po",
        "cover_additional_info": "cover additional info",
        "performance": "perf",
        "stallion_additional_info": "stallion additional info",
        "offspring": "the offspring",
        "crossbreeding_advice": "que des juments cools",
        "stallion_std_negative_tests": {
            "metrite": {
                "test_date": "08/10/2023"
            },
            "arterite": {
                "test_date": "08/10/2023"
            }
        },
        "stallion_vaccines": [
            "rhino"
        ]
    }
    response = stallions_client.post('/stallions/stallion', json=body, headers=headers)
    assert response.status_code == 200
    bertrand_id = response.json()["stallion_id"]
    response = stallions_client.post(f'/stallions/stallion-files/{bertrand_id}', files=files, headers=headers)
    assert response.status_code == 200

    fake_db.stallions.update_many({},{"$set": {"profile_status": "visible"}})

    response = stallions_client.get('/stallions/available-stallion-breeds')
    assert response.status_code == 200
    assert response.json()['breeds'], ['Arabe' == 'Fjord']

    response = stallions_client.get('/stallions/available-stallion-production-breeds')
    assert response.status_code == 200
    assert response.json()['breeds'], ['Arabe', 'Boulonnais' == 'Fjord']

    response = stallions_client.put(f'/stallions/stallion-profile-status/{bertrand_id}?new_status=hidden', headers=headers)
    assert response.status_code == 200

    response = stallions_client.put(f'/stallions/stallion-profile-status/{bertrand_id}?new_status=wtf', headers=headers)
    assert response.status_code == 403

    response = stallions_client.put(f'/stallions/stallion-profile-status/{bertrand_id}?new_status=visible')
    assert response.status_code == 401

    response = stallions_client.put(f'/stallions/stallion-profile-status/{bertrand_id}?new_status=visible', headers=other_headers)
    assert response.status_code == 403

    response = stallions_client.put(f'/stallions/stallion-profile-status/{bertrand_id}?new_status=visible', headers=headers)
    assert response.status_code == 200

    # test stallion owners first
    response = stallion_owners_client.delete(f'/stallion-owners/stallion-owner/{stallion_owner_id}?stallion_id=', headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == 'a stallion is linked to this stallion owner'

    response = stallion_owners_client.delete(f'/stallion-owners/stallion-owner/{stallion_owner_id}?stallion_id={bertrand_id}', headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == 'this stallion is linked to this stallion owner'

    # with page <= 0
    response = stallions_client.get('/stallions/search?page=0&limit=16')
    assert response.status_code == 422

    # basic use for no filter
    response = stallions_client.get('/stallions/search?page=1&limit=16')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 2

    content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

    assert content_sorted_on_name[0]["name"] == "Bertrand"
    assert content_sorted_on_name[1]["name"] == "Joris"

    # prices

    # testing 422
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_price=bonjour')
    assert response.status_code == 422

    response = stallions_client.get('/stallions/search?page=1&limit=16&max_price=bonjour')
    assert response.status_code == 422

    response = stallions_client.get('/stallions/search?page=1&limit=16&max_price=bonjour&min_price=580')
    assert response.status_code == 422

    # (0) 425+f (1) 570+f (2) 750+f (3) 1278+f (4)

    fees_coeff = 0.08

    # (0) min
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_price=2')
    assert response.status_code == 200

    content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

    assert len(content_sorted_on_name) == 2
    def get_total(x: int):
        return calculate_checkout(x, fees_coeff).total
    assert content_sorted_on_name[0]["price"] == get_total(425)
    assert content_sorted_on_name[1]["price"] == get_total(750)

    # (0) max
    response = stallions_client.get('/stallions/search?page=1&limit=16&max_price=2')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 0

    # (1) min
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_price=430')
    assert response.status_code == 200

    content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

    assert len(content_sorted_on_name) == 2
    assert content_sorted_on_name[0]["price"] == get_total(425)
    assert content_sorted_on_name[1]["price"] == get_total(750)

    # (1) max
    response = stallions_client.get('/stallions/search?page=1&limit=16&max_price=568')
    assert response.status_code == 200

    content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

    assert len(content_sorted_on_name) == 1
    assert content_sorted_on_name[0]["price"] == get_total(425)

    # (2) min
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_price=580')
    assert response.status_code == 200

    content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

    assert len(content_sorted_on_name) == 2
    assert content_sorted_on_name[0]["price"] == get_total(570)
    assert content_sorted_on_name[1]["price"] == get_total(750)

    # (2) max
    response = stallions_client.get('/stallions/search?page=1&limit=16&max_price=740')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1
    assert response.json()["content"][0]["price"] == get_total(425)

    # (3) min
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_price=1277')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1
    assert response.json()["content"][0]["price"] == get_total(1278)

    # (3) max
    response = stallions_client.get('/stallions/search?page=1&limit=16&max_price=1277')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 2

    content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])
    assert content_sorted_on_name[0]["price"] == get_total(425)
    assert content_sorted_on_name[1]["price"] == get_total(750)

    # (4) min
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_price=8500')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 0

    # (4) max
    response = stallions_client.get('/stallions/search?page=1&limit=16&max_price=8500')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 2

    content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])
    assert content_sorted_on_name[0]["price"] == get_total(425)
    assert content_sorted_on_name[1]["price"] == get_total(750)

    # when min > max
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_price=1230&max_price=1177')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 0

    # mix min and max
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_price=560&max_price=1277')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 2

    content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])
    assert content_sorted_on_name[0]["price"] == get_total(570)
    assert content_sorted_on_name[1]["price"] == get_total(750)

    # when min height too high
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_height=180')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 0

    # only one height matches
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_height=160&max_height=175')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1
    assert response.json()["content"][0]["name"] == "Joris"

    # two heights match
    response = stallions_client.get('/stallions/search?page=1&limit=16&min_height=160&max_height=182')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 2

    # both breeds
    response = stallions_client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 2

    content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])
    assert len(content_sorted_on_name) == 2
    assert content_sorted_on_name[0]["price"] == get_total(425)
    assert content_sorted_on_name[1]["price"] == get_total(750)

    # one breed
    response = stallions_client.get('/stallions/search?page=1&limit=16&breeds=Fjord')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1
    assert response.json()["content"][0]["name"] == "Bertrand"
    assert response.json()["content"][0]["price"] == get_total(425)

    response = stallions_client.get('/stallions/search?page=1&limit=16&breeds=Arabe')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1
    assert response.json()["content"][0]["name"] == "Joris"
    assert response.json()["content"][0]["price"] == get_total(750)

    # among other breeds
    response = stallions_client.get('/stallions/search?page=1&limit=16&breeds=Arabe&breeds=Welsh')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1
    assert response.json()["content"][0]["name"] == "Joris"
    assert response.json()["content"][0]["price"] == get_total(750)

    # breed and price
    response = stallions_client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 2

    content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])
    assert len(content_sorted_on_name) == 2
    assert content_sorted_on_name[0]["price"] == get_total(570)
    assert content_sorted_on_name[1]["price"] == get_total(750)

    # production breeds
    response = stallions_client.get('/stallions/search?page=1&limit=16&production_breeds=Fjord&production_breeds=Boulonnais')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 2

    # many production breeds but only one stallion having one of them
    response = stallions_client.get('/stallions/search?page=1&limit=16&production_breeds=Fjord&production_breeds=Trakehner')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1
    assert response.json()["content"][0]["name"] == "Bertrand"

    # many production breeds but 0 stallion having one of them
    response = stallions_client.get('/stallions/search?page=1&limit=16&production_breeds=Percheron&production_breeds=Trakehner')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 0

    # price, breed and production_breeds
    response = stallions_client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1
    assert response.json()["content"][0]["price"] == get_total(570)

    # cover_type
    response = stallions_client.get('/stallions/search?page=1&limit=16&cover_types=hand')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 2
    assert response.json()["content"][0]["name"] == "Joris"
    assert response.json()["content"][0]["price"] == get_total(1278)
    assert response.json()["content"][1]["name"] == "Bertrand"
    assert response.json()["content"][1]["price"] == get_total(570)

    # testing 422 cover types
    response = stallions_client.get('/stallions/search?page=1&limit=16&cover_types=doesnotexist')
    assert response.status_code == 422

    response = stallions_client.get('/stallions/search?page=1&limit=16&cover_types=bonjour&cover_types=lib')
    assert response.status_code == 422

    # price, breed, production_breeds and cover_types with 0 result bcs the price of the cover type asked is too high
    response = stallions_client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner&cover_types=lib')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 0

    # price, breed, production_breeds and cover_types
    response = stallions_client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=100&production_breeds=Fjord&production_breeds=Trakehner&cover_types=hand')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1
    assert response.json()["content"][0]["price"] == get_total(570)

    # testing 422 when price, breed, production_breeds and cover_types
    response = stallions_client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner&cover_types=hand&cover_types=doesnotexist')
    assert response.status_code == 422

    # distance
    lat_balma = 43.611222
    lng_balma = 1.505792

    # incomplete distance parameters
    response = stallions_client.get(f'/stallions/search?page=1&limit=16&lat={lat_balma}&lng={lng_balma}')
    assert response.status_code == 422

    response = stallions_client.get(f'/stallions/search?page=1&limit=16&lat={lat_balma}&distance=1')
    assert response.status_code == 422

    response = stallions_client.get(f'/stallions/search?page=1&limit=16&lng={lng_balma}&distance=1')
    assert response.status_code == 422

    # different pages and limits
    response = stallions_client.get('/stallions/search?page=2&limit=16')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 0

    response = stallions_client.get('/stallions/search?page=1&limit=1')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1

    response = stallions_client.get('/stallions/search?page=2&limit=1')
    assert response.status_code == 200
    assert len(response.json()["content"]) == 1

    response = stallions_client.get('/stallions/search?page=2&limit=100000')
    assert response.status_code == 422

    response = stallions_client.get('/stallions/search?page=2&limit=-100000')
    assert response.status_code == 422

    # favorites
    stallions_it = fake_db.stallions.find()
    ids = [str(stallion["_id"]) for stallion in stallions_it]
    first_stallion_id = ids[0]
    second_stallion_id = ids[1]

    response = stallions_client.get('/stallions/favorites', headers=headers)
    assert response.json()["favorite_stallions"] == []

    response = stallions_client.delete(f'/stallions/favorites/{first_stallion_id}', headers=headers)
    assert response.status_code == 422

    response = stallions_client.get('/stallions/favorites', headers=headers)
    assert response.json()["favorite_stallions"] == []

    response = stallions_client.post(f'/stallions/favorites/{first_stallion_id}', headers=headers)
    assert response.status_code == 200

    response = stallions_client.get('/stallions/favorites', headers=headers)
    assert response.json()["favorite_stallions"] == [first_stallion_id]

    # when already in list
    response = stallions_client.post(f'/stallions/favorites/{first_stallion_id}', headers=headers)
    assert response.status_code == 422

    response = stallions_client.get('/stallions/favorites', headers=headers)
    assert response.json()["favorite_stallions"] == [first_stallion_id]

    response = stallions_client.delete(f'/stallions/favorites/{first_stallion_id}', headers=headers)
    assert response.status_code == 200

    response = stallions_client.get('/stallions/favorites', headers=headers)
    assert response.json()["favorite_stallions"] == []

    # putting both stallions
    response = stallions_client.post(f'/stallions/favorites/{first_stallion_id}', headers=headers)
    assert response.status_code == 200

    response = stallions_client.post(f'/stallions/favorites/{second_stallion_id}', headers=headers)
    assert response.status_code == 200

    response = stallions_client.get('/stallions/favorites', headers=headers)
    assert response.json()["favorite_stallions"] == ids

    response = stallions_client.delete(f'/stallions/favorites/{second_stallion_id}', headers=headers)
    assert response.status_code == 200

    response = stallions_client.get('/stallions/favorites', headers=headers)
    assert response.json()["favorite_stallions"] == [first_stallion_id]
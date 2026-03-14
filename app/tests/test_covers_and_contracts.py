import pytest
import datetime
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from aioresponses import aioresponses
from fastapi import HTTPException
from bson.objectid import ObjectId
from freezegun import freeze_time

from app.routers.covers.utils import check_arrival_date
from app.routers.contracts.utils import create_and_send_contract
from app.routers.payments.utils import calculate_advance
from app.config import settings

async def test(fake_db, stallion_owners_client, auth_client, payments_client, contracts_client, stallions_client, users_client, covers_client):
    with open('tests/resources/sellefrançais.jpg', 'rb') as f:
        ph = f.read()

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

    owner_headers = {"Authorization": f"Bearer {access_token}"}

    # add a stallion owner
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
    response = stallion_owners_client.post('/stallion-owners/stallion-owner', json=query, headers=owner_headers)
    assert response.status_code == 200
    stallion_owner_id = response.json()["id"]

    # add a stallion
    post_stallion_body = {}

    post_stallion_body["final_fields_body"] = {
        "name": "Michel du Rouet",
        "breed": "Selle Français",
        "n_sire": "65123458X",
        "birthdate": "28/10/1998"
    }

    post_stallion_body["editable_fields_body"] = {
        "stallion_owner_id": stallion_owner_id,
        "main_desc": "desc",
        "color": "Bai",
        "height": 170,
        "lat": 44.841225,
        "lng": -0.5800364,
        "city": "Bordeaux",
        "postal_code": "33000",
        "production_breeds": [
            "Selle Français"
        ],
        "cover_specs": {
            "lib": {
                "price": 750,
                "balance_payment_condition": "living_foal_48",
                "advance_percentage": 40,
                "cover_place": "ici2",
                "maximum_nb_of_attempts": 3,
                "demanded_std_negative_tests": {
                    "metrite": {
                        "test_oldness": 30,
                    },
                    "arterite": {
                        "test_oldness": 30,
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
                "test_date": "09/10/2023"
            },
            "arterite": {
                "test_date": "09/10/2023"
            }
        },
        "stallion_vaccines": [
            "rhino"
        ]
    }

    response = stallions_client.post('/stallions/stallion', json=post_stallion_body, headers=owner_headers)
    assert response.status_code == 200
    stallion_id = response.json()["stallion_id"]

    files = (
        ("photos", ("photo.jpg", ph, "image/jpg")),
        ("photos", ("photo2.jpg", ph, "image/jpg"))
    )

    response = stallions_client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=owner_headers)
    assert response.status_code == 200

    stallion_in_db = fake_db.stallions.find_one({"name": "Michel du Rouet"})

    # actual covers tests

    # adding a new user
    response = auth_client.post('/auth/register', json={
        "firstname": "Joris",
        "lastname": "Lagraphe",
        "email": "lrdeservice2@gmail.com",
        "phone_number": "0665824651",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200

    # login to get buyer access token
    response = auth_client.post('/auth/login', json={
        "email": "lrdeservice2@gmail.com",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200
    assert "accessToken" in response.json()
    access_token = response.json()["accessToken"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # when the stallion is not visible
    body = {
        "seller_id": str(stallion_in_db["handler_id"]),
        "stallion_id": stallion_id,
        "mare_nsire": "64853156156X",
        "mare_name": "Bernadette de Normandie",
        "mare_breed": "Boulonnais",
        "message": "Yo",
        "mare_pregnancy_history": "nada",
        "cover_type": "lib"
    }
    response = covers_client.post('/covers/cover', json=body, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "stallion not available for cover"

    fake_db.stallions.update_many(
        {},
        {
            "$set": {
                "profile_status": "visible"
            }
        }
    )

    # when seller id = buyer id
    body = {
        "seller_id": str(stallion_in_db["handler_id"]),
        "stallion_id": stallion_id,
        "mare_nsire": "64853156156X",
        "mare_name": "Bernadette de Normandie",
        "mare_breed": "Boulonnais",
        "mare_pregnancy_history": "nada",
        "message": "Yo",
        "cover_type": "lib"
    }
    response = covers_client.post('/covers/cover', json=body, headers=owner_headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "seller_id is equal to buyer_id"

    # when the stallion id does not exist
    body = {
        "seller_id": str(stallion_in_db["handler_id"]),
        "stallion_id": "650daa37f528f38e3e674aee",
        "mare_nsire": "64853156156X",
        "mare_name": "Bernadette de Normandie",
        "mare_breed": "Boulonnais",
        "mare_pregnancy_history": "nada",
        "message": "Yo",
        "cover_type": "lib"
    }
    response = covers_client.post('/covers/cover', json=body, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "stallion not found"

    # when the seller id does not exist
    body = {
        "seller_id": "650daa37f528f38e3e674aee",
        "stallion_id": stallion_id,
        "mare_nsire": "64853156156X",
        "mare_name": "Bernadette de Normandie",
        "mare_pregnancy_history": "nada",
        "mare_breed": "Boulonnais",
        "message": "Yo",
        "cover_type": "lib"
    }
    response = covers_client.post('/covers/cover', json=body, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "seller not found"

    # when the seller id is not readable
    body = {
        "seller_id": "wtf",
        "stallion_id": stallion_id,
        "mare_nsire": "64853156156X",
        "mare_name": "Bernadette de Normandie",
        "mare_breed": "Boulonnais",
        "mare_pregnancy_history": "nada",
        "message": "Yo",
        "cover_type": "lib"
    }
    response = covers_client.post('/covers/cover', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "seller_id is not readable"

    # when the cover type does not exist
    body = {
        "seller_id": str(stallion_in_db["handler_id"]),
        "stallion_id": stallion_id,
        "mare_nsire": "64853156156X",
        "mare_name": "Bernadette de Normandie",
        "mare_breed": "Boulonnais",
        "mare_pregnancy_history": "nada",
        "message": "Yo",
        "cover_type": "hand"
    }
    response = covers_client.post('/covers/cover', json=body, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "cover type does not exist on stallion"

    # stallion id not readable
    body = {
        "seller_id": str(stallion_in_db["handler_id"]),
        "stallion_id": "wtf",
        "mare_nsire": "64853156156X",
        "mare_name": "Bernadette de Normandie",
        "mare_breed": "Boulonnais",
        "message": "Yo",
        "mare_pregnancy_history": "nada",
        "cover_type": "lib"
    }
    response = covers_client.post('/covers/cover', json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "stallion_id is not readable"

    # when everything is fine
    body = {
        "seller_id": str(stallion_in_db["handler_id"]),
        "stallion_id": stallion_id,
        "mare_nsire": "64853156156X",
        "mare_name": "Bernadette de Normandie",
        "mare_breed": "Boulonnais",
        "message": "Yo",
        "mare_pregnancy_history": "nada",
        "cover_type": "lib"
    }
    response = covers_client.post('/covers/cover', json=body, headers=headers)
    assert response.status_code == 200

    # cover already exists
    body = {
        "seller_id": str(stallion_in_db["handler_id"]),
        "stallion_id": stallion_id,
        "mare_nsire": "64853156156X",
        "mare_name": "Bernadette de Normandie",
        "mare_breed": "Boulonnais",
        "message": "Yo",
        "mare_pregnancy_history": "nada",
        "cover_type": "lib"
    }
    response = covers_client.post('/covers/cover', json=body, headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "cover already exists"

    # REQUESTED
    # when everything is fine
    cover_in_db = fake_db.covers.find_one({},{})

    assert cover_in_db["seller_id"] == stallion_in_db["handler_id"]
    assert cover_in_db["mare_nsire"] == "64853156156X"
    assert cover_in_db["mare_name"] == "Bernadette de Normandie"
    assert cover_in_db["mare_breed"] == "Boulonnais"
    assert cover_in_db["mare_pregnancy_history"] == "nada"
    assert cover_in_db["message"] == "Yo"
    assert cover_in_db["cover_type"] == "lib"

    assert cover_in_db["status"] == settings.cover_status[0]
    buyer_in_db = fake_db.users.find_one({"firstname": "Joris"})
    assert cover_in_db["buyer_id"] == buyer_in_db["_id"]
    assert cover_in_db['stallion_nsire'] == stallion_in_db['n_sire']
    for field in ['name', 'breed', 'color', 'height', 'birthdate', 'offspring', 'performance', 'pedigree_po', 'pedigree']:
        assert cover_in_db[f'stallion_{field}'] == stallion_in_db[field]
    assert cover_in_db["cover_specs"]["balance_payment_condition"] == stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["balance_payment_condition"]
    assert cover_in_db["cover_specs"]["cover_place"] == stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["cover_place"]
    assert cover_in_db["cover_specs"]["maximum_nb_of_attempts"] == stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["maximum_nb_of_attempts"]
    assert cover_in_db["cover_specs"]["demanded_std_negative_tests"]["metrite"]["test_oldness"] == stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["demanded_std_negative_tests"]["metrite"]["test_oldness"]
    assert cover_in_db["cover_specs"]["demanded_std_negative_tests"]["arterite"]["test_oldness"] == stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["demanded_std_negative_tests"]["arterite"]["test_oldness"]
    assert cover_in_db["cover_specs"]["demanded_vaccines"] == stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["demanded_vaccines"]

    assert cover_in_db["timestamps"]["cursor_index"] == 1
    assert cover_in_db["timestamps"]["timestamps_list"][0]["timestamp"] < datetime.datetime.now()
    for timestamp in cover_in_db["timestamps"]["timestamps_list"][1:]:
        assert timestamp["timestamp"] is None
    assert cover_in_db["subtotal"] == 750
    assert cover_in_db["fees"] == settings.fees_coeff * 750
    assert cover_in_db["cover_specs"]["advance_percentage"] == 40
    assert cover_in_db["notes"] == {"seller": "", "buyer": ""}

    cover_id = str(cover_in_db["_id"])
    wrong_cover_id = "650eff43536a21d3970bf942"

    # check if cover is in right cover group + prices
    response = covers_client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["price"] == round(750 * (1 + settings.fees_coeff), 2)

    response = covers_client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=owner_headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0

    response = covers_client.get('/covers/cover-group?group=pendingApproval&point_of_view=seller', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0

    response = covers_client.get('/covers/cover-group?group=pendingApproval&point_of_view=seller', headers=owner_headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["price"] == 750

    # add another stallion + cover to check sorting on dates
    post_stallion_body["final_fields_body"]["n_sire"] = "591784564X"
    post_stallion_body["final_fields_body"]["name"] = "Osef du Chalet"

    response = stallions_client.post('/stallions/stallion', json=post_stallion_body, headers=owner_headers)
    assert response.status_code == 200
    second_stallion_id = response.json()["stallion_id"]

    fake_db.stallions.update_many(
        {},
        {
            "$set": {
                "profile_status": "visible"
            }
        }
    )

    second_stallion_in_db = fake_db.stallions.find_one({"_id": ObjectId(second_stallion_id)})

    body = {
        "seller_id": str(second_stallion_in_db["handler_id"]),
        "stallion_id": second_stallion_id,
        "mare_nsire": "1864896456X",
        "mare_name": "Mauricette",
        "mare_breed": "Boulonnais",
        "message": "Yo",
        "mare_pregnancy_history": "bcp de trucs",
        "cover_type": "lib"
    }
    response = covers_client.post('/covers/cover', json=body, headers=headers)
    assert response.status_code == 200

    response = covers_client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=headers)
    assert response.status_code == 200
    res_json = response.json()
    assert len(res_json["items"]) == 2
    assert res_json["items"][0]["mare_name"] == "Mauricette"
    second_cover_id = res_json["items"][0]["id"]

    # register another user
    response = auth_client.post('/auth/register', json={
        "firstname": "Jocelin",
        "lastname": "Verdier",
        "email": "lrdeservice3@gmail.com",
        "phone_number": "0665824651",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200

    # login to get access token
    response = auth_client.post('/auth/login', json={
        "email": "lrdeservice3@gmail.com",
        "password": "acjiodfehy"
    })
    assert response.status_code == 200
    assert "accessToken" in response.json()
    access_token = response.json()["accessToken"]

    other_user_headers = {"Authorization": f"Bearer {access_token}"}

    # user is neither buyer nor seller: 403
    response = covers_client.get(f'/covers/cover/{cover_id}', headers=other_user_headers)
    assert response.status_code == 403

    # wrong cover_id: 404
    response = covers_client.get(f'/covers/cover/{wrong_cover_id}', headers=headers)
    assert response.status_code == 404

    # when user is buyer
    response = covers_client.get(f'/covers/cover/{cover_id}', headers=headers)
    assert response.status_code == 200
    cover_information_json = response.json()
    for field in ['name', 'breed', 'height', 'color', 'pedigree', 'pedigree_po', 'performance', 'offspring', 'production_breeds']:
        assert cover_information_json[f'stallion_{field}'] == stallion_in_db[field]
    assert cover_information_json["stallion_nsire"] == stallion_in_db['n_sire']
    assert cover_information_json['stallion_birthdate'] == '28/10/1998'
    assert cover_information_json["mare_name"] == "Bernadette de Normandie"
    assert cover_information_json["mare_breed"] == "Boulonnais"
    assert cover_information_json["mare_nsire"] == "64853156156X"
    assert cover_information_json["mare_pregnancy_history"] == 'nada'
    assert cover_information_json["cover_type"] == "lib"
    assert cover_information_json["status"] == "requested"
    assert cover_information_json["price"] == round(750 * (1 + settings.fees_coeff), 2)
    assert cover_information_json["buyer_message"] == "Yo"
    assert cover_information_json["timestamps"][0]["timestamp"][:2] == "Le"
    assert cover_information_json["notes"] == ""
    assert cover_information_json["contact_firstname"] == "Michel"
    assert cover_information_json["contact_lastname"] == "Dupont"
    assert cover_information_json["contact_phone_number"] == ""
    assert cover_information_json["contact_email"] == ""
    assert cover_information_json["pov"] == "buyer"

    # when user is seller
    response = covers_client.get(f'/covers/cover/{cover_id}', headers=owner_headers)
    assert response.status_code == 200
    cover_information_json = response.json()
    assert cover_information_json["stallion_name"] == "Michel du Rouet"
    assert cover_information_json["stallion_breed"] == "Selle Français"
    assert cover_information_json["stallion_nsire"] == "65123458X"
    assert cover_information_json["stallion_production_breeds"] == ["Selle Français"]
    assert cover_information_json["mare_name"] == "Bernadette de Normandie"
    assert cover_information_json["mare_breed"] == "Boulonnais"
    assert cover_information_json["mare_nsire"] == "64853156156X"
    assert cover_information_json["cover_type"] == "lib"
    assert cover_information_json["status"] == "requested"
    assert cover_information_json["price"] == 750
    assert cover_information_json["buyer_message"] == "Yo"
    assert cover_information_json["timestamps"][0]["timestamp"][:2] == "Le"
    assert cover_information_json["notes"] == ""
    assert cover_information_json["contact_firstname"] == "Joris"
    assert cover_information_json["contact_lastname"] == "Lagraphe"
    assert cover_information_json["contact_phone_number"] == "0665824651"
    assert cover_information_json["contact_email"] == "lrdeservice2@gmail.com"
    assert cover_information_json["pov"] == "seller"

    # scores
    # when wrong user access token: 403
    response = covers_client.put(f"/covers/cover-notes/{cover_id}", json={"notes": "hehe"}, headers=other_user_headers)
    assert response.status_code == 403

    # when wrong cover id: 404
    response = covers_client.put(f"/covers/cover-notes/{wrong_cover_id}", json={"notes": "hehe"}, headers=headers)
    assert response.status_code == 404

    # when ok: modifying buyer scores: 200
    response = covers_client.put(f"/covers/cover-notes/{cover_id}", json={"notes": "hehe"}, headers=headers)
    assert response.status_code == 200

    # check that seller scores stayed the same
    response = covers_client.get(f'/covers/cover/{cover_id}', headers=owner_headers)
    assert response.json()["notes"] == ""

    # check that buyer scores indeed changed
    response = covers_client.get(f'/covers/cover/{cover_id}', headers=headers)
    assert response.json()["notes"] == "hehe"

    # COVER EDITION
    # when buyer tries to edit cover
    response = covers_client.put(f'/covers/cover/{cover_id}', json={"new_subtotal": 300}, headers=headers)
    assert response.status_code == 403

    # when seller edits price
    response = covers_client.put(f'/covers/cover/{cover_id}', json={"new_subtotal": 300}, headers=owner_headers)
    assert response.status_code == 200
    response = covers_client.get(f'/covers/cover/{cover_id}', headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["price"] == 300

    now = datetime.datetime.now()
    if now.month >= 10:
        value = datetime.datetime(year=now.year +1, month=1, day=1).strftime('%d/%m/%Y')
        response = covers_client.put(f'/covers/cover/{cover_id}', json={"arrival_date": value}, headers=owner_headers)
    else:
        value = now.strftime('%d/%m/%Y')
        response = covers_client.put(f'/covers/cover/{cover_id}', json={"arrival_date": value}, headers=owner_headers)
    assert response.status_code == 200
    response = covers_client.get(f'/covers/cover/{cover_id}', headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["arrival_date"] == value

    response = covers_client.put(f'/covers/cover/{cover_id}', json={"new_subtotal": 750}, headers=owner_headers)
    assert response.status_code == 200

    # APPROVED
    # approve cover request

    # with unexisting cover id
    response = covers_client.post(f'/covers/step-forward-cover/{wrong_cover_id}', json={"next_status": "approved"}, headers=owner_headers)
    assert response.status_code == 404

    # when its the buyer that tries to approve his own cover buying demand
    response = covers_client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "approved"}, headers=headers)
    assert response.status_code == 403

    # when ok
    response = covers_client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "approved"}, headers=owner_headers)
    assert response.status_code == 200

    cover_in_db = fake_db.covers.find_one({"_id": cover_in_db["_id"]})
    assert cover_in_db["status"] == settings.cover_status[1]
    assert not cover_in_db["timestamps"]["timestamps_list"][1]["status"] is None

    # when the cover is already approved
    response = covers_client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "approved"}, headers=owner_headers)
    assert response.status_code == 403

    # edition when the cover is already approved fails
    response = covers_client.put(f'/covers/cover/{cover_id}', json={"new_subtotal": 1200}, headers=owner_headers)
    assert response.status_code == 403

    # move back to requested, then denied, then requested, then approved
    response = covers_client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "requested"}, headers=owner_headers)
    assert response.status_code == 200

    response = covers_client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "denied"}, headers=owner_headers)
    assert response.status_code == 200

    response = covers_client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "requested"}, headers=owner_headers)
    assert response.status_code == 200

    response = covers_client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "approved"}, headers=owner_headers)
    assert response.status_code == 200

    # check if cover stays in right cover group
    response = covers_client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert response.json()["items"][0]["mare_name"] == "Bernadette de Normandie"

    response = covers_client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=owner_headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0

    response = covers_client.get('/covers/cover-group?group=pendingApproval&point_of_view=seller', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0

    response = covers_client.get('/covers/cover-group?group=pendingApproval&point_of_view=seller', headers=owner_headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert response.json()["items"][0]["mare_name"] == "Bernadette de Normandie"


    ## SIGNATURE
    with patch('app.routers.contracts.utils.create_and_send_contract', new_callable=AsyncMock) as mock0, \
    patch('app.routers.payments.router.stripe', new_callable=Mock), \
    patch('app.routers.payments.router.stripe.Account.create', new_callable=Mock) as mock1, \
    patch('app.routers.payments.router.stripe.Account.create_person', new_callable=Mock) as mock2, \
    patch('app.routers.payments.router.stripe.Account.create_external_account', new_callable=Mock) as mock3, \
    patch('app.routers.payments.router.stripe.Webhook.construct_event', new_callable=Mock) as mock4:
        mock0.return_value=({
            "data": {
                "contract": {
                    "id": "the_contract_id",
                    "signers": [
                        {
                            "email": "lrdeservice2@gmail.com",
                            "sign_page_url": "first_signer_sign_page_url"
                        },
                        {
                            "email": "lrdeservice@gmail.com",
                            "sign_page_url": "second_signer_sign_page_url"                        }
                    ]
                }
            }
        }, None)
        mock1.return_value={"id": "acct"}
        mock2.return_value={"id": "pers"}
        mock3.return_value={"last4": "2606"}

        # wrong cover id
        response = contracts_client.get(f'/contracts/sign-page-url/{wrong_cover_id}', headers=headers)
        assert response.status_code == 404

        # when a user not involved in the cover tries to sign
        response = contracts_client.get(f'/contracts/sign-page-url/{cover_id}', headers=other_user_headers)
        assert response.status_code == 403

        # when right user but insufficient legal identity level for buyer
        response = contracts_client.get(f'/contracts/sign-page-url/{cover_id}', headers=headers)
        assert response.status_code == 409
        assert response.json()["detail"] == "insufficient legal identity level for buyer"

        buyer_legal_identity = {
            "business_type": "individual",
            "gender": "Monsieur",
            "address_postal_code": "Whatever",
            "address_line1": "Whatever",
            "address_city": "Whatever",
            "birthdate": "12/12/1998",
            "birthplace": "Là",
            "citizenship": "Fr eheh"
        }
        response = users_client.put('/users/legal-identity', headers=headers, json=buyer_legal_identity)
        assert response.status_code == 200
        assert response.json()["new_level"] == 2

        # when right user but insufficient legal identity level for seller
        response = contracts_client.get(f'/contracts/sign-page-url/{cover_id}', headers=headers)
        assert response.status_code == 409
        assert response.json()["detail"] == "insufficient legal identity level for seller"

        seller_legal_identity = {
            "business_type": "company",
            "gender": "Monsieur",
            "company_name": "LRDE",
            "company_structure": "SAS",
            "capital": "1500",
            "siren": "123456789",
            "head_office_address_line1": "Whatever",
            "head_office_address_postal_code": "Whatever",
            "head_office_address_city": "Whatever",
            "role_in_company": "President",
            "birthdate": "01/01/2000",
            "address_line1": "Whatever",
            "address_postal_code": "Whatever",
            "address_city": "Whatever",
        }
        response = users_client.put('/users/legal-identity', headers=owner_headers, json=seller_legal_identity)
        assert response.status_code == 200
        assert response.json()["new_level"] == 2

        body = {
            "business_type": "individual",
            "account_token": "token",
            "bank_account_token": "token2"
        }
        response = payments_client.post('/payments/stripe-account', json=body, headers=owner_headers)
        assert response.status_code == 200

        # when ok
        response = contracts_client.get(f'/contracts/sign-page-url/{cover_id}', headers=headers)
        assert response.status_code == 200
        assert len(mock0.call_args_list) == 1
        assert response.json()["url"] == "first_signer_sign_page_url"

        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        assert cover_in_db["contract_id"] == "the_contract_id"

        buyer_in_db = fake_db.users.find_one({"email": "lrdeservice2@gmail.com"})
        seller_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
        assert cover_in_db["sign_page_urls"][str(buyer_in_db["_id"])] == "first_signer_sign_page_url"
        assert cover_in_db["sign_page_urls"][str(seller_in_db["_id"])] == "second_signer_sign_page_url"
        assert cover_in_db["status"] == "signingstarted"

        # when ok
        response = contracts_client.get(f'/contracts/sign-page-url/{cover_id}', headers=headers)
        assert response.status_code == 200
        assert response.json()["url"] == "first_signer_sign_page_url"
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        assert cover_in_db["status"] == "signingstarted"

    buyer_in_db = fake_db.users.find_one({"email": "lrdeservice2@gmail.com"})
    seller_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
    if cover_in_db["seller_id"] == cover_in_db["stallion_owner_id"]:
        stallion_owner_in_db = None
    else:
        stallion_owner_in_db = fake_db.stallion_owners.find_one({"_id": cover_in_db["stallion_owner_id"]})

    with aioresponses() as m:
        m.post('thisisanurl?token=osef', payload={"message": "success"})

        _, sent_body = await create_and_send_contract(
            "this-is-a-template-id",
            cover_in_db,
            buyer_in_db,
            seller_in_db,
            stallion_owner_in_db,
            True,
            168,
            [],
            "email",
            ["sms_verification_code"],
            "thisismyfrontendurl",
            "thisisanurl",
            "osef"
        )

    placeholders = {}
    for elt in sent_body["placeholder_fields"]:
        placeholders[elt["api_key"]] = elt["value"]

    cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})

    assert placeholders["total_ttc"] == cover_in_db["total"]
    assert placeholders["advance_ttc"] == calculate_advance(cover_in_db["total"], cover_in_db["cover_specs"]["advance_percentage"])

    # testing webhooks

    # with a wrong secret-token
    response = contracts_client.post('/contracts/esignatures-webhook',
        json={
            "status": "signer-signed",
            "secret_token": "nope",
            "data": {
                "contract": {
                    "id": "the_contract_id"
                },
                "signer": {
                    "signing_order": "1"
                }
            }
        }
    )
    assert response.status_code == 401
    cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
    assert cover_in_db["status"] == "signingstarted"

    # with wrong contract id
    response = contracts_client.post('/contracts/esignatures-webhook',
        json={
            "status": "signer-signed",
            "secret_token": settings.contracts_secret_token,
            "data": {
                "contract": {
                    "id": "nope"
                },
                "signer": {
                    "signing_order": "1"
                }
            }
        }
    )
    assert response.status_code == 500
    cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
    assert cover_in_db["status"] == "signingstarted"

    # with a status that is not "signer-signed"
    response = contracts_client.post('/contracts/esignatures-webhook',
        json={
            "status": "wtf",
            "secret_token": settings.contracts_secret_token,
            "data": {
                "contract": {
                    "id": "the_contract_id"
                },
                "signer": {
                    "signing_order": "1"
                }
            }
        }
    )
    assert response.status_code == 200
    cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
    assert cover_in_db["status"] == "signingstarted"

    # when ok
    response = contracts_client.post('/contracts/esignatures-webhook',
        json={
            "status": "signer-signed",
            "secret_token": settings.contracts_secret_token,
            "data": {
                "contract": {
                    "id": "the_contract_id"
                },
                "signer": {
                    "signing_order": "1"
                }
            }
        }
    )
    assert response.status_code == 200
    cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
    assert cover_in_db["status"] == "buyersigned"

    # check that cover is not forwarded twice if twice the same webhook is received
    response = contracts_client.post('/contracts/esignatures-webhook',
        json={
            "status": "signer-signed",
            "secret_token": settings.contracts_secret_token,
            "data": {
                "contract": {
                    "id": "the_contract_id"
                },
                "signer": {
                    "signing_order": "1"
                }
            }
        }
    )
    assert response.status_code == 200
    cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
    assert cover_in_db["status"] == "buyersigned"

    # check that checkout cannot be get because the contract is not sellersigned
    with patch('app.routers.payments.router.stripe.checkout.Session.expire', new_callable=Mock) as mock0, \
    patch('app.routers.payments.router.stripe.checkout.Session.create', new_callable=Mock) as mock1:
        response = payments_client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "status does not allow this payment"

    # check that cover is indeed forwarded when its signing_order == "2"
    response = contracts_client.post('/contracts/esignatures-webhook',
        json={
            "status": "signer-signed",
            "secret_token": settings.contracts_secret_token,
            "data": {
                "contract": {
                    "id": "the_contract_id"
                },
                "signer": {
                    "signing_order": "2"
                }
            }
        }
    )
    assert response.status_code == 200
    cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
    assert cover_in_db["status"] == "sellersigned"

    # checkout tests
    with patch('app.routers.payments.router.stripe.checkout.Session.create', new_callable=Mock) as create_mock, \
    patch('app.routers.payments.router.stripe.checkout.Session.retrieve', new_callable=MagicMock) as retrieve_mock:
        create_mock.return_value.client_secret = "secret0"
        create_mock.return_value.id = "id0"
        # when the cover id is not readable
        response = payments_client.get('/payments/get-checkout-session/oungabounga?payment_part=advance', headers=headers)
        assert response.status_code == 422

        # when the cover id is wrong
        response = payments_client.get(f'/payments/get-checkout-session/{wrong_cover_id}?payment_part=advance', headers=headers)
        assert response.status_code == 404

        # when the access token is not the buyers one
        response = payments_client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=owner_headers)
        assert response.status_code == 403

        # when payment_part is not allowed
        response = payments_client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=wtf', headers=headers)
        assert response.status_code == 422
        assert response.json()["detail"] == 'payment_part has to be either "advance" or "balance"'

        # when ok
        response = payments_client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
        assert response.status_code == 200
        assert response.json()["client_secret"] == "secret0"

        # when the session has not been completed, should send back the first client secret
        create_mock.return_value.client_secret = "secret1"
        create_mock.return_value.id = "id1"
        class CustomMock:
            status = "open"
            client_secret = "secret0"
            id = "id0"

            def __getitem__(self, key):
                return self.__getattribute__(key)

        retrieve_mock.return_value = CustomMock()

        response = payments_client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
        assert response.status_code == 200
        assert response.json()["client_secret"] == "secret0"

        # when the session has been completed but webhook hasnt hit yet, should raise 409 until webhook hit
        class CustomMock2:
            status = "complete"
            client_secret = None
            id = "id0"

            def __getitem__(self, key):
                return self.__getattribute__(key)
        retrieve_mock.return_value = CustomMock2()
        response = payments_client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
        assert response.status_code == 409
        assert response.json()["detail"] == "payment is completing"

        # try twice
        response = payments_client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
        assert response.status_code == 409
        assert response.json()["detail"] == "payment is completing"

    # trying to review before status >= downpaid
    response = users_client.post(f'/users/reviews/{str(cover_in_db["seller_id"])}', json={
        "cover_id": cover_id,
        "score": 5,
        "content": "mdr"
    }, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "cover status does not allow review writing"

    # simulate webhook hit
    with patch('app.routers.payments.router.stripe.Webhook.construct_event', new_callable=Mock) as construct_event_mock:
        # without headers
        construct_event_mock.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "id0"
                }
            }
        }
        response = payments_client.post('/payments/stripe-checkout-webhook', json={})
        assert response.status_code == 401
        assert response.json()["detail"] == "header not found"

        # when no cover with this session id can be found
        construct_event_mock.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "wtf"
                }
            }
        }
        response = payments_client.post('/payments/stripe-checkout-webhook', json={}, headers={"stripe-signature": "osef"})
        assert response.status_code == 404
        assert response.json()["detail"] == "cover not found"

        # when ok
        construct_event_mock.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "id0"
                }
            }
        }
        response = payments_client.post('/payments/stripe-checkout-webhook', json={}, headers={"stripe-signature": "osef"})
        assert response.status_code == 200
        assert response.json()["message"] == "successfully received webhook"

        cover_in_db = fake_db.covers.find_one({"_id": cover_in_db["_id"]})
        assert cover_in_db["status"] == "downpaid"

    # trying to pay advance without knowing it is already paid, and webhook has hit
    with patch('app.routers.payments.router.stripe.checkout.Session.create', new_callable=Mock) as create_mock, \
    patch('app.routers.payments.router.stripe.checkout.Session.retrieve', new_callable=MagicMock) as retrieve_mock:
        create_mock.return_value.client_secret = "secret2"
        create_mock.return_value.id = "id2"

        response = payments_client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "status does not allow this payment"

        # but balance should work
        response = payments_client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=balance', headers=headers)
        assert response.status_code == 200
        assert response.json()["client_secret"] == "secret2"


    # reviews
    response = covers_client.get(f'/covers/cover/{cover_id}', headers=headers)
    seller_id = response.json()["contact_id"]

    for review_pov in ["given", "received"]:
        for cover_pov in ["buyer", "seller"]:
            response = users_client.get(f'/users/reviews/{seller_id}?review_pov={review_pov}&cover_pov={cover_pov}', headers=headers)
            assert response.status_code == 200
            assert response.json()["reviews"] == []

    ## wrong current user
    response = users_client.post(f'/users/reviews/{seller_id}', json={
        "cover_id": cover_id,
        "score": 5,
        "content": "mdr"
    }, headers=other_user_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "no permissions to write a review"

    other_user_in_db = fake_db.users.find_one({"email": "lrdeservice3@gmail.com"})
    other_user_id = str(other_user_in_db["_id"])

    ## wrong target user
    response = users_client.post(f'/users/reviews/{other_user_id}', json={
        "cover_id": cover_id,
        "score": 5,
        "content": "mdr"
    }, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "no permissions to write a review"

    client_in_db = fake_db.users.find_one({"email": "lrdeservice2@gmail.com"})
    client_id = str(client_in_db["_id"])

    ## when target is user itself
    response = users_client.post(f'/users/reviews/{client_id}', json={
        "cover_id": cover_id,
        "score": 5,
        "content": "mdr"
    }, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "user cannot review itself"

    # check that reviews are indeed empty
    for review_pov in ["given", "received"]:
        for cover_pov in ["buyer", "seller"]:
            response = users_client.get(f'/users/reviews/{seller_id}?review_pov={review_pov}&cover_pov={cover_pov}', headers=headers)
            assert response.status_code == 200
            assert response.json()["reviews"] == []

    ## reviews
    response = users_client.post(f'/users/reviews/{seller_id}', json={
        "cover_id": cover_id,
        "score": 5,
        "content": "mdr"
    }, headers=headers)
    assert response.status_code == 200

    cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})

    seller_in_db = fake_db.users.find_one({"_id": ObjectId(seller_id)})
    assert seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["avg_score"] == 5
    assert seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["nb"] == 1
    assert len(seller_in_db["reviews"]["received"]["seller"]) == 1

    # check reviews in db
    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert response.json()["reviews"] == []

    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert response.json()["reviews"] == []

    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert response.json()["reviews"] == []

    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
    assert len(response.json()["reviews"]) == 1
    review = response.json()["reviews"][0]
    assert review["stallion_name"] == cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == cover_in_db["stallion_nsire"]
    assert review["reviewer_firstname"] == client_in_db["firstname"]
    assert review["reviewer_lastname"] == client_in_db["lastname"]
    assert review["reviewed_firstname"] == seller_in_db["firstname"]
    assert review["reviewed_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 5
    assert review["content"] == "mdr"

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert response.json()["reviews"] == []

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert response.json()["reviews"] == []

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert response.json()["reviews"] == []

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 1
    review = response.json()["reviews"][0]
    assert review["stallion_name"] == cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == cover_in_db["stallion_nsire"]
    assert review["reviewer_firstname"] == client_in_db["firstname"]
    assert review["reviewer_lastname"] == client_in_db["lastname"]
    assert review["reviewed_firstname"] == seller_in_db["firstname"]
    assert review["reviewed_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 5
    assert review["content"] == "mdr"

    ## when cover has already been reviewed
    response = users_client.post(f'/users/reviews/{seller_id}', json={
        "cover_id": cover_id,
        "score": 1,
        "content": "pa ouf"
    }, headers=headers)
    assert response.status_code == 403

    # validate balance payment with webhook
    with patch('app.routers.payments.router.stripe.Webhook.construct_event', new_callable=Mock) as construct_event_mock:
        construct_event_mock.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "id2"
                }
            }
        }
        response = payments_client.post('/payments/stripe-checkout-webhook', json={}, headers={"stripe-signature": "osef"})
        assert response.status_code == 200
        assert response.json()["message"] == "successfully received webhook"

    ## when cover has already been reviewed by the buyer
    response = users_client.post(f'/users/reviews/{seller_id}', json={
        "cover_id": cover_id,
        "score": 1,
        "content": "pa ouf"
    }, headers=headers)
    assert response.status_code == 403

    ## when seller is reviewing
    response = users_client.post(f'/users/reviews/{client_id}', json={
        "cover_id": cover_id,
        "score": 1,
        "content": "nulachier"
    }, headers=owner_headers)
    assert response.status_code == 200

    seller_in_db = fake_db.users.find_one({"_id": ObjectId(seller_id)})
    assert seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["avg_score"] == 5
    assert seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["nb"] == 1
    assert len(seller_in_db["reviews"]["received"]["seller"]) == 1

    client_in_db = fake_db.users.find_one({"_id": ObjectId(client_id)})
    assert client_in_db["buyer_score"] == 1
    assert len(client_in_db["reviews"]["received"]["buyer"]) == 1

    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 1
    review = response.json()["reviews"][0]
    assert review["stallion_name"] == cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == cover_in_db["stallion_nsire"]
    assert review["reviewer_firstname"] == client_in_db["firstname"]
    assert review["reviewer_lastname"] == client_in_db["lastname"]
    assert review["reviewed_firstname"] == seller_in_db["firstname"]
    assert review["reviewed_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 5
    assert review["content"] == "mdr"

    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 1
    review = response.json()["reviews"][0]
    assert review["stallion_name"] == cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == cover_in_db["stallion_nsire"]
    assert review["reviewer_firstname"] == seller_in_db["firstname"]
    assert review["reviewer_lastname"] == seller_in_db["lastname"]
    assert review["reviewed_firstname"] == client_in_db["firstname"]
    assert review["reviewed_lastname"] == client_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 1
    assert review["content"] == "nulachier"

    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 0

    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 0

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 1
    review = response.json()["reviews"][0]
    assert review["stallion_name"] == cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == cover_in_db["stallion_nsire"]
    assert review["reviewer_firstname"] == client_in_db["firstname"]
    assert review["reviewer_lastname"] == client_in_db["lastname"]
    assert review["reviewed_firstname"] == seller_in_db["firstname"]
    assert review["reviewed_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 5
    assert review["content"] == "mdr"

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 1
    review = response.json()["reviews"][0]
    assert review["stallion_name"] == cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == cover_in_db["stallion_nsire"]
    assert review["reviewed_firstname"] == client_in_db["firstname"]
    assert review["reviewed_lastname"] == client_in_db["lastname"]
    assert review["reviewer_firstname"] == seller_in_db["firstname"]
    assert review["reviewer_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 1
    assert review["content"] == "nulachier"

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 0

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 0

    # second cover to review
    ## put arrival date first
    now = datetime.datetime.now()
    if now.month >= 10:
        value = datetime.datetime(year=now.year +1, month=1, day=1).strftime('%d/%m/%Y')
        response = covers_client.put(f'/covers/cover/{second_cover_id}', json={"arrival_date": value}, headers=owner_headers)
    else:
        value = now.strftime('%d/%m/%Y')
        response = covers_client.put(f'/covers/cover/{second_cover_id}', json={"arrival_date": value}, headers=owner_headers)

    ## approve the cover
    response = covers_client.post(f'/covers/step-forward-cover/{second_cover_id}', json={"next_status": "approved"}, headers=owner_headers)
    assert response.status_code == 200

    with patch('app.routers.contracts.utils.create_and_send_contract', new_callable=AsyncMock) as mock:
        mock.return_value=({
            "data": {
                "contract": {
                    "id": "the_second_contract_id",
                    "signers": [
                        {
                            "email": "lrdeservice2@gmail.com",
                            "sign_page_url": "first_signer_sign_page_url"
                        },
                        {
                            "email": "lrdeservice@gmail.com",
                            "sign_page_url": "second_signer_sign_page_url"                        }
                    ]
                }
            }
        }, None)

        response = contracts_client.get(f'/contracts/sign-page-url/{second_cover_id}', headers=headers)
        assert response.status_code == 200

    response = contracts_client.post('/contracts/esignatures-webhook',
        json={
            "status": "signer-signed",
            "secret_token": settings.contracts_secret_token,
            "data": {
                "contract": {
                    "id": "the_second_contract_id"
                },
                "signer": {
                    "signing_order": "1"
                }
            }
        }
    )
    assert response.status_code == 200

    response = contracts_client.post('/contracts/esignatures-webhook',
        json={
            "status": "signer-signed",
            "secret_token": settings.contracts_secret_token,
            "data": {
                "contract": {
                    "id": "the_second_contract_id"
                },
                "signer": {
                    "signing_order": "2"
                }
            }
        }
    )
    assert response.status_code == 200

    with patch('app.routers.payments.router.stripe.checkout.Session.create', new_callable=Mock) as create_mock, \
    patch('app.routers.payments.router.stripe.checkout.Session.retrieve', new_callable=MagicMock) as retrieve_mock:
        create_mock.return_value.client_secret = "secret3"
        create_mock.return_value.id = "id3"

        # advance should work
        response = payments_client.get(f'/payments/get-checkout-session/{second_cover_id}?payment_part=advance', headers=headers)
        assert response.status_code == 200
        assert response.json()["client_secret"] == "secret3"

    with patch('app.routers.payments.router.stripe.Webhook.construct_event', new_callable=Mock) as construct_event_mock:
        construct_event_mock.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "id3"
                }
            }
        }
        response = payments_client.post('/payments/stripe-checkout-webhook', json={}, headers={"stripe-signature": "osef"})
        assert response.status_code == 200
        assert response.json()["message"] == "successfully received webhook"

    second_cover_in_db = fake_db.covers.find_one({"_id": ObjectId(second_cover_id)})
    assert second_cover_in_db["status"] == "downpaid"

    # posting the second review
    response = users_client.post(f'/users/reviews/{client_id}', json={
        "cover_id": second_cover_id,
        "score": 2,
        "content": "david goodenough"
    }, headers=owner_headers)
    assert response.status_code == 200

    seller_in_db = fake_db.users.find_one({"_id": ObjectId(seller_id)})
    assert seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["avg_score"] == 5
    assert seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["nb"] == 1
    assert len(seller_in_db["reviews"]["received"]["seller"]) == 1

    client_in_db = fake_db.users.find_one({"_id": ObjectId(client_id)})
    assert client_in_db["buyer_score"] == 1.5
    assert len(client_in_db["reviews"]["received"]["buyer"]) == 2

    # unchanged
    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 0

    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 0

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 0

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 0

    second_cover_in_db = fake_db.covers.find_one({"_id": ObjectId(second_cover_id)})

    response = users_client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 1
    review = response.json()["reviews"][0]
    assert review["stallion_name"] == cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == cover_in_db["stallion_nsire"]
    assert review["reviewer_firstname"] == client_in_db["firstname"]
    assert review["reviewer_lastname"] == client_in_db["lastname"]
    assert review["reviewed_firstname"] == seller_in_db["firstname"]
    assert review["reviewed_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 5
    assert review["content"] == "mdr"

    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 1
    review = response.json()["reviews"][0]
    assert review["stallion_name"] == cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == cover_in_db["stallion_nsire"]
    assert review["reviewer_firstname"] == client_in_db["firstname"]
    assert review["reviewer_lastname"] == client_in_db["lastname"]
    assert review["reviewed_firstname"] == seller_in_db["firstname"]
    assert review["reviewed_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 5
    assert review["content"] == "mdr"

    # changed
    response = users_client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 2

    review = response.json()["reviews"][0]
    assert review["stallion_name"] == second_cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == second_cover_in_db["stallion_nsire"]
    assert review["reviewed_firstname"] == client_in_db["firstname"]
    assert review["reviewed_lastname"] == client_in_db["lastname"]
    assert review["reviewer_firstname"] == seller_in_db["firstname"]
    assert review["reviewer_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 2
    assert review["content"] == "david goodenough"

    review = response.json()["reviews"][1]
    assert review["stallion_name"] == cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == cover_in_db["stallion_nsire"]
    assert review["reviewed_firstname"] == client_in_db["firstname"]
    assert review["reviewed_lastname"] == client_in_db["lastname"]
    assert review["reviewer_firstname"] == seller_in_db["firstname"]
    assert review["reviewer_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 1
    assert review["content"] == "nulachier"

    response = users_client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert len(response.json()["reviews"]) == 2

    review = response.json()["reviews"][0]
    assert review["stallion_name"] == second_cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == second_cover_in_db["stallion_nsire"]
    assert review["reviewed_firstname"] == client_in_db["firstname"]
    assert review["reviewed_lastname"] == client_in_db["lastname"]
    assert review["reviewer_firstname"] == seller_in_db["firstname"]
    assert review["reviewer_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 2
    assert review["content"] == "david goodenough"

    review = response.json()["reviews"][1]
    assert review["stallion_name"] == cover_in_db["stallion_name"]
    assert review["stallion_nsire"] == cover_in_db["stallion_nsire"]
    assert review["reviewed_firstname"] == client_in_db["firstname"]
    assert review["reviewed_lastname"] == client_in_db["lastname"]
    assert review["reviewer_firstname"] == seller_in_db["firstname"]
    assert review["reviewer_lastname"] == seller_in_db["lastname"]
    assert review["writing_date"] == datetime.datetime.now().strftime("le %d/%m/%Y")
    assert review["score"] == 1
    assert review["content"] == "nulachier"

    response = users_client.post(f'/users/reviews/{seller_id}', json={
        "cover_id": second_cover_id,
        "score": 4,
        "content": "plutôt bieng"
    }, headers=headers)
    assert response.status_code == 200

    # user-score
    response = users_client.get(f'/users/user-score/{seller_id}?cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert response.json()["firstname"] == "Michel"
    assert response.json()["lastname"] == "Dupont"
    assert response.json()["score"] == 4.5
    assert response.json()["nb_reviews"] == 2
    assert response.json()["owner_has_other_reviews"] == False

    response = users_client.get(f'/users/user-score/{seller_id}?cover_pov=seller&stallion_nsire=591784564X', headers=headers)
    assert response.status_code == 200
    assert response.json()["firstname"] == "Michel"
    assert response.json()["lastname"] == "Dupont"
    assert response.json()["score"] == 4
    assert response.json()["nb_reviews"] == 1
    assert response.json()["owner_has_other_reviews"] == True

    response = users_client.get(f'/users/user-score/{client_id}?cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert response.json()["firstname"] == "Joris"
    assert response.json()["lastname"] == "Lagraphe"
    assert response.json()["score"] == 1.5
    assert response.json()["nb_reviews"] == 2
    assert response.json()["owner_has_other_reviews"] == False

    # when such notes do not exist
    response = users_client.get(f'/users/user-score/{seller_id}?cover_pov=buyer', headers=headers)
    assert response.status_code == 200
    assert response.json()["firstname"] == "Michel"
    assert response.json()["lastname"] == "Dupont"
    assert response.json()["score"] == None
    assert response.json()["nb_reviews"] == None
    assert response.json()["owner_has_other_reviews"] == False

    response = users_client.get(f'/users/user-score/{seller_id}?cover_pov=buyer&stallion_nsire=591784564X', headers=headers)
    assert response.status_code == 200
    assert response.json()["firstname"] == "Michel"
    assert response.json()["lastname"] == "Dupont"
    assert response.json()["score"] == None
    assert response.json()["nb_reviews"] == None
    assert response.json()["owner_has_other_reviews"] == False

    response = users_client.get(f'/users/user-score/{client_id}?cover_pov=seller', headers=headers)
    assert response.status_code == 200
    assert response.json()["firstname"] == "Joris"
    assert response.json()["lastname"] == "Lagraphe"
    assert response.json()["score"] == None
    assert response.json()["nb_reviews"] == None
    assert response.json()["owner_has_other_reviews"] == False

def test_arrival_date():
    with freeze_time("2000-04-15"):
        check_arrival_date("15/04/2000")
        check_arrival_date("30/09/2000")
        with pytest.raises(HTTPException): check_arrival_date("14/04/2000")
        with pytest.raises(HTTPException): check_arrival_date("01/10/2000")

    with freeze_time("2000-10-15"):
        check_arrival_date("01/01/2001")
        check_arrival_date("30/09/2001")
        with pytest.raises(HTTPException): check_arrival_date("31/12/2000")
        with pytest.raises(HTTPException): check_arrival_date("01/10/2001")
import unittest
import datetime
from unittest.mock import Mock

from unittest.mock import Mock, MagicMock, AsyncMock, patch
from aioresponses import aioresponses
from fastapi import FastAPI, HTTPException
from bson.objectid import ObjectId
from fastapi.testclient import TestClient
from freezegun import freeze_time

from testing.context import fake_db, get_db, get_db_client, SMTPDummySession
import routers.auth.router as auth_router
import routers.stallions.router as stallions_router
import routers.stallions.utils as stallions_utils
import routers.covers.router as covers_router
import routers.covers.utils as covers_utils
import routers.payments.router as payments_router
import routers.payments.utils as payments_utils
import routers.contracts.router as contracts_router
import routers.contracts.utils as contracts_utils
import routers.users.router as users_router
import routers.stallion_owners.router as stallion_owners_router

stallions_config = stallions_utils.load_config()
payments_config = payments_utils.load_config()
config = covers_utils.load_config()
contracts_config = contracts_utils.load_config()

server = FastAPI()

server.dependency_overrides[auth_router.get_db] = get_db
server.dependency_overrides[stallions_router.get_db] = get_db
server.dependency_overrides[covers_router.get_db] = get_db
server.dependency_overrides[contracts_router.get_db] = get_db
server.dependency_overrides[users_router.get_db] = get_db
server.dependency_overrides[stallion_owners_router.get_db] = get_db

server.dependency_overrides[auth_router.get_db_client] = get_db_client
server.dependency_overrides[stallions_router.get_db_client] = get_db_client
server.dependency_overrides[contracts_router.get_db_client] = get_db_client
server.dependency_overrides[users_router.get_db_client] = get_db_client

server.dependency_overrides[stallions_router.get_stalllion_photos_bucket] = lambda: unittest.mock.Mock()

auth_router.mailing_utils.smtplib.SMTP = SMTPDummySession
auth_router.monitoring_tools.send_telegram_message = Mock()
stallions_router.monitoring_tools.send_telegram_message = Mock()
covers_router.monitoring_tools.send_telegram_message = Mock()
contracts_router.monitoring_tools.send_telegram_message = AsyncMock()

server.include_router(auth_router.router)
server.include_router(stallions_router.router)
server.include_router(covers_router.router)
server.include_router(contracts_router.router)
server.include_router(payments_router.router)
server.include_router(users_router.router)
server.include_router(stallion_owners_router.router)

client = TestClient(server)

class CoversTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ph = open('/lerepairedeletalon/server/app/testing/stallions/sellefrançais.jpg', 'rb')

    async def test(self):
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
        response = client.post('/stallion-owners/stallion-owner', json=query, headers=owner_headers)
        self.assertEqual(response.status_code, 200)
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

        response = client.post('/stallions/stallion', json=post_stallion_body, headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        stallion_id = response.json()["stallion_id"]

        files = (
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg"))
        )

        response = client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        stallion_in_db = fake_db.stallions.find_one({"name": "Michel du Rouet"})

        # actual covers tests

        # adding a new user
        response = client.post('/auth/register', json={
            "firstname": "Joris",
            "lastname": "Lagraphe",
            "email": "lrdeservice2@gmail.com",
            "phone_number": "0665824651",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)

        # login to get buyer access token
        response = client.post('/auth/login', json={
            "email": "lrdeservice2@gmail.com",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue("accessToken" in response.json())
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
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "stallion not available for cover")

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
        response = client.post('/covers/cover', json=body, headers=owner_headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "seller_id is equal to buyer_id")

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
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "stallion not found")

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
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "seller not found")

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
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "seller_id is not readable")

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
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "cover type does not exist on stallion")

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
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "stallion_id is not readable")

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
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 200)

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
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "cover already exists")

        # REQUESTED
        # when everything is fine
        cover_in_db = fake_db.covers.find_one({},{})

        self.assertEqual(cover_in_db["seller_id"], stallion_in_db["handler_id"])
        self.assertEqual(cover_in_db["mare_nsire"], "64853156156X")
        self.assertEqual(cover_in_db["mare_name"], "Bernadette de Normandie")
        self.assertEqual(cover_in_db["mare_breed"], "Boulonnais")
        self.assertEqual(cover_in_db["mare_pregnancy_history"], "nada")
        self.assertEqual(cover_in_db["message"], "Yo")
        self.assertEqual(cover_in_db["cover_type"], "lib")

        self.assertEqual(cover_in_db["status"], config["status"][0])
        buyer_in_db = fake_db.users.find_one({"firstname": "Joris"})
        self.assertEqual(cover_in_db["buyer_id"], buyer_in_db["_id"])
        self.assertEqual(cover_in_db['stallion_nsire'], stallion_in_db['n_sire'])
        for field in ['name', 'breed', 'color', 'height', 'birthdate', 'offspring', 'performance', 'pedigree_po', 'pedigree']:
            self.assertEqual(cover_in_db[f'stallion_{field}'], stallion_in_db[field])
        self.assertEqual(cover_in_db["cover_specs"]["balance_payment_condition"], stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["balance_payment_condition"])
        self.assertEqual(cover_in_db["cover_specs"]["cover_place"], stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["cover_place"])
        self.assertEqual(cover_in_db["cover_specs"]["maximum_nb_of_attempts"], stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["maximum_nb_of_attempts"])
        self.assertEqual(
            cover_in_db["cover_specs"]["demanded_std_negative_tests"]["metrite"]["test_oldness"],
            stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["demanded_std_negative_tests"]["metrite"]["test_oldness"]
        )
        self.assertEqual(
            cover_in_db["cover_specs"]["demanded_std_negative_tests"]["arterite"]["test_oldness"],
            stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["demanded_std_negative_tests"]["arterite"]["test_oldness"]
        )
        self.assertEqual(
            cover_in_db["cover_specs"]["demanded_vaccines"],
            stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["demanded_vaccines"]
        )

        self.assertEqual(cover_in_db["timestamps"]["cursor_index"], 1)
        self.assertTrue(cover_in_db["timestamps"]["timestamps_list"][0]["timestamp"] < datetime.datetime.now())
        for timestamp in cover_in_db["timestamps"]["timestamps_list"][1:]:
            self.assertIsNone(timestamp["timestamp"])
        self.assertEqual(cover_in_db["subtotal_ht"], 750)
        self.assertEqual(cover_in_db["fees_ht"], payments_config['fees_coeff'] * 750 + payments_config['fees_offset'])
        self.assertEqual(cover_in_db["cover_specs"]["advance_percentage"], 40)
        self.assertEqual(cover_in_db["notes"], {
            "seller": "",
            "buyer": ""
        })

        cover_id = str(cover_in_db["_id"])
        wrong_cover_id = "650eff43536a21d3970bf942"

        # check if cover is in right cover group + prices
        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(
            response.json()["items"][0]["price"],
            round(750 * (1 + payments_config["TVA_cover_coeff_HT"]), 2) \
            + round((750*payments_config['fees_coeff'] + payments_config["fees_offset"])*(1+payments_config['TVA_coeff_HT']), 2)
        )

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 0)

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 0)

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=seller', headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(response.json()["items"][0]["price"], round(750 * (1 + payments_config["TVA_cover_coeff_HT"]), 2))

        # add another stallion + cover to check sorting on dates
        post_stallion_body["final_fields_body"]["n_sire"] = "591784564X"
        post_stallion_body["final_fields_body"]["name"] = "Osef du Chalet"

        response = client.post('/stallions/stallion', json=post_stallion_body, headers=owner_headers)
        self.assertEqual(response.status_code, 200)
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
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(len(res_json["items"]), 2)
        self.assertEqual(res_json["items"][0]["mare_name"], "Mauricette")
        second_cover_id = res_json["items"][0]["id"]

        # register another user
        response = client.post('/auth/register', json={
            "firstname": "Jocelin",
            "lastname": "Verdier",
            "email": "lrdeservice3@gmail.com",
            "phone_number": "0665824651",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)

        # login to get access token
        response = client.post('/auth/login', json={
            "email": "lrdeservice3@gmail.com",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue("accessToken" in response.json())
        access_token = response.json()["accessToken"]

        other_user_headers = {"Authorization": f"Bearer {access_token}"}

        # user is neither buyer nor seller: 403
        response = client.get(f'/covers/cover/{cover_id}', headers=other_user_headers)
        self.assertEqual(response.status_code, 403)

        # wrong cover_id: 404
        response = client.get(f'/covers/cover/{wrong_cover_id}', headers=headers)
        self.assertEqual(response.status_code, 404)

        # when user is buyer
        response = client.get(f'/covers/cover/{cover_id}', headers=headers)
        self.assertEqual(response.status_code, 200)
        cover_information_json = response.json()
        for field in ['name', 'breed', 'height', 'color', 'pedigree', 'pedigree_po', 'performance', 'offspring', 'production_breeds']:
            self.assertEqual(cover_information_json[f'stallion_{field}'], stallion_in_db[field])
        self.assertEqual(cover_information_json["stallion_nsire"], stallion_in_db['n_sire'])
        self.assertEqual(cover_information_json['stallion_birthdate'], '28/10/1998')
        self.assertEqual(cover_information_json["mare_name"], "Bernadette de Normandie")
        self.assertEqual(cover_information_json["mare_breed"], "Boulonnais")
        self.assertEqual(cover_information_json["mare_nsire"], "64853156156X")
        self.assertEqual(cover_information_json["mare_pregnancy_history"], 'nada')
        self.assertEqual(cover_information_json["cover_type"], "lib")
        self.assertEqual(cover_information_json["status"], "requested")
        self.assertEqual(
            cover_information_json["price"],
            round(750 * (1 + payments_config["TVA_cover_coeff_HT"]), 2) \
            + round((750*payments_config['fees_coeff'] + payments_config["fees_offset"])*(1+payments_config['TVA_coeff_HT']), 2)
        )
        self.assertEqual(cover_information_json["buyer_message"], "Yo")
        self.assertEqual(cover_information_json["timestamps"][0]["timestamp"][:2], "Le")
        self.assertEqual(cover_information_json["notes"], "")
        self.assertEqual(cover_information_json["contact_firstname"], "Michel")
        self.assertEqual(cover_information_json["contact_lastname"], "Dupont")
        self.assertEqual(cover_information_json["contact_phone_number"], "")
        self.assertEqual(cover_information_json["contact_email"], "")
        self.assertEqual(cover_information_json["pov"], "buyer")

        # when user is seller
        response = client.get(f'/covers/cover/{cover_id}', headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        cover_information_json = response.json()
        self.assertEqual(cover_information_json["stallion_name"], "Michel du Rouet")
        self.assertEqual(cover_information_json["stallion_breed"], "Selle Français")
        self.assertEqual(cover_information_json["stallion_nsire"], "65123458X")
        self.assertEqual(cover_information_json["stallion_production_breeds"], ["Selle Français"])
        self.assertEqual(cover_information_json["mare_name"], "Bernadette de Normandie")
        self.assertEqual(cover_information_json["mare_breed"], "Boulonnais")
        self.assertEqual(cover_information_json["mare_nsire"], "64853156156X")
        self.assertEqual(cover_information_json["cover_type"], "lib")
        self.assertEqual(cover_information_json["status"], "requested")
        self.assertEqual(cover_information_json["price"], round(750 * (1 + payments_config["TVA_cover_coeff_HT"]), 2))
        self.assertEqual(cover_information_json["buyer_message"], "Yo")
        self.assertEqual(cover_information_json["timestamps"][0]["timestamp"][:2], "Le")
        self.assertEqual(cover_information_json["notes"], "")
        self.assertEqual(cover_information_json["contact_firstname"], "Joris")
        self.assertEqual(cover_information_json["contact_lastname"], "Lagraphe")
        self.assertEqual(cover_information_json["contact_phone_number"], "0665824651")
        self.assertEqual(cover_information_json["contact_email"], "lrdeservice2@gmail.com")
        self.assertEqual(cover_information_json["pov"], "seller")

        # scores
        # when wrong user access token: 403
        response = client.put(f"/covers/cover-notes/{cover_id}", json={"notes": "hehe"}, headers=other_user_headers)
        self.assertEqual(response.status_code, 403)

        # when wrong cover id: 404
        response = client.put(f"/covers/cover-notes/{wrong_cover_id}", json={"notes": "hehe"}, headers=headers)
        self.assertEqual(response.status_code, 404)

        # when ok: modifying buyer scores: 200
        response = client.put(f"/covers/cover-notes/{cover_id}", json={"notes": "hehe"}, headers=headers)
        self.assertEqual(response.status_code, 200)

        # check that seller scores stayed the same
        response = client.get(f'/covers/cover/{cover_id}', headers=owner_headers)
        self.assertEqual(response.json()["notes"], "")

        # check that buyer scores indeed changed
        response = client.get(f'/covers/cover/{cover_id}', headers=headers)
        self.assertEqual(response.json()["notes"], "hehe")

        # COVER EDITION
        # when buyer tries to edit cover
        response = client.put(f'/covers/cover/{cover_id}', json={"new_subtotal": 300}, headers=headers)
        self.assertEqual(response.status_code, 403)

        # when seller edits price
        response = client.put(f'/covers/cover/{cover_id}', json={"new_subtotal": 300}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        response = client.get(f'/covers/cover/{cover_id}', headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["price"], round(300*(1+payments_config["TVA_cover_coeff_HT"]), 2))

        now = datetime.datetime.now()
        if now.month >= 10:
            value = datetime.datetime(year=now.year +1, month=1, day=1).strftime('%d/%m/%Y')
            response = client.put(f'/covers/cover/{cover_id}', json={"arrival_date": value}, headers=owner_headers)
        else:
            value = now.strftime('%d/%m/%Y')
            response = client.put(f'/covers/cover/{cover_id}', json={"arrival_date": value}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        response = client.get(f'/covers/cover/{cover_id}', headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["arrival_date"], value)

        response = client.put(f'/covers/cover/{cover_id}', json={"new_subtotal": 750}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        # APPROVED
        # approve cover request

        # with unexisting cover id
        response = client.post(f'/covers/step-forward-cover/{wrong_cover_id}', json={"next_status": "approved"}, headers=owner_headers)
        self.assertEqual(response.status_code, 404)

        # when its the buyer that tries to approve his own cover buying demand
        response = client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "approved"}, headers=headers)
        self.assertEqual(response.status_code, 403)

        # when ok
        response = client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "approved"}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        cover_in_db = fake_db.covers.find_one({"_id": cover_in_db["_id"]})
        self.assertEqual(cover_in_db["status"], config["status"][1])
        self.assertFalse(cover_in_db["timestamps"]["timestamps_list"][1]["status"] is None)

        # when the cover is already approved
        response = client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "approved"}, headers=owner_headers)
        self.assertEqual(response.status_code, 403)

        # edition when the cover is already approved fails
        response = client.put(f'/covers/cover/{cover_id}', json={"new_subtotal": 1200}, headers=owner_headers)
        self.assertEqual(response.status_code, 403)

        # move back to requested, then denied, then requested, then approved
        response = client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "requested"}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        response = client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "denied"}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        response = client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "requested"}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        response = client.post(f'/covers/step-forward-cover/{cover_id}', json={"next_status": "approved"}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        # check if cover stays in right cover group
        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 2)
        self.assertEqual(response.json()["items"][0]["mare_name"], "Bernadette de Normandie")

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 0)

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 0)

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=seller', headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 2)
        self.assertEqual(response.json()["items"][0]["mare_name"], "Bernadette de Normandie")


        ## SIGNATURE
        with patch('routers.contracts.utils.create_and_send_contract', new_callable=AsyncMock) as mock0, \
        patch('routers.payments.router.stripe', new_callable=Mock), \
        patch('routers.payments.router.stripe.Account.create', new_callable=Mock) as mock1, \
        patch('routers.payments.router.stripe.Account.create_person', new_callable=Mock) as mock2, \
        patch('routers.payments.router.stripe.Account.create_external_account', new_callable=Mock) as mock3, \
        patch('routers.payments.router.stripe.Webhook.construct_event', new_callable=Mock) as mock4:
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
            response = client.get(f'/contracts/sign-page-url/{wrong_cover_id}', headers=headers)
            self.assertEqual(response.status_code, 404)

            # when a user not involved in the cover tries to sign
            response = client.get(f'/contracts/sign-page-url/{cover_id}', headers=other_user_headers)
            self.assertEqual(response.status_code, 403)

            # when right user but insufficient legal identity level for buyer
            response = client.get(f'/contracts/sign-page-url/{cover_id}', headers=headers)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"], "insufficient legal identity level for buyer")

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
            response = client.put('/users/legal-identity', headers=headers, json=buyer_legal_identity)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["new_level"], 2)

            # when right user but insufficient legal identity level for seller
            response = client.get(f'/contracts/sign-page-url/{cover_id}', headers=headers)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"], "insufficient legal identity level for seller")

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
            response = client.put('/users/legal-identity', headers=owner_headers, json=seller_legal_identity)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["new_level"], 2)

            body = {
                "business_type": "individual",
                "account_token": "token",
                "bank_account_token": "token2"
            }
            response = client.post('/payments/stripe-account', json=body, headers=owner_headers)
            self.assertEqual(response.status_code, 200)

            # when ok
            response = client.get(f'/contracts/sign-page-url/{cover_id}', headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(contracts_router.utils.create_and_send_contract.call_args_list), 1)
            self.assertEqual(response.json()["url"], "first_signer_sign_page_url")

            cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
            self.assertEqual(cover_in_db["contract_id"], "the_contract_id")

            buyer_in_db = fake_db.users.find_one({"email": "lrdeservice2@gmail.com"})
            seller_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
            self.assertEqual(cover_in_db["sign_page_urls"][str(buyer_in_db["_id"])], "first_signer_sign_page_url")
            self.assertEqual(cover_in_db["sign_page_urls"][str(seller_in_db["_id"])], "second_signer_sign_page_url")
            self.assertEqual(cover_in_db["status"], "signingstarted")

            # when ok
            response = client.get(f'/contracts/sign-page-url/{cover_id}', headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["url"], "first_signer_sign_page_url")
            cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
            self.assertEqual(cover_in_db["status"], "signingstarted")

        buyer_in_db = fake_db.users.find_one({"email": "lrdeservice2@gmail.com"})
        seller_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})
        if cover_in_db["seller_id"] == cover_in_db["stallion_owner_id"]:
            stallion_owner_in_db = None
        else:
            stallion_owner_in_db = fake_db.stallion_owners.find_one({"_id": cover_in_db["stallion_owner_id"]})

        with aioresponses() as m:
            m.post('thisisanurl?token=osef', payload={"message": "success"})

            _, sent_body = await contracts_utils.create_and_send_contract(
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

        self.assertEqual(placeholders["total_ht"], round(cover_in_db["subtotal_ht"] + cover_in_db["fees_ht"], 2))
        self.assertEqual(placeholders["total_ttc"], payments_utils.calculate_checkout(
            cover_in_db["subtotal_ht"],
            cover_in_db["fees_ht"],
            payments_config["TVA_coeff_HT"],
            payments_config["TVA_cover_coeff_HT"]
        ).total)
        self.assertEqual(placeholders["advance_ht"], payments_utils.calculate_advance(
            round(cover_in_db["subtotal_ht"] + cover_in_db["fees_ht"], 2),
            cover_in_db["cover_specs"]["advance_percentage"]
        ))
        self.assertEqual(placeholders["advance_ttc"], payments_utils.calculate_advance(
            payments_utils.calculate_checkout(
            cover_in_db["subtotal_ht"],
            cover_in_db["fees_ht"],
            payments_config["TVA_coeff_HT"],
            payments_config["TVA_cover_coeff_HT"]
            ).total,
            cover_in_db["cover_specs"]["advance_percentage"]
        ))

        # testing webhooks

        # with a wrong secret-token
        response = client.post(
            '/contracts/esignatures-webhook',
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
        self.assertEqual(response.status_code, 401)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "signingstarted")

        # with wrong contract id
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "secret_token": contracts_config['secret_token'],
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
        self.assertEqual(response.status_code, 500)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "signingstarted")

        # with a status that is not "signer-signed"
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "wtf",
                "secret_token": contracts_config['secret_token'],
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
        self.assertEqual(response.status_code, 200)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "signingstarted")

        # when ok
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "secret_token": contracts_config['secret_token'],
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
        self.assertEqual(response.status_code, 200)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "buyersigned")

        # check that cover is not forwarded twice if twice the same webhook is received
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "secret_token": contracts_config['secret_token'],
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
        self.assertEqual(response.status_code, 200)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "buyersigned")

        # check that checkout cannot be get because the contract is not sellersigned
        with patch('routers.payments.router.stripe.checkout.Session.expire', new_callable=Mock) as mock0, \
        patch('routers.payments.router.stripe.checkout.Session.create', new_callable=Mock) as mock1:
            response = client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["detail"], "status does not allow this payment")

        # check that cover is indeed forwarded when its signing_order == "2"
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "secret_token": contracts_config['secret_token'],
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
        self.assertEqual(response.status_code, 200)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "sellersigned")

        # checkout tests
        with patch('routers.payments.router.stripe.checkout.Session.create', new_callable=Mock) as create_mock, \
        patch('routers.payments.router.stripe.checkout.Session.retrieve', new_callable=MagicMock) as retrieve_mock:
            create_mock.return_value.client_secret = "secret0"
            create_mock.return_value.id = "id0"
            # when the cover id is not readable
            response = client.get('/payments/get-checkout-session/oungabounga?payment_part=advance', headers=headers)
            self.assertEqual(response.status_code, 422)

            # when the cover id is wrong
            response = client.get(f'/payments/get-checkout-session/{wrong_cover_id}?payment_part=advance', headers=headers)
            self.assertEqual(response.status_code, 404)

            # when the access token is not the buyers one
            response = client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=owner_headers)
            self.assertEqual(response.status_code, 403)

            # when payment_part is not allowed
            response = client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=wtf', headers=headers)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["detail"], 'payment_part has to be either "advance" or "balance"')

            # when ok
            response = client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["client_secret"], "secret0")

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

            response = client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["client_secret"], "secret0")

            # when the session has been completed but webhook hasnt hit yet, should raise 409 until webhook hit
            class CustomMock2:
                status = "complete"
                client_secret = None
                id = "id0"

                def __getitem__(self, key):
                    return self.__getattribute__(key)
            retrieve_mock.return_value = CustomMock2()
            response = client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"], "payment is completing")

            # try twice
            response = client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"], "payment is completing")

        # trying to review before status >= downpaid
        response = client.post(f'/users/reviews/{str(cover_in_db["seller_id"])}', json={
            "cover_id": cover_id,
            "score": 5,
            "content": "mdr"
        }, headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "cover status does not allow review writing")

        # simulate webhook hit
        with patch('routers.payments.router.stripe.Webhook.construct_event', new_callable=Mock) as construct_event_mock:
            # without headers
            construct_event_mock.return_value = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "id0"
                    }
                }
            }
            response = client.post('/payments/stripe-checkout-webhook', json={})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["detail"], "header not found")

            # when no cover with this session id can be found
            construct_event_mock.return_value = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "wtf"
                    }
                }
            }
            response = client.post('/payments/stripe-checkout-webhook', json={}, headers={"stripe-signature": "osef"})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["detail"], "cover not found")

            # when ok
            construct_event_mock.return_value = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "id0"
                    }
                }
            }
            response = client.post('/payments/stripe-checkout-webhook', json={}, headers={"stripe-signature": "osef"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["message"], "successfully received webhook")

            cover_in_db = fake_db.covers.find_one({"_id": cover_in_db["_id"]})
            self.assertEqual(cover_in_db["status"], "downpaid")

        # trying to pay advance without knowing it is already paid, and webhook has hit
        with patch('routers.payments.router.stripe.checkout.Session.create', new_callable=Mock) as create_mock, \
        patch('routers.payments.router.stripe.checkout.Session.retrieve', new_callable=MagicMock) as retrieve_mock:
            create_mock.return_value.client_secret = "secret2"
            create_mock.return_value.id = "id2"

            response = client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=advance', headers=headers)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["detail"], "status does not allow this payment")

            # but balance should work
            response = client.get(f'/payments/get-checkout-session/{cover_id}?payment_part=balance', headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["client_secret"], "secret2")


        # reviews
        response = client.get(f'/covers/cover/{cover_id}', headers=headers)
        seller_id = response.json()["contact_id"]
        response = client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=buyer')
        self.assertEqual(response.status_code, 401)

        for review_pov in ["given", "received"]:
            for cover_pov in ["buyer", "seller"]:
                response = client.get(f'/users/reviews/{seller_id}?review_pov={review_pov}&cover_pov={cover_pov}', headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["reviews"], [])

        ## wrong current user
        response = client.post(f'/users/reviews/{seller_id}', json={
            "cover_id": cover_id,
            "score": 5,
            "content": "mdr"
        }, headers=other_user_headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "no permissions to write a review")

        other_user_in_db = fake_db.users.find_one({"email": "lrdeservice3@gmail.com"})
        other_user_id = str(other_user_in_db["_id"])

        ## wrong target user
        response = client.post(f'/users/reviews/{other_user_id}', json={
            "cover_id": cover_id,
            "score": 5,
            "content": "mdr"
        }, headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "no permissions to write a review")

        client_in_db = fake_db.users.find_one({"email": "lrdeservice2@gmail.com"})
        client_id = str(client_in_db["_id"])

        ## when target is user itself
        response = client.post(f'/users/reviews/{client_id}', json={
            "cover_id": cover_id,
            "score": 5,
            "content": "mdr"
        }, headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "user cannot review itself")

        # check that reviews are indeed empty
        for review_pov in ["given", "received"]:
            for cover_pov in ["buyer", "seller"]:
                response = client.get(f'/users/reviews/{seller_id}?review_pov={review_pov}&cover_pov={cover_pov}', headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["reviews"], [])

        ## reviews
        response = client.post(f'/users/reviews/{seller_id}', json={
            "cover_id": cover_id,
            "score": 5,
            "content": "mdr"
        }, headers=headers)
        self.assertEqual(response.status_code, 200)

        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})

        seller_in_db = fake_db.users.find_one({"_id": ObjectId(seller_id)})
        self.assertEqual(seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["avg_score"], 5)
        self.assertEqual(seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["nb"], 1)
        self.assertEqual(len(seller_in_db["reviews"]["received"]["seller"]), 1)

        # check reviews in db
        response = client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reviews"], [])

        response = client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reviews"], [])

        response = client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reviews"], [])

        response = client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(len(response.json()["reviews"]), 1)
        review = response.json()["reviews"][0]
        self.assertEqual(review["stallion_name"], cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewer_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewed_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 5)
        self.assertEqual(review["content"], "mdr")

        response = client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reviews"], [])

        response = client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reviews"], [])

        response = client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reviews"], [])

        response = client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 1)
        review = response.json()["reviews"][0]
        self.assertEqual(review["stallion_name"], cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewer_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewed_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 5)
        self.assertEqual(review["content"], "mdr")

        ## when cover has already been reviewed
        response = client.post(f'/users/reviews/{seller_id}', json={
            "cover_id": cover_id,
            "score": 1,
            "content": "pa ouf"
        }, headers=headers)
        self.assertEqual(response.status_code, 403)

        # validate balance payment with webhook
        with patch('routers.payments.router.stripe.Webhook.construct_event', new_callable=Mock) as construct_event_mock:
            construct_event_mock.return_value = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "id2"
                    }
                }
            }
            response = client.post('/payments/stripe-checkout-webhook', json={}, headers={"stripe-signature": "osef"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["message"], "successfully received webhook")

        ## when cover has already been reviewed by the buyer
        response = client.post(f'/users/reviews/{seller_id}', json={
            "cover_id": cover_id,
            "score": 1,
            "content": "pa ouf"
        }, headers=headers)
        self.assertEqual(response.status_code, 403)

        ## when seller is reviewing
        response = client.post(f'/users/reviews/{client_id}', json={
            "cover_id": cover_id,
            "score": 1,
            "content": "nulachier"
        }, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        seller_in_db = fake_db.users.find_one({"_id": ObjectId(seller_id)})
        self.assertEqual(seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["avg_score"], 5)
        self.assertEqual(seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["nb"], 1)
        self.assertEqual(len(seller_in_db["reviews"]["received"]["seller"]), 1)

        client_in_db = fake_db.users.find_one({"_id": ObjectId(client_id)})
        self.assertEqual(client_in_db["buyer_score"], 1)
        self.assertEqual(len(client_in_db["reviews"]["received"]["buyer"]), 1)

        response = client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 1)
        review = response.json()["reviews"][0]
        self.assertEqual(review["stallion_name"], cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewer_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewed_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 5)
        self.assertEqual(review["content"], "mdr")

        response = client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 1)
        review = response.json()["reviews"][0]
        self.assertEqual(review["stallion_name"], cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewer_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["reviewed_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], client_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 1)
        self.assertEqual(review["content"], "nulachier")

        response = client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 0)

        response = client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 0)

        response = client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 1)
        review = response.json()["reviews"][0]
        self.assertEqual(review["stallion_name"], cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewer_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewed_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 5)
        self.assertEqual(review["content"], "mdr")

        response = client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 1)
        review = response.json()["reviews"][0]
        self.assertEqual(review["stallion_name"], cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewed_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewer_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 1)
        self.assertEqual(review["content"], "nulachier")

        response = client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 0)

        response = client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 0)

        # second cover to review
        ## put arrival date first
        now = datetime.datetime.now()
        if now.month >= 10:
            value = datetime.datetime(year=now.year +1, month=1, day=1).strftime('%d/%m/%Y')
            response = client.put(f'/covers/cover/{second_cover_id}', json={"arrival_date": value}, headers=owner_headers)
        else:
            value = now.strftime('%d/%m/%Y')
            response = client.put(f'/covers/cover/{second_cover_id}', json={"arrival_date": value}, headers=owner_headers)

        ## approve the cover
        response = client.post(f'/covers/step-forward-cover/{second_cover_id}', json={"next_status": "approved"}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        with patch('routers.contracts.utils.create_and_send_contract', new_callable=AsyncMock) as mock:
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

            response = client.get(f'/contracts/sign-page-url/{second_cover_id}', headers=headers)
            self.assertEqual(response.status_code, 200)

        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "secret_token": contracts_config['secret_token'],
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
        self.assertEqual(response.status_code, 200)

        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "secret_token": contracts_config['secret_token'],
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
        self.assertEqual(response.status_code, 200)

        with patch('routers.payments.router.stripe.checkout.Session.create', new_callable=Mock) as create_mock, \
        patch('routers.payments.router.stripe.checkout.Session.retrieve', new_callable=MagicMock) as retrieve_mock:
            create_mock.return_value.client_secret = "secret3"
            create_mock.return_value.id = "id3"

            # advance should work
            response = client.get(f'/payments/get-checkout-session/{second_cover_id}?payment_part=advance', headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["client_secret"], "secret3")

        with patch('routers.payments.router.stripe.Webhook.construct_event', new_callable=Mock) as construct_event_mock:
            construct_event_mock.return_value = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "id3"
                    }
                }
            }
            response = client.post('/payments/stripe-checkout-webhook', json={}, headers={"stripe-signature": "osef"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["message"], "successfully received webhook")

        second_cover_in_db = fake_db.covers.find_one({"_id": ObjectId(second_cover_id)})
        self.assertEqual(second_cover_in_db["status"], "downpaid")

        # posting the second review
        response = client.post(f'/users/reviews/{client_id}', json={
            "cover_id": second_cover_id,
            "score": 2,
            "content": "david goodenough"
        }, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        seller_in_db = fake_db.users.find_one({"_id": ObjectId(seller_id)})
        self.assertEqual(seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["avg_score"], 5)
        self.assertEqual(seller_in_db["seller_score"][cover_in_db["stallion_nsire"]]["nb"], 1)
        self.assertEqual(len(seller_in_db["reviews"]["received"]["seller"]), 1)

        client_in_db = fake_db.users.find_one({"_id": ObjectId(client_id)})
        self.assertEqual(client_in_db["buyer_score"], 1.5)
        self.assertEqual(len(client_in_db["reviews"]["received"]["buyer"]), 2)

        # unchanged
        response = client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 0)

        response = client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 0)

        response = client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 0)

        response = client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 0)

        second_cover_in_db = fake_db.covers.find_one({"_id": ObjectId(second_cover_id)})

        response = client.get(f'/users/reviews/{client_id}?review_pov=given&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 1)
        review = response.json()["reviews"][0]
        self.assertEqual(review["stallion_name"], cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewer_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewed_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 5)
        self.assertEqual(review["content"], "mdr")

        response = client.get(f'/users/reviews/{seller_id}?review_pov=received&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 1)
        review = response.json()["reviews"][0]
        self.assertEqual(review["stallion_name"], cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewer_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewed_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 5)
        self.assertEqual(review["content"], "mdr")

        # changed
        response = client.get(f'/users/reviews/{client_id}?review_pov=received&cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 2)

        review = response.json()["reviews"][0]
        self.assertEqual(review["stallion_name"], second_cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], second_cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewed_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewer_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 2)
        self.assertEqual(review["content"], "david goodenough")

        review = response.json()["reviews"][1]
        self.assertEqual(review["stallion_name"], cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewed_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewer_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 1)
        self.assertEqual(review["content"], "nulachier")

        response = client.get(f'/users/reviews/{seller_id}?review_pov=given&cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 2)

        review = response.json()["reviews"][0]
        self.assertEqual(review["stallion_name"], second_cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], second_cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewed_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewer_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 2)
        self.assertEqual(review["content"], "david goodenough")

        review = response.json()["reviews"][1]
        self.assertEqual(review["stallion_name"], cover_in_db["stallion_name"])
        self.assertEqual(review["stallion_nsire"], cover_in_db["stallion_nsire"])
        self.assertEqual(review["reviewed_firstname"], client_in_db["firstname"])
        self.assertEqual(review["reviewed_lastname"], client_in_db["lastname"])
        self.assertEqual(review["reviewer_firstname"], seller_in_db["firstname"])
        self.assertEqual(review["reviewer_lastname"], seller_in_db["lastname"])
        self.assertEqual(review["writing_date"], datetime.datetime.now().strftime("le %d/%m/%Y"))
        self.assertEqual(review["score"], 1)
        self.assertEqual(review["content"], "nulachier")

        response = client.post(f'/users/reviews/{seller_id}', json={
            "cover_id": second_cover_id,
            "score": 4,
            "content": "plutôt bieng"
        }, headers=headers)
        self.assertEqual(response.status_code, 200)

        # user-score
        response = client.get(f'/users/user-score/{seller_id}?cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firstname"], "Michel")
        self.assertEqual(response.json()["lastname"], "Dupont")
        self.assertEqual(response.json()["score"], 4.5)
        self.assertEqual(response.json()["nb_reviews"], 2)
        self.assertEqual(response.json()["owner_has_other_reviews"], False)

        response = client.get(f'/users/user-score/{seller_id}?cover_pov=seller&stallion_nsire=591784564X', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firstname"], "Michel")
        self.assertEqual(response.json()["lastname"], "Dupont")
        self.assertEqual(response.json()["score"], 4)
        self.assertEqual(response.json()["nb_reviews"], 1)
        self.assertEqual(response.json()["owner_has_other_reviews"], True)

        response = client.get(f'/users/user-score/{client_id}?cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firstname"], "Joris")
        self.assertEqual(response.json()["lastname"], "Lagraphe")
        self.assertEqual(response.json()["score"], 1.5)
        self.assertEqual(response.json()["nb_reviews"], 2)
        self.assertEqual(response.json()["owner_has_other_reviews"], False)

        # when such notes do not exist
        response = client.get(f'/users/user-score/{seller_id}?cover_pov=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firstname"], "Michel")
        self.assertEqual(response.json()["lastname"], "Dupont")
        self.assertEqual(response.json()["score"], None)
        self.assertEqual(response.json()["nb_reviews"], None)
        self.assertEqual(response.json()["owner_has_other_reviews"], False)

        response = client.get(f'/users/user-score/{seller_id}?cover_pov=buyer&stallion_nsire=591784564X', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firstname"], "Michel")
        self.assertEqual(response.json()["lastname"], "Dupont")
        self.assertEqual(response.json()["score"], None)
        self.assertEqual(response.json()["nb_reviews"], None)
        self.assertEqual(response.json()["owner_has_other_reviews"], False)

        response = client.get(f'/users/user-score/{client_id}?cover_pov=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firstname"], "Joris")
        self.assertEqual(response.json()["lastname"], "Lagraphe")
        self.assertEqual(response.json()["score"], None)
        self.assertEqual(response.json()["nb_reviews"], None)
        self.assertEqual(response.json()["owner_has_other_reviews"], False)

    def tearDown(self):
        self.ph.close()

class ArrivalDate(unittest.TestCase):
    def test(self):
        with freeze_time("2000-04-15"):
            covers_utils.check_arrival_date("15/04/2000")
            covers_utils.check_arrival_date("30/09/2000")
            self.assertRaises(HTTPException, covers_utils.check_arrival_date, "14/04/2000")
            self.assertRaises(HTTPException, covers_utils.check_arrival_date, "01/10/2000")

        with freeze_time("2000-10-15"):
            covers_utils.check_arrival_date("01/01/2001")
            covers_utils.check_arrival_date("30/09/2001")
            self.assertRaises(HTTPException, covers_utils.check_arrival_date, "31/12/2000")
            self.assertRaises(HTTPException, covers_utils.check_arrival_date, "01/10/2001")

if __name__ == '__main__':
    unittest.main()

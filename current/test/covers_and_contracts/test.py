import unittest
import base64
import os
import sys
import datetime
import math

from unittest.mock import AsyncMock, patch
from aioresponses import aioresponses

from fastapi import FastAPI
from bson.objectid import ObjectId

import mongomock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../bin/')))

import src.api.auth.router as auth_router
import src.api.stallions.router as stallions_router
import src.api.stallions.utils as stallions_utils
import src.api.covers.router as covers_router
import src.api.covers.utils as covers_utils
import src.api.pricing.router as pricing_router
import src.api.pricing.utils as pricing_utils
import src.api.contracts.router as contracts_router
import src.api.contracts.utils as contracts_utils

fake_client = mongomock.MongoClient()
fake_db = fake_client.main

stallions_config = stallions_utils.load_config()
pricing_config = pricing_utils.load_config()
config = covers_utils.load_config()
contracts_config = contracts_utils.load_config()

server = FastAPI()

server.dependency_overrides[auth_router.get_db] = lambda: fake_db
server.dependency_overrides[stallions_router.get_db] = lambda: fake_db
server.dependency_overrides[covers_router.get_db] = lambda: fake_db
server.dependency_overrides[contracts_router.get_db] = lambda: fake_db

server.include_router(auth_router.router)
server.include_router(stallions_router.router)
server.include_router(covers_router.router)
server.include_router(contracts_router.router)
server.include_router(pricing_router.router)

client = TestClient(server)

class CoversTest(unittest.IsolatedAsyncioTestCase):
    async def test(self):
        # register a new user
        response = client.post('/auth/register', json={
            "firstname": "Michel",
            "lastname": "Dupont",
            "email": "lrdeservice@gmail.com",
            "phone_number": "+33665824651",
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

        self.vf = open('/lerepairedeletalon/server/current/test/stallions/verification_file.png', 'rb')
        self.ph = open('/lerepairedeletalon/server/current/test/stallions/sellefrançais.jpg', 'rb')

        # add a stallion
        body = {}

        body["final_fields_body"] = {
            "name": "Michel du Rouet",
            "breed": "Selle Français",
            "n_sire": "65123458X",
            "birthdate": "28/10/1998"
        }

        body["editable_fields_body"] = {
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
                            "test_oldness": 30,
                        },
                        "arterite": {
                            "test_oldness": 30,
                        }
                    },
                    "demanded_vaccines": []
                },
                "iac": {
                    "price": 750,
                    "balance_payment_condition": "living_foal_48",
                    "advance_percentage": 40,
                    "nb_provided_straws": 9,
                    "left_straws_owner": "seller"
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

        response = client.post('/stallions/stallion', json=body, headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        stallion_id = response.json()["stallion_id"]

        files = (
            ("verification_file", ("verification_file.png", self.vf, "image/png")),
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
            "phone_number": "+33665824651",
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
            "seller_id": str(stallion_in_db["owner"]),
            "stallion_nsire": "65123458X",
            "mare_nsire": "64853156156X",
            "mare_name": "Bernadette de Normandie",
            "mare_breed": "Boulonnais",
            "message": "Yo",
            "cover_type": "iac",
            "provided_cover_place": "ici"
        }
        response = client.post('/covers/cover', json=body, headers=headers)

        self.assertEqual(response.status_code, 403)

        fake_db.stallions.update_many(
            {},
            {
                "$set": {
                    "profile_status": "visible"
                }
            }
        )

        # when everything is fine
        body = {
            "seller_id": str(stallion_in_db["owner"]),
            "stallion_nsire": "65123458X",
            "mare_nsire": "64853156156X",
            "mare_name": "Bernadette de Normandie",
            "mare_breed": "Boulonnais",
            "message": "Yo",
            "cover_type": "iac",
            "provided_cover_place": "ici"
        }
        response = client.post('/covers/cover', json=body, headers=headers)

        self.assertEqual(response.status_code, 200)

        fake_db.covers.delete_many({},{})

        # when seller id = buyer id
        body = {
            "seller_id": str(stallion_in_db["owner"]),
            "stallion_nsire": "65123458X",
            "mare_nsire": "64853156156X",
            "mare_name": "Bernadette de Normandie",
            "mare_breed": "Boulonnais",
            "message": "Yo",
            "cover_type": "iac",
            "provided_cover_place": "ici"
        }
        response = client.post('/covers/cover', json=body, headers=owner_headers)
        self.assertEqual(response.status_code, 400)

        # when the stallion nsire does not exist
        body = {
            "seller_id": str(stallion_in_db["owner"]),
            "stallion_nsire": "wtf",
            "mare_nsire": "64853156156X",
            "mare_name": "Bernadette de Normandie",
            "mare_breed": "Boulonnais",
            "message": "Yo",
            "cover_type": "iac",
            "provided_cover_place": "ici"
        }
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 404)

        # when the seller id does not exist
        body = {
            "seller_id": "650daa37f528f38e3e674aee",
            "stallion_nsire": "65123458X",
            "mare_nsire": "64853156156X",
            "mare_name": "Bernadette de Normandie",
            "mare_breed": "Boulonnais",
            "message": "Yo",
            "cover_type": "iac",
            "provided_cover_place": "ici"
        }
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 404)

        # when the seller id is not readable
        body = {
            "seller_id": "wtf",
            "stallion_nsire": "65123458X",
            "mare_nsire": "64853156156X",
            "mare_name": "Bernadette de Normandie",
            "mare_breed": "Boulonnais",
            "message": "Yo",
            "cover_type": "iac",
            "provided_cover_place": "ici"
        }
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        # when the cover type does not exist
        body = {
            "seller_id": str(stallion_in_db["owner"]),
            "stallion_nsire": "65123458X",
            "mare_nsire": "64853156156X",
            "mare_name": "Bernadette de Normandie",
            "mare_breed": "Boulonnais",
            "message": "Yo",
            "cover_type": "wtf",
            "provided_cover_place": "ici"
        }
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        # REQUESTED
        # when everything is fine
        body = {
            "seller_id": str(stallion_in_db["owner"]),
            "stallion_nsire": "65123458X",
            "mare_nsire": "64853156156X",
            "mare_name": "Bernadette de Normandie",
            "mare_breed": "Boulonnais",
            "message": "Yo",
            "cover_type": "iac",
            "provided_cover_place": "ici"
        }
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 200)

        cover_in_db = fake_db.covers.find_one({},{})

        self.assertEqual(cover_in_db["seller_id"], stallion_in_db["owner"])
        self.assertEqual(cover_in_db["stallion_nsire"], "65123458X")
        self.assertEqual(cover_in_db["mare_nsire"], "64853156156X")
        self.assertEqual(cover_in_db["mare_name"], "Bernadette de Normandie")
        self.assertEqual(cover_in_db["mare_breed"], "Boulonnais")
        self.assertEqual(cover_in_db["message"], "Yo")
        self.assertEqual(cover_in_db["cover_type"], "iac")

        self.assertEqual(cover_in_db["status"], config["status"][0])
        buyer_in_db = fake_db.users.find_one({"firstname": "Joris"})
        self.assertEqual(cover_in_db["buyer_id"], buyer_in_db["_id"])
        self.assertEqual(cover_in_db["stallion_name"], stallion_in_db["name"])
        self.assertEqual(cover_in_db["stallion_breed"], stallion_in_db["breed"])
        self.assertEqual(cover_in_db["stallion_production_breeds"], stallion_in_db["production_breeds"])
        self.assertEqual(cover_in_db["cover_specs"]["balance_payment_condition"], stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["balance_payment_condition"])
        self.assertEqual(cover_in_db["cover_specs"]["left_straws_owner"], stallion_in_db["cover_specs"][cover_in_db["cover_type"]]["left_straws_owner"])
        self.assertEqual(cover_in_db["timestamps"]["cursor_index"], 1)
        self.assertTrue(cover_in_db["timestamps"]["timestamps_list"][0]["timestamp"] < datetime.datetime.now())
        for timestamp in cover_in_db["timestamps"]["timestamps_list"][1:]:
            self.assertIsNone(timestamp["timestamp"])
        self.assertEqual(cover_in_db["provided_cover_place"], "ici")
        self.assertEqual(cover_in_db["subtotal"], 750)
        self.assertEqual(cover_in_db["buyer_fees_ht"], 45)
        self.assertEqual(cover_in_db["buyer_fees_ht"], 45)
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
        self.assertEqual(response.json()["items"][0]["price"], 750 + math.ceil(45*1.2))

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 0)

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=seller', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 0)

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=seller', headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(response.json()["items"][0]["price"], 750 - math.ceil(45*1.2))

        # add another cover to check sorting on dates
        body = {
            "seller_id": str(stallion_in_db["owner"]),
            "stallion_nsire": "65123458X",
            "mare_nsire": "1864896456X",
            "mare_name": "Mauricette",
            "mare_breed": "Boulonnais",
            "message": "Yo",
            "cover_type": "iac",
            "provided_cover_place": "ici"
        }
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.get('/covers/cover-group?group=pendingApproval&point_of_view=buyer', headers=headers)
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(len(res_json["items"]), 2)
        self.assertEqual(res_json["items"][0]["mare_name"], "Mauricette")

        # register another user
        response = client.post('/auth/register', json={
            "firstname": "Jocelin",
            "lastname": "Verdier",
            "email": "lrdeservice3@gmail.com",
            "phone_number": "+33665824651",
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
        self.assertEqual(cover_information_json["stallion_name"], "Michel du Rouet")
        self.assertEqual(cover_information_json["stallion_breed"], "Selle Français")
        self.assertEqual(cover_information_json["stallion_nsire"], "65123458X")
        self.assertEqual(cover_information_json["stallion_production_breeds"], ["Selle Français"])
        self.assertEqual(cover_information_json["mare_name"], "Bernadette de Normandie")
        self.assertEqual(cover_information_json["mare_breed"], "Boulonnais")
        self.assertEqual(cover_information_json["mare_nsire"], "64853156156X")
        self.assertEqual(cover_information_json["cover_type"], "iac")
        self.assertEqual(cover_information_json["provided_cover_place"], "ici")
        self.assertEqual(cover_information_json["status"], "requested")
        self.assertEqual(cover_information_json["price"], 750 + math.ceil(45*1.2))
        self.assertEqual(cover_information_json["buyer_message"], "Yo")
        self.assertEqual(cover_information_json["timestamps"][0]["timestamp"][:2], "Le")
        self.assertEqual(cover_information_json["notes"], "")
        self.assertEqual(cover_information_json["contact_name"], "Michel Dupont")
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
        self.assertEqual(cover_information_json["cover_type"], "iac")
        self.assertEqual(cover_information_json["provided_cover_place"], "ici")
        self.assertEqual(cover_information_json["status"], "requested")
        self.assertEqual(cover_information_json["price"], 750 - math.ceil(45*1.2))
        self.assertEqual(cover_information_json["buyer_message"], "Yo")
        self.assertEqual(cover_information_json["timestamps"][0]["timestamp"][:2], "Le")
        self.assertEqual(cover_information_json["notes"], "")
        self.assertEqual(cover_information_json["contact_name"], "Joris Lagraphe")
        self.assertEqual(cover_information_json["contact_phone_number"], "+33665824651")
        self.assertEqual(cover_information_json["contact_email"], "lrdeservice2@gmail.com")
        self.assertEqual(cover_information_json["pov"], "seller")

        # notes
        # when wrong user access token: 403
        response = client.put(f"/covers/cover-notes/{cover_id}", json={"notes": "hehe"}, headers=other_user_headers)
        self.assertEqual(response.status_code, 403)

        # when wrong cover id: 404
        response = client.put(f"/covers/cover-notes/{wrong_cover_id}", json={"notes": "hehe"}, headers=headers)
        self.assertEqual(response.status_code, 404)

        # when ok: modifying buyer notes: 200
        response = client.put(f"/covers/cover-notes/{cover_id}", json={"notes": "hehe"}, headers=headers)
        self.assertEqual(response.status_code, 200)

        # check that seller notes stayed the same
        response = client.get(f'/covers/cover/{cover_id}', headers=owner_headers)
        self.assertEqual(response.json()["notes"], "")

        # check that buyer notes indeed changed
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
        self.assertEqual(response.json()["price"], 300 - math.ceil(0.06 * 300 * 1.2))

        response = client.put(f'/covers/cover/{cover_id}', json={"arrival_date": "28/10/1998"}, headers=owner_headers)
        self.assertEqual(response.status_code, 403)

        response = client.put(f'/covers/cover/{cover_id}', json={"new_subtotal": 750}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)

        # quick tests on a cover type allowing to set arrival date

        body = {
            "seller_id": str(stallion_in_db["owner"]),
            "stallion_nsire": "65123458X",
            "mare_nsire": "7413214Y",
            "mare_name": "Marie-Jeanne",
            "mare_breed": "Arabe",
            "message": "Yo",
            "cover_type": "lib",
            "provided_cover_place": ""
        }
        response = client.post('/covers/cover', json=body, headers=headers)
        self.assertEqual(response.status_code, 200)
        temp_cover_id = str(fake_db.covers.find_one({"mare_name": "Marie-Jeanne"})["_id"])

        response = client.put(f'/covers/cover/{temp_cover_id}', json={"arrival_date": "30/03/2024"}, headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        response = client.get(f'/covers/cover/{temp_cover_id}', headers=owner_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["arrival_date"], "30/03/2024")

        fake_db.covers.delete_one({"_id": ObjectId(temp_cover_id)})

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

        # mocking contract building method not to actually build and send contract
        with patch('src.api.contracts.utils.create_and_send_contract', new_callable=AsyncMock) as mock:
            mock.return_value=({
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

            # wrong cover id
            response = client.get(f'/contracts/sign-page-url/{wrong_cover_id}', headers=headers)
            self.assertEqual(response.status_code, 404)

            # when a user not involved in the cover tries to sign
            response = client.get(f'/contracts/sign-page-url/{cover_id}', headers=other_user_headers)
            self.assertEqual(response.status_code, 403)

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

        # test contracts building

        # put contracts identity for seller
        body = {
            "type": "company",
            "gender": "Monsieur",
            "postal_address": "Whatever 2",
            "birthdate": "28/10/1998",
            "birthplace": "Là",
            "citizenship": "Fr eheh",
            "company_name": "la boite",
            "company_status": "a status",
            "capital": 18.75,
            "head_office_address": "par là",
            "siret": "AYIHBYIUN"
            
        }
        response = client.put('/auth/contracts-identity', headers=owner_headers, json=body)
        self.assertEqual(response.status_code, 200)

        body = {
            "type": "individual",
            "gender": "Monsieur",
            "postal_address": "Whatever 1",
            "birthdate": "29/10/1998",
            "birthplace": "Ici",
            "citizenship": "fr"
        }
        response = client.put('/auth/contracts-identity', headers=headers, json=body)
        self.assertEqual(response.status_code, 200)

        buyer_in_db = fake_db.users.find_one({"email": "lrdeservice2@gmail.com"})
        seller_in_db = fake_db.users.find_one({"email": "lrdeservice@gmail.com"})

        with aioresponses() as m:
            m.post('thisisanurl?token=osef', payload={"message": "success"})

            _, sent_body = await contracts_utils.create_and_send_contract(
                "this-is-a-template-id",
                cover_in_db,
                buyer_in_db,
                seller_in_db,
                True,
                168,
                "embedded",
                "email",
                ["sms"],
                "thisismyfrontendurl",
                "thisisanurl",
                "osef"
            )

        placeholders = {}
        for elt in sent_body["placeholder_fields"]:
            placeholders[elt["api_key"]] = elt["value"]
        
        self.assertEqual(placeholders["down_payment"], pricing_utils.calculate_advance(cover_in_db["subtotal"], cover_in_db["cover_specs"]["advance_percentage"], True) \
            + math.ceil(1.2 * pricing_utils.calculate_advance(cover_in_db["buyer_fees_ht"], cover_in_db["cover_specs"]["advance_percentage"], False)))
        self.assertEqual(placeholders["last_payment"], pricing_utils.calculate_balance(cover_in_db["subtotal"], cover_in_db["cover_specs"]["advance_percentage"], True) \
            + math.ceil(1.2 * pricing_utils.calculate_balance(cover_in_db["buyer_fees_ht"], cover_in_db["cover_specs"]["advance_percentage"], False)))

        # testing webhooks

        # with a wrong secret-token
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "data": {
                    "contract": {
                        "id": "the_contract_id"
                    },
                    "signer": {
                        "signing_order": "1"
                    }
                }
            },
            headers={"Authorization": "Bearer nope"})
        self.assertEqual(response.status_code, 401)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "signingstarted")

        # with wrong contract id
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "data": {
                    "contract": {
                        "id": "nope"
                    },
                    "signer": {
                        "signing_order": "1"
                    }
                }
            },
            headers={"Authorization": f"Bearer {(base64.b64encode((contracts_config['secret-token'] + ':').encode('utf-8'))).decode('utf-8')}"})
        self.assertEqual(response.status_code, 500)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "signingstarted")

        # with a status that is not "signer-signed"
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "wtf",
                "data": {
                    "contract": {
                        "id": "the_contract_id"
                    },
                    "signer": {
                        "signing_order": "1"
                    }
                }
            },
            headers={"Authorization": f"Bearer {(base64.b64encode((contracts_config['secret-token'] + ':').encode('utf-8'))).decode('utf-8')}"})
        self.assertEqual(response.status_code, 200)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "signingstarted")

        # when ok
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "data": {
                    "contract": {
                        "id": "the_contract_id"
                    },
                    "signer": {
                        "signing_order": "1"
                    }
                }
            },
            headers={"Authorization": f"Bearer {(base64.b64encode((contracts_config['secret-token'] + ':').encode('utf-8'))).decode('utf-8')}"})
        self.assertEqual(response.status_code, 200)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "buyersigned")

        # check that cover is not forwarded twice if twice the same webhook is received
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "data": {
                    "contract": {
                        "id": "the_contract_id"
                    },
                    "signer": {
                        "signing_order": "1"
                    }
                }
            },
            headers={"Authorization": f"Bearer {(base64.b64encode((contracts_config['secret-token'] + ':').encode('utf-8'))).decode('utf-8')}"})
        self.assertEqual(response.status_code, 200)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "buyersigned")

        # check that checkout cannot be get because the contract is not sellersigned
        response = client.get(f'/pricing/checkout/{cover_id}', headers=headers)
        self.assertEqual(response.status_code, 403)

        # check that cover is indeed forwarded when its signing_order == "2"
        response = client.post(
            '/contracts/esignatures-webhook',
            json={
                "status": "signer-signed",
                "data": {
                    "contract": {
                        "id": "the_contract_id"
                    },
                    "signer": {
                        "signing_order": "2"
                    }
                }
            },
            headers={"Authorization": f"Bearer {(base64.b64encode((contracts_config['secret-token'] + ':').encode('utf-8'))).decode('utf-8')}"})
        self.assertEqual(response.status_code, 200)
        cover_in_db = fake_db.covers.find_one({"_id": ObjectId(cover_id)})
        self.assertEqual(cover_in_db["status"], "sellersigned")

        # checkout tests
        # when the cover id is not readable
        response = client.get('/pricing/checkout/oungabounga', headers=headers)
        self.assertEqual(response.status_code, 422)

        # when the cover id is wrong
        response = client.get(f'/pricing/checkout/{wrong_cover_id}', headers=headers)
        self.assertEqual(response.status_code, 404)

        # when the access token is not the buyers one
        response = client.get(f'/pricing/checkout/{cover_id}', headers=owner_headers)
        self.assertEqual(response.status_code, 403)

        # when ok
        response = client.get(f'/pricing/checkout/{cover_id}', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["subtotal"], 300)
        self.assertEqual(response.json()["service_fees"], 22)
        self.assertEqual(response.json()["total"], 322)
        self.assertEqual(response.json()["status"], "sellersigned")

        # to be changed in the future
        response = client.post(f'/covers/step-forward-payment/{cover_id}')
        self.assertEqual(response.status_code, 200)

        # balance checkout
        response = client.get(f'/pricing/checkout/{cover_id}', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["subtotal"], 450)
        self.assertEqual(response.json()["service_fees"], 33)
        self.assertEqual(response.json()["total"], 483)
        self.assertEqual(response.json()["status"], "downpaid")

    def tearDown(self):
        self.vf.close()
        self.ph.close()

if __name__ == '__main__':
    os.chdir('../bin')
    unittest.main()
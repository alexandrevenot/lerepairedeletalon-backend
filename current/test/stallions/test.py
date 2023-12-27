import unittest
import os
import sys
import datetime

from fastapi import FastAPI
from bson.objectid import ObjectId
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from context import fake_db, get_db, get_db_client

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../bin/')))

import app.auth.router as auth_router
import app.stallions.router as stallions_router
import app.stallions.utils as stallions_utils
import app.pricing.utils as pricing_utils

config = stallions_utils.load_config()

server = FastAPI()

server.dependency_overrides[auth_router.get_db] = get_db
server.dependency_overrides[stallions_router.get_db] = get_db

server.dependency_overrides[auth_router.get_db_client] = get_db_client
server.dependency_overrides[stallions_router.get_db_client] = get_db_client

server.include_router(auth_router.router)
server.include_router(stallions_router.router)

client = TestClient(server)

class StallionsTest(unittest.TestCase):
    def test(self):
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

        headers = {"Authorization": f"Bearer {access_token}"}

        body = {}

        body["final_fields_body"] = {
            "name": "Michel du Rouet",
            "breed": "Selle Français",
            "n_sire": "8461684685X",
            "birthdate": "28/10/1998"
        }

        body["editable_fields_body"] = {
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
                "iai": {
                    "price": 750,
                    "balance_payment_condition": "living_foal_48",
                    "advance_percentage": 50,
                    "cover_place": "ici",
                    "maximum_nb_of_attempts": 3,
                    "hosting_specs": {
                        "meadow": {
                            "price": 6
                        }
                    }
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

        response = client.post('/stallions/stallion', json=body, headers=headers)

        self.assertEqual(response.status_code, 200)

        stallion_id = response.json()["stallion_id"]

        self.vf = open('/lerepairedeletalon/server/current/test/stallions/verification_file.png', 'rb')
        self.ph = open('/lerepairedeletalon/server/current/test/stallions/sellefrançais.jpg', 'rb')

        files = (
            ("verification_file", ("verification_file.png", self.vf, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg"))
        )

        response = client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.get('/stallions/my-stallions', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(str(response.json()["content"][0]["id"]), stallion_id)
        self.assertEqual(str(response.json()["content"][0]["name"]), "Michel du Rouet")
        self.assertEqual(str(response.json()["content"][0]["breed"]), "Selle Français")
        stallion_in_db = fake_db.stallions.find_one({"_id": ObjectId(stallion_id)})
        self.assertEqual(str(response.json()["content"][0]["photo_id"]), str(stallion_in_db["thumbnail_photo"]))
        self.assertEqual(response.json()["content"][0]["profile_status"], "to_be_validated")
        self.assertEqual(len(response.json()["content"][0].keys()), 6)

        fake_db.stallions.update_one({"_id": ObjectId(stallion_id)}, {"$set": {"profile_status": "visible"}})

        response = client.get(f'/stallions/stallion/{stallion_id}?mode=profile', headers=headers)
        self.assertEqual(response.status_code, 200)
        content = response.json()

        owner_id = str(fake_db.users.find_one({"email": "lrdeservice@gmail.com"})["_id"])
        self.assertEqual(content["owner"], owner_id)
        self.assertEqual(content["name"], "Michel du Rouet")
        self.assertEqual(content["breed"], "Selle Français")
        self.assertEqual(content["n_sire"], "8461684685X")
        self.assertEqual(content["age"], stallions_utils.calculate_age(datetime.datetime.strptime("28/10/1998","%d/%m/%Y")))
        self.assertEqual(content["main_desc"], "desc")
        self.assertEqual(content["color"], "Bai tâcheté")
        self.assertEqual(content["height"], 170.5)
        self.assertEqual(content["city"], "Toulouse")
        self.assertEqual(content["dep_name"], "Haute-Garonne")
        self.assertEqual(content["reg_name"], "Occitanie")
        self.assertEqual(content["production_breeds"], ["Selle Français"])
        self.assertEqual(content["cover_specs"]["iai"]["price"], 750)
        self.assertEqual(content["cover_specs"]["iai"]["balance_payment_condition"], "living_foal_48")
        self.assertEqual(content["cover_specs"]["iai"]["advance_percentage"], 50)
        self.assertEqual(content["cover_specs"]["iai"]["cover_place"], "ici")
        self.assertEqual(content["cover_specs"]["iai"]["maximum_nb_of_attempts"], 3)
        self.assertEqual(content["cover_specs"]["iai"]["hosting_specs"]["meadow"]["price"], 6)
        self.assertEqual(content["pedigree"], ['Popa'] + ['']*13)
        self.assertEqual(content["pedigree_po"], "pedigree po")
        self.assertEqual(content["cover_additional_info"], "cover additional info")
        self.assertEqual(content["performance"], "perf")
        self.assertEqual(content["stallion_additional_info"], "stallion additional info")
        self.assertEqual(content["offspring"], "the offspring")
        self.assertEqual(content["crossbreeding_advice"], "que des juments cools")
        self.assertEqual(content["stallion_std_negative_tests"]["metrite"]['test_date'], "08/10/2023")
        self.assertEqual(content["stallion_std_negative_tests"]["arterite"]['test_date'], "08/10/2023")
        self.assertEqual(content["stallion_vaccines"], [
                "rhino"
            ])


        body = {
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
                "iai": {
                    "price": 780,
                    "balance_payment_condition": "living_foal",
                    "advance_percentage": 40,
                    "cover_place": "là",
                    "maximum_nb_of_attempts": 4,
                    "hosting_specs": {
                        "meadow": {
                            "price": 7
                        }
                    }
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

        response = client.put(f'/stallions/stallion/{stallion_id}', json=body, headers=headers)
        self.assertEqual(response.status_code, 200)

        files = (
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg"))
        )

        response = client.put(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)

        nb_of_photos_in_db = len([_ for _ in fake_db.stallion_photos.find()])
        self.assertEqual(nb_of_photos_in_db, 3)

        response = client.get(f'/stallions/stallion/{stallion_id}?mode=profile', headers=headers)
        self.assertEqual(response.status_code, 200)
        content = response.json()

        owner_id = str(fake_db.users.find_one({"email": "lrdeservice@gmail.com"})["_id"])
        self.assertEqual(content["owner"], owner_id)
        self.assertEqual(content["name"], "Michel du Rouet")
        self.assertEqual(content["breed"], "Selle Français")
        self.assertEqual(content["n_sire"], "8461684685X")
        self.assertEqual(content["age"], stallions_utils.calculate_age(datetime.datetime.strptime("28/10/1998","%d/%m/%Y")))
        self.assertEqual(content["main_desc"], "other desc")
        self.assertEqual(content["color"], "Bai plus tâcheté")
        self.assertEqual(content["height"], 171)
        self.assertEqual(content["city"], "Rodez")
        self.assertEqual(content["dep_name"], "Aveyron")
        self.assertEqual(content["reg_name"], "Occitanie")
        self.assertEqual(content["production_breeds"], ["Selle Français", "Boulonnais"])
        self.assertEqual(content["cover_specs"]["iai"]["price"], 780)
        self.assertEqual(content["cover_specs"]["iai"]["balance_payment_condition"], "living_foal")
        self.assertEqual(content["cover_specs"]["iai"]["advance_percentage"], 40)
        self.assertEqual(content["cover_specs"]["iai"]["maximum_nb_of_attempts"], 4)
        self.assertEqual(content["cover_specs"]["iai"]["cover_place"], "là")
        self.assertEqual(content["cover_specs"]["iai"]["hosting_specs"]["meadow"]["price"], 7)
        self.assertEqual(content["pedigree"], ['Popa', 'Moman'] + ['']*12)
        self.assertEqual(content["pedigree_po"], "other pedigree po")
        self.assertEqual(content["cover_additional_info"], "other cover additional info")
        self.assertEqual(content["performance"], "other perf")
        self.assertEqual(content["stallion_additional_info"], "other stallion additional info")
        self.assertEqual(content["offspring"], "other the offspring")
        self.assertEqual(content["crossbreeding_advice"], "other que des juments cools")
        self.assertEqual(content["stallion_std_negative_tests"]["metrite"]["test_date"], "08/10/2023")
        self.assertEqual(content["stallion_std_negative_tests"]["arterite"]["test_date"], "08/10/2023")
        self.assertEqual(content["stallion_std_negative_tests"]["anemie"]["test_date"], "08/10/2023")
        self.assertEqual(content["stallion_vaccines"], [
                "rhino",
                "grippe"
            ])

        response = client.delete(f'/stallions/stallion/{stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(0, len([_ for _ in fake_db.stallions.find()]))
        self.assertEqual(0, len([_ for _ in fake_db.stallion_photos.find()]))
        self.assertEqual(0, len([_ for _ in fake_db.verification_files.find()]))

        # test invalid bodies for post stallion

        body = {}

        body["final_fields_body"] = {
            "name": "Michel du Rouet",
            "breed": "Selle Français",
            "n_sire": "8461684685X",
            "birthdate": "2810/1998"
        }

        body["editable_fields_body"] = {
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
                "iai": {
                    "price": 750,
                    "balance_payment_condition": "living_foal_48",
                    "advance_percentage": 50,
                    "cover_place": "ici",
                    "maximum_nb_of_attempts": 3,
                    "hosting_specs": {
                        "meadow": {
                            "price": 6
                        }
                    }
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
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        # production breeds duplicated
        body["final_fields_body"]["birthdate"] = "28/10/1998"
        body["editable_fields_body"]["production_breeds"] = ["Selle Français", "Selle Français"]
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        # cover_specs
        body["editable_fields_body"]["production_breeds"] = ["Selle Français"]
        body["editable_fields_body"]["cover_specs"]["iai"] = {
            "price": 750,
            "balance_payment_condition": "living_foal_485",
            "advance_percentage": 50,
            "cover_place": "ici",
            "maximum_nb_of_attempts": 3,
            "hosting_specs": {
                "meadow": {
                    "price": 6
                }
            }
        }
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        # cover_specs
        body["editable_fields_body"]["cover_specs"]["iai"] = {
            "price": 750,
            "balance_payment_condition": "living_foal_48",
            "advance_percentage": 52,
            "cover_place": "ici",
            "maximum_nb_of_attempts": 3,
            "hosting_specs": {
                "meadow": {
                    "price": 6
                }
            }
        }
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        # cover_specs
        body["editable_fields_body"]["cover_specs"]["iai"] = {
            "price": 750,
            "balance_payment_condition": "living_foal_48",
            "advance_percentage": 50,
            "cover_place": "ici",
            "maximum_nb_of_attempts": -1,
            "hosting_specs": {
                "meadow": {
                    "price": 6
                }
            }
        }
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        # cover_specs
        body["editable_fields_body"]["cover_specs"]["iai"] = {
            "price": 750,
            "balance_payment_condition": "living_foal_48",
            "advance_percentage": 50,
            "cover_place": "ici",
            "maximum_nb_of_attempts": 3,
            "hosting_specs": {
                "meadow": False,
            }
        }
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        # cover_specs
        body["editable_fields_body"]["cover_specs"] = {}
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        # pedigree
        body["editable_fields_body"]["cover_specs"]["iai"] = {
            "price": 750,
            "balance_payment_condition": "living_foal_48",
            "advance_percentage": 50,
            "cover_place": "ici",
            "maximum_nb_of_attempts": 3,
            "hosting_specs": {
                "meadow": {
                    "price": 6
                }
            }
        }
        body["editable_fields_body"]["pedigree"] = [""] * 15
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        body["editable_fields_body"]["pedigree"] = ["Popa"]
        body["editable_fields_body"]["stallion_std_negative_tests"] = ["not a disease"]
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        body["editable_fields_body"]["stallion_std_negative_tests"] = {
            "anemie": {
                "test_date": "08/10/2023"
            }
        }
        body["editable_fields_body"]["stallion_vaccines"] = ["covid15"]
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 422)

        # put stallion in db to test next routes 422
        body["editable_fields_body"]["stallion_vaccines"] = ["grippe"]
        response = client.post('/stallions/stallion', json=body, headers=headers)
        stallion_id = response.json()["stallion_id"]
        self.assertEqual(response.status_code, 200)

        self.phtl = open('/lerepairedeletalon/server/current/test/stallions/photo_too_large.jpg', 'rb')
        self.vftl = open('/lerepairedeletalon/server/current/test/stallions/verification_file_too_large.pdf', 'rb')

        files = (
            ("verification_file", ("verification_file.png", self.vftl, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg"))
        )
        response = client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)
    
        files = (
            ("verification_file", ("verification_file.png", self.vf, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.phtl, "image/jpg"))
        )
        response = client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # register another user
        response = client.post('/auth/register', json={
            "firstname": "Joris",
            "lastname": "Lagraphe",
            "email": "lrdeservice2@gmail.com",
            "phone_number": "+33665824651",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)

        # login to get access token
        response = client.post('/auth/login', json={
            "email": "lrdeservice2@gmail.com",
            "password": "acjiodfehy"
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue("accessToken" in response.json())
        access_token = response.json()["accessToken"]

        other_headers = {"Authorization": f"Bearer {access_token}"}

        files = (
            ("verification_file", ("verification_file.png", self.vf, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg"))
        )

        response = client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=other_headers)
        self.assertEqual(response.status_code, 403)

        response = client.post('/stallions/stallion-files/651bd0779fdb7d78aecf9ef3', files=files, headers=headers)
        self.assertEqual(response.status_code, 404)

        response = client.post('/stallions/stallion-files/651bd0779fdb7d78aec', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        response = client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.post(f'/stallions/stallion-files/{stallion_id}', files=files, headers=headers)
        self.assertEqual(response.status_code, 403)

        response = client.put(f'/stallions/stallion/{stallion_id}', json=body["editable_fields_body"], headers=other_headers)
        self.assertEqual(response.status_code, 403)

        files = (
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg"))
        )

        response = client.put(f'/stallions/stallion-files/{stallion_id}', files=files, headers=other_headers)
        self.assertEqual(response.status_code, 403)

        response = client.delete(f"/stallions/stallion/{stallion_id}", headers=headers)
        self.assertEqual(response.status_code, 200)

        # add stallions for search
        body = {}

        body["final_fields_body"] = {
            "name": "Joris",
            "breed": "Arabe",
            "n_sire": "65234871X",
            "birthdate": "28/10/1998"
        }

        body["editable_fields_body"] = {
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
                "iai": {
                    "price": 750,
                    "balance_payment_condition": "living_foal_48",
                    "advance_percentage": 50,
                    "cover_place": "ici",
                    "maximum_nb_of_attempts": 3,
                    "hosting_specs": {
                        "meadow": {
                            "price": 6
                        }
                    }
                },
                "iac": {
                    "price": 1278,
                    "balance_payment_condition": "living_foal_48",
                    "advance_percentage": 50,
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
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 200)
        joris_id = response.json()["stallion_id"]
        files = (
            ("verification_file", ("verification_file.png", self.vf, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg"))
        )
        response = client.post(f'/stallions/stallion-files/{joris_id}', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)

        body = {}

        body["final_fields_body"] = {
            "name": "Bertrand",
            "breed": "Fjord",
            "n_sire": "74566523X",
            "birthdate": "28/10/1998"
        }

        body["editable_fields_body"] = {
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
        response = client.post('/stallions/stallion', json=body, headers=headers)
        self.assertEqual(response.status_code, 200)
        bertrand_id = response.json()["stallion_id"]
        response = client.post(f'/stallions/stallion-files/{bertrand_id}', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)

        fake_db.stallions.update_many({},{"$set": {"profile_status": "visible"}})

        response = client.put(f'/stallions/stallion-profile-status/{bertrand_id}?new_status=hidden', headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.put(f'/stallions/stallion-profile-status/{bertrand_id}?new_status=wtf', headers=headers)
        self.assertEqual(response.status_code, 403)

        response = client.put(f'/stallions/stallion-profile-status/{bertrand_id}?new_status=visible')
        self.assertEqual(response.status_code, 401)

        response = client.put(f'/stallions/stallion-profile-status/{bertrand_id}?new_status=visible', headers=other_headers)
        self.assertEqual(response.status_code, 403)

        response = client.put(f'/stallions/stallion-profile-status/{bertrand_id}?new_status=visible', headers=headers)
        self.assertEqual(response.status_code, 200)

        # with page <= 0
        response = client.get('/stallions/search?page=0&limit=16')
        self.assertEqual(response.status_code, 422)

        # basic use for no filter
        response = client.get('/stallions/search?page=1&limit=16')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(content_sorted_on_name[0]["name"], "Bertrand")
        self.assertEqual(content_sorted_on_name[1]["name"], "Joris")

        # prices

        # testing 422
        response = client.get('/stallions/search?page=1&limit=16&min_price=bonjour')
        self.assertEqual(response.status_code, 422)

        response = client.get('/stallions/search?page=1&limit=16&max_price=bonjour')
        self.assertEqual(response.status_code, 422)

        response = client.get('/stallions/search?page=1&limit=16&max_price=bonjour&min_price=580')
        self.assertEqual(response.status_code, 422)

        # (0) 425+f (1) 570+f (2) 750+f (3) 1278+f (4)

        pricing_config = pricing_utils.load_config()

        # (0) min
        response = client.get('/stallions/search?page=1&limit=16&min_price=2')
        self.assertEqual(response.status_code, 200)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 2)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_utils.calculate_fees_ht(
            425,
            pricing_config['buyer_fees_coeff'],
            pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(
            750,
            pricing_config['buyer_fees_coeff'],
            pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # (0) max
        response = client.get('/stallions/search?page=1&limit=16&max_price=2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 0)

        # (1) min
        response = client.get('/stallions/search?page=1&limit=16&min_price=430')
        self.assertEqual(response.status_code, 200)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 2)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_utils.calculate_fees_ht(425, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(750, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # (1) max
        response = client.get('/stallions/search?page=1&limit=16&max_price=568')
        self.assertEqual(response.status_code, 200)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 1)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_utils.calculate_fees_ht(425, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # (2) min
        response = client.get('/stallions/search?page=1&limit=16&min_price=580')
        self.assertEqual(response.status_code, 200)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 2)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(570, pricing_utils.calculate_fees_ht(570, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(750, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # (2) max
        response = client.get('/stallions/search?page=1&limit=16&max_price=740')
        self.assertEqual(response.status_code, 200)

        pricing_config = pricing_utils.load_config()
        self.assertEqual(len(response.json()["content"]), 1)

        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(425, pricing_utils.calculate_fees_ht(425, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # (3) min
        response = client.get('/stallions/search?page=1&limit=16&min_price=1277')
        self.assertEqual(response.status_code, 200)

        pricing_config = pricing_utils.load_config()
        self.assertEqual(len(response.json()["content"]), 1)

        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(1278, pricing_utils.calculate_fees_ht(1278, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # (3) max
        response = client.get('/stallions/search?page=1&limit=16&max_price=1277')
        self.assertEqual(response.status_code, 200)

        pricing_config = pricing_utils.load_config()
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_utils.calculate_fees_ht(425, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(750, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # (4) min
        response = client.get('/stallions/search?page=1&limit=16&min_price=8500')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 0)

        # (4) max
        response = client.get('/stallions/search?page=1&limit=16&max_price=8500')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_utils.calculate_fees_ht(425, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(750, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # when min > max
        response = client.get('/stallions/search?page=1&limit=16&min_price=1230&max_price=1177')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 0)

        # mix min and max
        response = client.get('/stallions/search?page=1&limit=16&min_price=560&max_price=1277')
        self.assertEqual(response.status_code, 200)

        pricing_config = pricing_utils.load_config()
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(570, pricing_utils.calculate_fees_ht(570, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(750, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # when min height too high
        response = client.get('/stallions/search?page=1&limit=16&min_height=180')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 0)

        # only one height matches
        response = client.get('/stallions/search?page=1&limit=16&min_height=160&max_height=175')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Joris")

        # two heights match
        response = client.get('/stallions/search?page=1&limit=16&min_height=160&max_height=182')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)

        # both breeds
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 2)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_utils.calculate_fees_ht(425, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(750, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # one breed
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Bertrand")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(425, pricing_utils.calculate_fees_ht(425, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        response = client.get('/stallions/search?page=1&limit=16&breeds=Arabe')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Joris")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(750, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # among other breeds
        response = client.get('/stallions/search?page=1&limit=16&breeds=Arabe&breeds=Welsh')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Joris")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(750, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # breed and price
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 2)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(570, pricing_utils.calculate_fees_ht(570, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(750, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # production breeds
        response = client.get('/stallions/search?page=1&limit=16&production_breeds=Fjord&production_breeds=Boulonnais')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)

        # many production breeds but only one stallion having one of them
        response = client.get('/stallions/search?page=1&limit=16&production_breeds=Fjord&production_breeds=Trakehner')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Bertrand")

        # many production breeds but 0 stallion having one of them
        response = client.get('/stallions/search?page=1&limit=16&production_breeds=Percheron&production_breeds=Trakehner')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 0)

        # price, breed and production_breeds
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(570, pricing_utils.calculate_fees_ht(570, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # cover_type
        response = client.get('/stallions/search?page=1&limit=16&cover_types=hand&cover_types=iart')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Bertrand")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(570, pricing_utils.calculate_fees_ht(570, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # testing 422 cover types
        response = client.get('/stallions/search?page=1&limit=16&cover_types=doesnotexist')
        self.assertEqual(response.status_code, 422)

        response = client.get('/stallions/search?page=1&limit=16&cover_types=bonjour&cover_types=lib')
        self.assertEqual(response.status_code, 422)

        # price, breed, production_breeds and cover_types with 0 result bcs the price of the cover type asked is too high
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner&cover_types=lib')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 0)

        # price, breed, production_breeds and cover_types
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=100&production_breeds=Fjord&production_breeds=Trakehner&cover_types=hand')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(570, pricing_utils.calculate_fees_ht(570, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT'], pricing_config['TVA_cover_coeff_HT']).total)

        # testing 422 when price, breed, production_breeds and cover_types
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner&cover_types=hand&cover_types=doesnotexist')
        self.assertEqual(response.status_code, 422)

        # distance
        lat_balma = 43.611222
        lng_balma = 1.505792

        # incomplete distance parameters
        response = client.get(f'/stallions/search?page=1&limit=16&lat={lat_balma}&lng={lng_balma}')
        self.assertEqual(response.status_code, 422)

        response = client.get(f'/stallions/search?page=1&limit=16&lat={lat_balma}&distance=1')
        self.assertEqual(response.status_code, 422)

        response = client.get(f'/stallions/search?page=1&limit=16&lng={lng_balma}&distance=1')
        self.assertEqual(response.status_code, 422)

        #
        #  NotImplementedError: '$geoWithin' is a valid operation but it is not supported by Mongomock yet.
        # 
        # # complete distance parameters but too far
        # response = client.get(f'/stallions/search?page=1&limit=16&lat={lat_balma}&lng={lng_balma}&distance=0.5')
        # self.assertEqual(response.status_code, 200)
        # self.assertEqual(len(response.json()["content"]), 0)

        # # complete distance parameters, 1 result
        # response = client.get(f'/stallions/search?page=1&limit=16&lat={lat_balma}&lng={lng_balma}&distance=10')
        # self.assertEqual(response.status_code, 200)
        # self.assertEqual(len(response.json()["content"]), 1)
        # self.assertEqual(response.json()["content"]["name"], "Joris")

        # # complete distance parameters, 2 results
        # response = client.get(f'/stallions/search?page=1&limit=16&lat={lat_balma}&lng={lng_balma}&distance=300')
        # self.assertEqual(response.status_code, 200)
        # self.assertEqual(len(response.json()["content"]), 2)
        # content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        # self.assertEqual(len(content_sorted_on_name), 2)
        # self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_utils.calculate_fees_ht(425, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT']).total)
        # self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_utils.calculate_fees_ht(750, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset']), pricing_config['TVA_coeff_HT']).total)

        # different pages and limits
        response = client.get('/stallions/search?page=2&limit=16')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 0)

        response = client.get('/stallions/search?page=1&limit=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)

        response = client.get('/stallions/search?page=2&limit=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)

        response = client.get('/stallions/search?page=2&limit=100000')
        self.assertEqual(response.status_code, 422)

        response = client.get('/stallions/search?page=2&limit=-100000')
        self.assertEqual(response.status_code, 422)

        # favorites
        stallions_it = fake_db.stallions.find()
        ids = [str(stallion["_id"]) for stallion in stallions_it]
        first_stallion_id = ids[0]
        second_stallion_id = ids[1]

        response = client.get('/stallions/favorites', headers=headers)
        self.assertEqual(response.json()["favorite_stallions"], [])

        response = client.delete(f'/stallions/favorites/{first_stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 422)

        response = client.get('/stallions/favorites', headers=headers)
        self.assertEqual(response.json()["favorite_stallions"], [])

        response = client.post(f'/stallions/favorites/{first_stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.get('/stallions/favorites', headers=headers)
        self.assertEqual(response.json()["favorite_stallions"], [first_stallion_id])

        # when already in list
        response = client.post(f'/stallions/favorites/{first_stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 422)

        response = client.get('/stallions/favorites', headers=headers)
        self.assertEqual(response.json()["favorite_stallions"], [first_stallion_id])

        response = client.delete(f'/stallions/favorites/{first_stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.get('/stallions/favorites', headers=headers)
        self.assertEqual(response.json()["favorite_stallions"], [])

        # putting both stallions
        response = client.post(f'/stallions/favorites/{first_stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.post(f'/stallions/favorites/{second_stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.get('/stallions/favorites', headers=headers)
        self.assertEqual(response.json()["favorite_stallions"], ids)

        response = client.delete(f'/stallions/favorites/{second_stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.get('/stallions/favorites', headers=headers)
        self.assertEqual(response.json()["favorite_stallions"], [first_stallion_id])

    def tearDown(self):
        self.vf.close()
        self.ph.close()
        self.vftl.close()
        self.phtl.close()


if __name__ == '__main__':
    os.chdir('../bin')
    unittest.main()
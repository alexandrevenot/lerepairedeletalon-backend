import unittest
import os
import sys

from fastapi import FastAPI
from bson.objectid import ObjectId

import mongomock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../bin/')))

import src.api.auth.router as auth_router
import src.api.stallions.router as stallions_router
import src.api.pricing.utils as pricing_utils

fake_client = mongomock.MongoClient()
fake_db = fake_client.main

server = FastAPI()

server.dependency_overrides[auth_router.get_db] = lambda: fake_db
server.dependency_overrides[stallions_router.get_db] = lambda: fake_db

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

        # without token
        response = client.post('/stallions/register-new-stallion')
        self.assertEqual(response.status_code, 401)

        # with uncomplete data
        response = client.post('/stallions/register-new-stallion', headers=headers)
        self.assertEqual(response.status_code, 422)

        self.cs = open('/lerepairedeletalon/server/current/test/stallions/carnetdesaillie.png', 'rb')
        self.ph = open('/lerepairedeletalon/server/current/test/stallions/sellefrançais.jpg', 'rb')
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.7")),
            ("lng", (None, "0.1")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )

        # complete data
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        stallion_in_db = fake_db.stallions.find_one({"name": "Michel du Rouet"})
        self.assertTrue(stallion_in_db is not None)

        for field in [
            "c_saillies",
            "photos",
            "name",
            "breed",
            "n_sire",
            "main_desc",
            "color",
            "height",
            "birthdate",
            "location",
            "city",
            "postal_code",
            "production_breeds",
            "prices",
            "pedigree",
            "cover_additional_info",
            "performance",
            "pedigree_po",
            "stallion_additional_info",
            "offspring",
            "owner"
        ]:
            self.assertTrue(field in stallion_in_db)
        
        self.assertTrue(isinstance(stallion_in_db["owner"], ObjectId))
        self.assertEqual(str(stallion_in_db["owner"]), str(fake_db.users.find_one({"email": "lrdeservice@gmail.com"})["_id"]))

        self.assertEqual(stallion_in_db["prices"][0]["cover_type"], "iai")
        self.assertEqual(stallion_in_db["prices"][0]["cover_place"], "ici")
        self.assertEqual(stallion_in_db["prices"][0]["price"], 750)

        self.assertEqual(stallion_in_db["location"]["type"], "Point")
        self.assertEqual(stallion_in_db["location"]["coordinates"][0], 0.1)
        self.assertEqual(stallion_in_db["location"]["coordinates"][1], 0.7)

        self.assertFalse(stallion_in_db["searchable"])

        # already existing n_sire in db
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 400)
        fake_db.stallions.delete_one({"name": "Michel du Rouet"})

        # unavailable breed
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "???")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "0.0")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # height that cannot be read as float
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "???")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "0.0")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # unparsable birthdate
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "???")),
            ("lat", (None, "0.0")),
            ("lng", (None, "0.0")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # when lat is not a float
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "???")),
            ("lng", (None, "0.0")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # when lng is an int
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        fake_db.stallions.delete_one({"name": "Michel du Rouet"})

        # when one of the production breeds does not exist
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "???")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # when there are many production breeds
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        fake_db.stallions.delete_one({"name": "Michel du Rouet"})

        # when there are many production breeds but one of them does not exist
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "???")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # many times the same production breed
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # unexisting cover type
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'wtf')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # cover places, types and prices different lengths
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_types", (None, 'iac')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # consistent length in cover places, types and prices, but twice the same cover type
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '750')),
            ("prices", (None, '840')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # cover price when its not readable as int
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '0.0')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # empty pedigree
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '741')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        stallion_in_db = fake_db.stallions.find_one({"name": "Michel du Rouet"})
        self.assertEqual(stallion_in_db["pedigree"], [""] * 14)
        fake_db.stallions.delete_one({"name": "Michel du Rouet"})

        # not full pedigree
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '741')),
            ("pedigree", (None, 'Popa')),
            ("pedigree", (None, 'Moman')),
            ("pedigree", (None, 'Grand-Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        stallion_in_db = fake_db.stallions.find_one({"name": "Michel du Rouet"})
        self.assertEqual(stallion_in_db["pedigree"], ["Popa", "Moman", "Grand-Popa"] + ["" for _ in range(11)])
        fake_db.stallions.delete_one({"name": "Michel du Rouet"})

        # not full pedigree with spaces
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '741')),
            ("pedigree", (None, 'Popa')),
            ("pedigree", (None, '')),
            ("pedigree", (None, 'Grand-Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        stallion_in_db = fake_db.stallions.find_one({"name": "Michel du Rouet"})
        self.assertEqual(stallion_in_db["pedigree"], ["Popa", "", "Grand-Popa"] + ["" for _ in range(11)])
        fake_db.stallions.delete_one({"name": "Michel du Rouet"})

        # full pedigree
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '741')),
            ("pedigree", (None, 'Popa')),
            ("pedigree", (None, 'Moman')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        stallion_in_db = fake_db.stallions.find_one({"name": "Michel du Rouet"})
        self.assertEqual(stallion_in_db["pedigree"], ["Popa", "Moman"] + ["Grand-Popa"]*12)
        fake_db.stallions.delete_one({"name": "Michel du Rouet"})

        # full pedigree
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '741')),
            ("pedigree", (None, 'Popa')),
            ("pedigree", (None, 'Moman')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'Grand-Popa')),
            ("pedigree", (None, 'La goutte de trop')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # with empty optionnal fields
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '741'))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        fake_db.stallions.delete_one({"name": "Michel du Rouet"})

        # with a c_saillies that is too large
        self.cstl = open('/lerepairedeletalon/server/current/test/stallions/c_saillies_too_large.pdf', 'rb')
        files = (
            ("c_saillies", ("c_saillies.png", self.cstl, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '741'))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # with a photo that is too large
        self.phtl = open('/lerepairedeletalon/server/current/test/stallions/photo_too_large.jpg', 'rb')
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("photos", ("photo3.jpg", self.phtl, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.0")),
            ("lng", (None, "7")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("production_breeds", (None, "Camargue")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '741'))
        )
        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 422)

        # add a stallion for the other tests
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Michel du Rouet")),
            ("breed", (None, "Selle Français")),
            ("n_sire", (None, "65123458X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.7")),
            ("lng", (None, "0.1")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )

        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        stallion_in_db = fake_db.stallions.find_one({"name": "Michel du Rouet"})

        # testing my-stallions
        response = client.get('/stallions/my-stallions', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(str(response.json()["content"][0]["id"]), str(stallion_in_db["_id"]))
        self.assertEqual(str(response.json()["content"][0]["name"]), "Michel du Rouet")
        self.assertEqual(str(response.json()["content"][0]["breed"]), "Selle Français")
        self.assertEqual(str(response.json()["content"][0]["photoId"]), str(stallion_in_db["photos"][0]))
        self.assertFalse(response.json()["content"][0]["searchable"])
        self.assertEqual(len(response.json()["content"][0].keys()), 5)

        # adding a second stallion
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Joris")),
            ("breed", (None, "Boulonnais")),
            ("n_sire", (None, "65234871X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "0.7")),
            ("lng", (None, "0.1")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Selle Français")),
            ("cover_types", (None, 'iai')),
            ("cover_places", (None, 'ici')),
            ("prices", (None, '750')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )

        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        second_stallion_in_db = fake_db.stallions.find_one({"name": "Joris"})

        response = client.get('/stallions/my-stallions', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)
        self.assertEqual(str(response.json()["content"][0]["id"]), str(stallion_in_db["_id"]))
        self.assertEqual(str(response.json()["content"][0]["name"]), "Michel du Rouet")
        self.assertEqual(str(response.json()["content"][0]["breed"]), "Selle Français")
        self.assertEqual(str(response.json()["content"][0]["photoId"]), str(stallion_in_db["photos"][0]))
        self.assertFalse(response.json()["content"][0]["searchable"])
        self.assertEqual(len(response.json()["content"][0].keys()), 5)
        self.assertEqual(str(response.json()["content"][1]["id"]), str(second_stallion_in_db["_id"]))
        self.assertEqual(str(response.json()["content"][1]["name"]), "Joris")
        self.assertEqual(str(response.json()["content"][1]["breed"]), "Boulonnais")
        self.assertEqual(str(response.json()["content"][1]["photoId"]), str(second_stallion_in_db["photos"][0]))
        self.assertFalse(response.json()["content"][1]["searchable"])
        self.assertEqual(len(response.json()["content"][1].keys()), 5)

        # testing stallion-profile-information
        first_stallion_id = str(stallion_in_db["_id"])
        second_stallion_id = str(second_stallion_in_db["_id"])

        response = client.get(f'/stallions/stallion-profile-information?stallion_id={first_stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 403)

        fake_db.stallions.update_many(
            {},
            {
                "$set": {
                    "searchable": True
                }
            }
        )
        response = client.get(f'/stallions/stallion-profile-information?stallion_id={first_stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        self.assertEqual(response.json()["stallionProfile"]["breed"], "Selle Français")
        self.assertEqual(response.json()["stallionProfile"]["name"], "Michel du Rouet")
        self.assertEqual(response.json()["stallionProfile"]["n_sire"], "65123458X")
        self.assertEqual(response.json()["stallionProfile"]["main_desc"], "desc")
        self.assertEqual(response.json()["stallionProfile"]["color"], "Bai")
        self.assertEqual(response.json()["stallionProfile"]["height"], 170)
        self.assertTrue(isinstance(response.json()["stallionProfile"]["height"], float))
        self.assertEqual(response.json()["stallionProfile"]["offspring"], "the offspring")
        self.assertEqual(response.json()["stallionProfile"]["performance"], "perf")
        self.assertEqual(response.json()["stallionProfile"]["pedigree"], ["Popa"] + 13*[""])
        self.assertEqual(response.json()["stallionProfile"]["pedigree_po"], "pedigree perfs offspring")
        self.assertEqual(response.json()["stallionProfile"]["stallion_additional_info"], "stallion additional info")
        self.assertEqual(response.json()["stallionProfile"]["cover_additional_info"], "cover additional info")
        self.assertEqual(response.json()["stallionProfile"]["city"], "Toulouse")
        self.assertEqual(response.json()["stallionProfile"]["postal_code"], "31000")
        self.assertEqual(response.json()["stallionProfile"]["dep_name"], "Haute-Garonne")
        self.assertEqual(response.json()["stallionProfile"]["reg_name"], "Occitanie")
        self.assertEqual(response.json()["stallionProfile"]["breed"], "Selle Français")
        self.assertEqual(response.json()["stallionProfile"]["production_breeds"], ["Selle Français"])
        self.assertEqual(response.json()["stallionProfile"]["breed"], "Selle Français")
        self.assertEqual(response.json()["stallionProfile"]["prices"][0]["cover_type"], "iai")
        self.assertEqual(response.json()["stallionProfile"]["prices"][0]["cover_place"], "ici")
        self.assertEqual(response.json()["stallionProfile"]["prices"][0]["price"], 750)
        self.assertEqual(response.json()["stallionProfile"]["location"]["type"], "Point")
        self.assertEqual(response.json()["stallionProfile"]["location"]["coordinates"], [0.1, 0.7])
        self.assertEqual(response.json()["stallionProfile"]["age"], 24)

        response = client.get(f'/stallions/stallion-profile-information?stallion_id={second_stallion_id}', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stallionProfile"]["breed"], "Boulonnais")

        # testing search feature
        fake_db.stallions.delete_many({})
        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Joris")),
            ("breed", (None, "Arabe")),
            ("n_sire", (None, "65234871X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Bai")),
            ("height", (None, "170")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "43.6")),
            ("lng", (None, "1.433333")),
            ("city", (None, "Toulouse")),
            ("postal_code", (None, "31000")),
            ("production_breeds", (None, "Arabe")),
            ("production_breeds", (None, "Boulonnais")),
            ("cover_types", (None, 'iai')),
            ("cover_types", (None, 'iac')),
            ("cover_places", (None, 'ici')),
            ("cover_places", (None, 'là')),
            ("prices", (None, '750')),
            ("prices", (None, '1278')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )

        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
        self.assertEqual(response.status_code, 200)

        files = (
            ("c_saillies", ("c_saillies.png", self.cs, "image/png")),
            ("photos", ("photo.jpg", self.ph, "image/jpg")),
            ("photos", ("photo2.jpg", self.ph, "image/jpg")),
            ("name", (None, "Bertrand")),
            ("breed", (None, "Fjord")),
            ("n_sire", (None, "74566523X")),
            ("main_desc", (None, "desc")),
            ("color", (None, "Blanc")),
            ("height", (None, "177")),
            ("birthdate", (None, "28/10/1998")),
            ("lat", (None, "44.841225")),
            ("lng", (None, "-0.5800364")),
            ("city", (None, "Bordeaux")),
            ("postal_code", (None, "33000")),
            ("production_breeds", (None, "Fjord")),
            ("cover_types", (None, 'lib')),
            ("cover_types", (None, 'hand')),
            ("cover_places", (None, 'ici2')),
            ("cover_places", (None, 'là2')),
            ("prices", (None, '425')),
            ("prices", (None, '570')),
            ("pedigree", (None, 'Popa')),
            ("cover_additional_info", (None, "cover additional info")),
            ("performance", (None, "perf")),
            ("pedigree_po", (None, "pedigree perfs offspring")),
            ("stallion_additional_info", (None, "stallion additional info")),
            ("offspring", (None, "the offspring"))
        )

        response = client.post('/stallions/register-new-stallion', files=files, headers=headers)
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
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # (0) max
        response = client.get('/stallions/search?page=1&limit=16&max_price=2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 0)

        # (1) min
        response = client.get('/stallions/search?page=1&limit=16&min_price=430')
        self.assertEqual(response.status_code, 200)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 2)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # (1) max
        response = client.get('/stallions/search?page=1&limit=16&max_price=568')
        self.assertEqual(response.status_code, 200)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 1)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # (2) min
        response = client.get('/stallions/search?page=1&limit=16&min_price=580')
        self.assertEqual(response.status_code, 200)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 2)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(570, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # (2) max
        response = client.get('/stallions/search?page=1&limit=16&max_price=740')
        self.assertEqual(response.status_code, 200)

        pricing_config = pricing_utils.load_config()
        self.assertEqual(len(response.json()["content"]), 1)

        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # (3) min
        response = client.get('/stallions/search?page=1&limit=16&min_price=1277')
        self.assertEqual(response.status_code, 200)

        pricing_config = pricing_utils.load_config()
        self.assertEqual(len(response.json()["content"]), 1)

        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(1278, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # (3) max
        response = client.get('/stallions/search?page=1&limit=16&max_price=1277')
        self.assertEqual(response.status_code, 200)

        pricing_config = pricing_utils.load_config()
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # (4) min
        response = client.get('/stallions/search?page=1&limit=16&min_price=8500')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 0)

        # (4) max
        response = client.get('/stallions/search?page=1&limit=16&max_price=8500')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # both breeds
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 2)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # one breed
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Bertrand")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        response = client.get('/stallions/search?page=1&limit=16&breeds=Arabe')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Joris")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # among other breeds
        response = client.get('/stallions/search?page=1&limit=16&breeds=Arabe&breeds=Welsh')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Joris")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # testing 422 breeds
        response = client.get('/stallions/search?page=1&limit=16&breeds=doesnotexist')
        self.assertEqual(response.status_code, 422)

        response = client.get('/stallions/search?page=1&limit=16&breeds=bonjour&breeds=Welsh')
        self.assertEqual(response.status_code, 422)

        # breed and price
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 2)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(570, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

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

        # testing 422 production breeds
        response = client.get('/stallions/search?page=1&limit=16&production_breeds=doesnotexist')
        self.assertEqual(response.status_code, 422)

        response = client.get('/stallions/search?page=1&limit=16&production_breeds=bonjour&production_breeds=Welsh')
        self.assertEqual(response.status_code, 422)

        # price, breed and production_breeds
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(570, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # both colors
        response = client.get('/stallions/search?page=1&limit=16&colors=Bai&colors=Blanc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 2)

        content_sorted_on_name = sorted(response.json()["content"], key=lambda x: x["name"])

        self.assertEqual(len(content_sorted_on_name), 2)
        self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)
        self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # one color
        response = client.get('/stallions/search?page=1&limit=16&colors=Blanc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Bertrand")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        response = client.get('/stallions/search?page=1&limit=16&colors=Bai')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Joris")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # among other colors
        response = client.get('/stallions/search?page=1&limit=16&colors=Bai&colors=Noir')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Joris")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # testing 422 colors
        response = client.get('/stallions/search?page=1&limit=16&colors=doesnotexist')
        self.assertEqual(response.status_code, 422)

        response = client.get('/stallions/search?page=1&limit=16&colors=bonjour&colors=Bai')
        self.assertEqual(response.status_code, 422)

        # price, breed, production_breeds and colors
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner&colors=Blanc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(570, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # cover_type
        response = client.get('/stallions/search?page=1&limit=16&cover_types=hand&cover_types=iarp')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["name"], "Bertrand")
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # testing 422 cover types
        response = client.get('/stallions/search?page=1&limit=16&cover_types=doesnotexist')
        self.assertEqual(response.status_code, 422)

        response = client.get('/stallions/search?page=1&limit=16&cover_types=bonjour&cover_types=lib')
        self.assertEqual(response.status_code, 422)

        # price, breed, production_breeds, colors and cover_types with 0 result bcs the price of the cover type asked is too high
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner&colors=Blanc&cover_types=lib')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 0)

        # price, breed, production_breeds, colors and cover_types
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner&colors=Blanc&cover_types=hand')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["content"]), 1)
        self.assertEqual(response.json()["content"][0]["price"], pricing_utils.calculate_checkout(570, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

        # testing 422 when price, breed, production_breeds, colors and cover_types
        response = client.get('/stallions/search?page=1&limit=16&breeds=Fjord&breeds=Arabe&min_price=580&production_breeds=Fjord&production_breeds=Trakehner&colors=Blanc&cover_types=hand&cover_types=doesnotexist')
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
        # self.assertEqual(content_sorted_on_name[0]["price"], pricing_utils.calculate_checkout(425, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)
        # self.assertEqual(content_sorted_on_name[1]["price"], pricing_utils.calculate_checkout(750, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT']).total)

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

    def tearDown(self):
        self.cs.close()
        self.ph.close()
        self.cstl.close()
        self.phtl.close()


if __name__ == '__main__':
    os.chdir('../bin')
    unittest.main()
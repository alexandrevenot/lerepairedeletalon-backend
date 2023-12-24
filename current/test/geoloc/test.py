import unittest
import os
import sys

from fastapi import FastAPI

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../bin/')))

import app.geoloc.router as geoloc_router
import app.geoloc.utils as geoloc_utils

server = FastAPI()

server.include_router(geoloc_router.router)

client = TestClient(server)

class GeolocTest(unittest.TestCase):
    def test(self):
        result = geoloc_utils.find_city_not_normalized('abancourt')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["lat"], 49.6961)
        self.assertEqual(result[0]["lng"], 1.7651)
        self.assertEqual(result[1]["lat"], 50.2347)
        self.assertEqual(result[1]["lng"], 3.2127)

        result = geoloc_utils.find_city_not_normalized('toulouse')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["lat"], 43.6043)
        self.assertEqual(result[0]["lng"], 1.4437)
        self.assertEqual(result[0]["postal_code"], "31000")

        result = geoloc_utils.find_city_not_normalized('saunieres')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["lat"], 46.9015)
        self.assertEqual(result[0]["lng"], 5.0796)
        self.assertEqual(result[0]["postal_code"], "71350")

        result = geoloc_utils.find_city_not_normalized('gormekzjlnbgjrekyuhbx')
        self.assertEqual(len(result), 0)

        result = geoloc_utils.normalize("This-Is-an-Étrange'Name")
        self.assertEqual(result, "thisisanetrangename")

        response = client.get('/geoloc/city?city=Toulouse')
        self.assertEqual(response.status_code, 200)
        result = response.json()["content"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["lat"], 43.6043)
        self.assertEqual(result[0]["lng"], 1.4437)
        self.assertEqual(result[0]["postal_code"], "31000")

        response = client.get('/geoloc/city?city=abbevilleLaRiviere')
        self.assertEqual(response.status_code, 200)
        result = response.json()["content"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["lat"], 48.3468)
        self.assertEqual(result[0]["lng"], 2.1659)
        self.assertEqual(result[0]["postal_code"], "91150")
        self.assertEqual(result[0]["city"], "Abbéville-la-Rivière")

        result = geoloc_utils.find_dep_and_region("83")
        self.assertEqual(result["dep_name"], "Var")
        self.assertEqual(result["reg_name"], "Provence-Alpes-Côte d'Azur")

if __name__ == '__main__':
    os.chdir('../bin')
    unittest.main()
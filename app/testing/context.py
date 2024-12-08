import mongomock
import unittest

fake_client = mongomock.MongoClient()
fake_db = fake_client.main

class DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def start_transaction(self):
        pass

    def commit_transaction(self):
        pass

    def abort_transaction(self):
        pass

class DummyClient:
    def start_session(self):
        return DummySession()

dummy_client = DummyClient()

get_db = lambda: fake_db
get_db_client = lambda: dummy_client

class SMTPDummySession:
    def __init__(self, osef, osef2):
        pass

    def __enter__(self):
        return unittest.mock.Mock()

    def __exit__(self, exc_type, exc_value, traceback):
        pass

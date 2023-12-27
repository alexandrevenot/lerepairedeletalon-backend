import mongomock

fake_client = mongomock.MongoClient()
fake_db = fake_client.main

class DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def start_transaction(self):
        return self

class DummyClient:
    def start_session(self):
        return DummySession()

dummy_client = DummyClient()

get_db = lambda: fake_db
get_db_client = lambda: dummy_client
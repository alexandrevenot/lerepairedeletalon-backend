import yaml

from pymongo import MongoClient

with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

class DBConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = MongoClient(config['mongo_url'])
            cls._instance.db = getattr(cls._instance.client, config['db_to_use'])
        return cls._instance

def get_db():
    return DBConnection().db
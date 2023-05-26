import yaml

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/stallions/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)
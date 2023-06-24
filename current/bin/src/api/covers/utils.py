import yaml

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/covers/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)
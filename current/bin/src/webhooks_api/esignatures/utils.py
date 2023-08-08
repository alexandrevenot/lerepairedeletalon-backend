import yaml

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/contracts/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)
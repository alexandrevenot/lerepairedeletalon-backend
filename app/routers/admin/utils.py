import yaml

def load_global_config() -> dict:
    with open('etc/config.yaml', 'r', encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('etc/admin/config.yaml', 'r', encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

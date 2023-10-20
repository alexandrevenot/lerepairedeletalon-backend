import yaml

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/covers/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

config = load_config()

def check_status_graph(status: str, next_status: str, pov: str):
    graph = config[f'{pov}_status_graph']
    return graph[status] is not None and next_status in graph[status]

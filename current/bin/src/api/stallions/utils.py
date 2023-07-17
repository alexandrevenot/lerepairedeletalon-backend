import yaml

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/stallions/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def get_displayed_price(document: dict, min_price: float, max_price: float) -> float:
    c = 0
    if min_price is not None:
        c += 1
    if max_price is not None:
        c += 1

    if c == 0:
        return min([elt["price"] for elt in document["prices"]])
    elif c == 1:
        if min_price is not None:
            return min([elt["price"] for elt in document["prices"] if elt["price"] >= min_price])
        else:
            return min([elt["price"] for elt in document["prices"] if elt["price"] <= max_price])
    else:
        return min([elt["price"] for elt in document["prices"] if elt["price"] >= min_price and elt["price"] <= max_price])


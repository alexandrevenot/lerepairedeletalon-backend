import yaml
import stripe

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/payments/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

config = load_config()

stripe.api_key = config["api_key"]

def delete_stripe_account(account_id):
    stripe.Account.delete(account_id)

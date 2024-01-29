import traceback
import yaml

from bson.objectid import ObjectId
from pymongo.errors import PyMongoError

import app.covers.utils as cover_utils
import app.mailing.utils as mailing_utils

covers_config = cover_utils.load_config()

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/users/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def notify_user(new_status: str, cover_id: ObjectId, destination_pov: str, user_in_db: dict, notifier_in_db: str, db, logger):
    try:
        db.users.update_one(
            {"_id": user_in_db["_id"]},
            {
                "$pull": {
                    f"notifications.covers.{destination_pov}.{group}": {"$in": [cover_id]}
                        for group in covers_config["destination-pov-and-status-to-group"][destination_pov].values()
                        if group != covers_config['destination-pov-and-status-to-group'][destination_pov][new_status]
                },
                "$addToSet": {
                    f"notifications.covers.{destination_pov}.{covers_config['destination-pov-and-status-to-group'][destination_pov][new_status]}": cover_id
                }
            }
        )
    except PyMongoError:
        logger.error('failed to write db: %s', traceback.format_exc())
    except KeyError:
        logger.error('error in notify_user: %s', traceback.format_exc())

    mailing_utils.send_notification_email(
        f"{user_in_db['firstname']} {user_in_db['lastname']}",
        user_in_db["email"],
        notifier_in_db["firstname"],
        new_status,
        destination_pov
    )

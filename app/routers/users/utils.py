import traceback

from bson.objectid import ObjectId
from pymongo.errors import PyMongoError

from ..mailing import utils as mailing_utils
from app.config import settings

def notify_user(new_status: str, cover_id: ObjectId, destination_pov: str, user_in_db: dict, notifier_in_db: str, db, logger):
    try:
        db.users.update_one(
            {"_id": user_in_db["_id"]},
            {
                "$pull": {
                    f"notifications.covers.{destination_pov}.{group}": {"$in": [cover_id]}
                        for group in settings.destination_pov_and_status_to_group[destination_pov].values()
                        if group != settings.destination_pov_and_status_to_group[destination_pov][new_status]
                },
                "$addToSet": {
                    f"notifications.covers.{destination_pov}.{settings.destination_pov_and_status_to_group[destination_pov][new_status]}": cover_id
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

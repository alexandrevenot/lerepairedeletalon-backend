import traceback
import yaml
from datetime import datetime, date

from fastapi import HTTPException
from pymongo.errors import PyMongoError

def load_global_config() -> dict:
    with open('etc/config.yaml', 'r', encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('etc/covers/config.yaml', 'r', encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

config = load_config()

def check_status_graph(status: str, next_status: str, pov: str):
    graph = config[f'{pov}_status_graph']
    return graph[status] is not None and next_status in graph[status]

async def step_forward_cover(cover_in_db: dict, next_status: str, db, logger, session=None):
    cursor_index = cover_in_db["timestamps"]["cursor_index"]
    timestamps_list = cover_in_db["timestamps"]["timestamps_list"]

    if timestamps_list[cursor_index]["status"] != next_status:
        timestamps_list.insert(cursor_index, {"status": next_status, "timestamp": datetime.now()})
    else:
        timestamps_list[cursor_index]["timestamp"] = datetime.now()

    try:
        update = {
            '$set': {
                'status': next_status,
                'timestamps' + '.' + 'cursor_index': cursor_index + 1,
                'timestamps' + '.' + 'timestamps_list': timestamps_list
                }
            }
        db.covers.update_one({"_id": cover_in_db["_id"]}, update, session=session)
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

def check_arrival_date(value: str):
    try:
        arrival_date = datetime.strptime(value, "%d/%m/%Y")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="incorrect arrival date format") from exc

    now = datetime.now()
    arrival_date_date = arrival_date.date()
    if now.month >= 10:
        if arrival_date_date < date(now.year+1, 1, 1):
            raise HTTPException(status_code=422, detail=f"<01/01/{now.year+1}")

        if arrival_date_date > date(now.year+1, 9, 30):
            raise HTTPException(status_code=422, detail=f">30/09/{now.year+1}")
    else:
        if arrival_date_date < now.date():
            raise HTTPException(status_code=422, detail=f"<{now.date().strftime('%d/%m/%Y')}")

        if arrival_date_date > date(now.year, 9, 30):
            raise HTTPException(status_code=422, detail=f">30/09/{now.year}")

    return arrival_date

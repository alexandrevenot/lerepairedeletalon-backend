import logging
import logging.handlers
import traceback
from pathlib import Path

from fastapi import APIRouter, HTTPException

from . import schemas, utils

# logging
log_dir = Path(__file__).parent.parent.parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(20)
handler = logging.handlers.RotatingFileHandler(
    f'logs/{__name__}.log',
    maxBytes=1024 * 1025 * 50,
    backupCount=2,
    mode='a'
    )
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info('Logger initialized')

# routes
router = APIRouter(prefix='/geoloc')

@router.get('/city', response_model=schemas.GetCitiesRM)
async def get_city(city: str):
    try:
        result = utils.find_city(city)
    except Exception as exc:
        logger.error('failed to read csvs to find city: %s', traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to find city') from exc

    if len(result) == 0:
        raise HTTPException(status_code=404, detail="city not found")

    return schemas.GetCitiesRM(content=result)

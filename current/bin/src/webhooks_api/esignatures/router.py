import logging
import logging.handlers
import base64
import aiohttp
import traceback

from typing import Annotated

from fastapi import APIRouter, HTTPException, Header

import src.webhooks_api.esignatures.utils as utils
import src.webhooks_api.esignatures.schemas as schemas

# configs
config = utils.load_config()

# logging
logger = logging.getLogger(__name__)
logger.setLevel(20)
handler = logging.handlers.RotatingFileHandler(
    f'/lerepairedeletalon/server/import/var/log/API/{__name__}.log',
    maxBytes=1024 * 1025 * 50,
    backupCount=2,
    mode='a'
    )
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info('Logger initialized')

router = APIRouter(prefix='/esignatures')

@router.post('/webhooks')
async def manage_wehbooks(query: schemas.ContractWebhookBody, authorization: Annotated[str | None, Header()] = None):
    try:
        assert authorization.split(" ")[1].encode('utf-8') == base64.b64encode((config["secret-token"] + ":").encode('utf-8'))
    except Exception as exc:
        raise HTTPException(status_code=401) from exc
    
    if query.status == "signer-signed":
        try:
            contract_id = query.data["contract"]["id"]
            data = {
                "contract_id": contract_id
            }
        except Exception as exc:
            logger.error(f'error when parsing webhook data: {traceback.format_exc()}')
            raise HTTPException(status_code=500, detail='error when parsing webhook data') from exc

        try:
            async with aiohttp.ClientSession() as session:
                url = "http://localhost:3001/covers/step-forward-signature"
                headers = {"Authorization": authorization}
                async with session.post(url, headers=headers, json=data) as response:
                    assert response.status == 200, f"POST on {url} : received status {response.status}"
        except Exception as exc:
            logger.error(f'error when processing signer-signed webhook: {traceback.format_exc()}')
            raise HTTPException(status_code=500, detail='error when processing signer-signed webhook') from exc

    return {"message": "successfully received webhook"}
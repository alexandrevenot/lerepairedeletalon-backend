import yaml
import base64
import aiohttp
import traceback

from typing import Annotated

from fastapi import APIRouter, HTTPException, Header

import src.webhooks_api.esignatures.utils as utils
import src.webhooks_api.esignatures.schemas as schemas

config = utils.load_config()

router = APIRouter(prefix='/esignatures')

@router.post('/webhooks')
async def manage_wehbooks(query: schemas.ContractWebhookBody, authorization: Annotated[str | None, Header()] = None):
    try:
        assert authorization.split(" ")[1].encode('utf-8') == base64.b64encode((config["secret-token"] + ":").encode('utf-8'))
    except:
        raise HTTPException(status_code=401)
    
    if query.status == "signer-signed":
        try:
            contract_id = query.data["contract"]["id"]
            data = {
                "contract_id": contract_id
            }
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:3001/covers/step-forward-signature"
                headers = {"Authorization": authorization}
                async with session.put(url, headers=headers, json=data) as response:
                    assert response.status == 200, f"PUT on http://localhost:3001/covers/step-forward-signature : received status {response.status}"
        except:
            print(traceback.format_exc())

    return {"message": "successfully received webhook"}
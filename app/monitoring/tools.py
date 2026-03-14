import traceback

import aiohttp

async def send_telegram_message(message: str, telegram_api_key: str, logger) -> None:
    url = f"https://api.telegram.org/bot7956411435:{telegram_api_key}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    "chat_id": 675660486,
                    "text": message,
                    "parse_mode": "MarkdownV2"
                }
            ) as response:
                assert response.status == 200, f"POST on https://api.telegram.org : received status code {response.status}"
    except Exception:
        logger.error('Error on send_telegram_message: %s', traceback.format_exc())

import aiohttp
from config import TRONACCS_API_URL


class TronaccsAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}

    async def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{TRONACCS_API_URL}{endpoint}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, params=params) as resp:
                return await resp.json()

    async def _post(self, endpoint: str, data: dict = None) -> dict:
        url = f"{TRONACCS_API_URL}{endpoint}"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=data) as resp:
                return await resp.json()

    async def get_me(self) -> dict:
        """Получить информацию о себе."""
        return await self._get("/me")

    async def get_items(self, filters: dict = None, page: int = 1) -> dict:
        """Получить список аккаунтов на маркете."""
        params = {"category": "telegram", "page": page}
        if filters:
            params.update(filters)
        return await self._get("/items", params)

    async def get_my_orders(self) -> dict:
        """Получить мои покупки."""
        return await self._get("/my-orders")

    async def get_item(self, item_id: int) -> dict:
        """Получить товар по ID."""
        return await self._get(f"/items/{item_id}")

    async def purchase_item(self, item_id: int) -> dict:
        """Купить товар."""
        return await self._post(f"/items/{item_id}/purchase")

    async def validate_key(self) -> bool:
        """Проверить валидность API ключа."""
        try:
            result = await self.get_me()
            return result.get("status") == "ok" or "id" in result
        except Exception:
            return False

import httpx
import json
import binascii
from typing import Any, List, Optional
from app.core.config import settings

class GraphAPIClient:
    def __init__(self):
        self.base_url = settings.read_api_url
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def decode_protobuf_name(self, name_field: str) -> str:
        try:
            if isinstance(name_field, str) and '"value"' in name_field:
                parsed = json.loads(name_field)
                hex_value = parsed.get("value")
                if hex_value:
                    return bytes.fromhex(hex_value).decode('utf-8')
        except Exception:
            pass
        return name_field

    async def call_api(self, method: str, endpoint: str, body: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        client = self._get_client()
        print(f"  📡 [GraphAPI] {method} {endpoint}")
        if body:
            print(f"  📦 Body: {json.dumps(body, indent=2)}")
        try:
            response = await client.request(method, url, json=body)
            if response.status_code >= 400:
                print(f"  ❌ API Error {response.status_code}: {response.text}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  ❌ API Call failed: {str(e)}")
            raise e

    async def search_entities(self, params: dict) -> List[dict]:
        result = await self.call_api("POST", "/v1/entities/search", params)
        entities = result.get("body", [])
        return entities

    async def get_relations(self, entity_id: str, body: Optional[dict] = None) -> List[dict]:
        endpoint = f"/v1/entities/{entity_id}/relations"
        actual_body = body if body is not None else {}
        result = await self.call_api("POST", endpoint, actual_body)
        return result if isinstance(result, list) else []

    async def get_attributes(self, category_id: str, dataset_name: str) -> dict:
        endpoint = f"/v1/entities/{category_id}/attributes/{dataset_name}"
        return await self.call_api("GET", endpoint)

graph_client = GraphAPIClient()

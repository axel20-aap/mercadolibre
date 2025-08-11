import os
import re
import time
from typing import Optional, Dict, Any
import requests

OAUTH_URL = "https://api.mercadolibre.com/oauth/token"
ITEM_URL = "https://api.mercadolibre.com/items/{}"
USER_ITEMS_SEARCH = "https://api.mercadolibre.com/users/{user_id}/items/search"
SITE_SEARCH = "https://api.mercadolibre.com/sites/MLM/search"


class MercadoLibreAPI:
    def __init__(self):
        self.app_id = os.environ.get("ML_APP_ID")
        self.app_secret = os.environ.get("ML_APP_SECRET")
        self.refresh_token = os.environ.get("ML_REFRESH_TOKEN")
        self.user_id = os.environ.get("ML_USER_ID")
        self.seller_id = os.environ.get("ML_SELLER_ID", self.user_id)
        self._access_token: Optional[str] = None
        self._access_token_exp = 0

    def _refresh_access_token(self) -> None:
        if not self.refresh_token:
            raise RuntimeError("Missing ML_REFRESH_TOKEN secret")
        data = {
            "grant_type": "refresh_token",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "refresh_token": self.refresh_token,
        }
        resp = requests.post(OAUTH_URL, data=data, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        self._access_token = payload["access_token"]
        # expires_in es en segundos
        self._access_token_exp = int(time.time()) + int(payload.get("expires_in", 3000)) - 60

    def _token(self) -> str:
        if not self._access_token or time.time() >= self._access_token_exp:
            self._refresh_access_token()
        return self._access_token  # type: ignore

    def get_item(self, item_id: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._token()}"}
        resp = requests.get(ITEM_URL.format(item_id), headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def search_items_by_sku(self, sku: str) -> Dict[str, Any]:
        if not self.user_id:
            raise RuntimeError("Missing ML_USER_ID secret for sku search")
        headers = {"Authorization": f"Bearer {self._token()}"}
        params = {"sku": sku}
        resp = requests.get(USER_ITEMS_SEARCH.format(user_id=self.user_id), params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def search_site_by_query(self, q: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._token()}"}
        params = {"q": q, "seller_id": self.seller_id}
        resp = requests.get(SITE_SEARCH, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def parse_item_id_from_url(url: str) -> Optional[str]:
        # Busca IDs del tipo /MLM-123456789 o /MLM123456789
        m = re.search(r"/(MLM-?\d+)", url, re.IGNORECASE)
        if m:
            raw = m.group(1).upper()
            return raw.replace("-", "")
        return None

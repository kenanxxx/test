import json
import time
from typing import Optional
import httpx
import base58

from config import SOLANA_RPC_URL, SOLANA_WSS_URL, PUMP_FUN_PROGRAM


class SolanaClient:
    def __init__(self):
        self.rpc_url = SOLANA_RPC_URL
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self._cache = {}
        self._cache_ttl = 5
        self._req_id = 0

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    async def _rpc_call(self, method: str, params: list) -> Optional[dict]:
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": method,
                "params": params,
            }
            response = await self.http_client.post(self.rpc_url, json=payload)
            data = response.json()
            if "result" in data:
                return data["result"]
            elif "error" in data:
                print(f"RPC error: {data['error']}")
        except Exception as e:
            print(f"RPC call error: {e}")
        return None

    async def get_account_info(self, address: str) -> Optional[dict]:
        cache_key = f"account:{address}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data

        result = await self._rpc_call(
            "getAccountInfo", [address, {"encoding": "jsonParsed"}]
        )
        if result and result.get("value"):
            self._cache[cache_key] = (time.time(), result["value"])
            return result["value"]
        return None

    async def get_token_balance(self, mint: str) -> float:
        result = await self._rpc_call(
            "getTokenAccountBalance", [mint]
        )
        if result and "value" in result:
            amount = float(result["value"].get("amount", 0))
            decimals = result["value"].get("decimals", 6)
            return amount / (10 ** decimals)
        return 0.0

    async def get_sol_balance(self, address: str) -> float:
        result = await self._rpc_call("getBalance", [address])
        if result:
            return result.get("value", 0) / 1e9
        return 0.0

    async def get_signatures_for_address(
        self, address: str, limit: int = 100
    ) -> list:
        result = await self._rpc_call(
            "getSignaturesForAddress", [address, {"limit": limit}]
        )
        if result:
            return result
        return []

    async def get_transaction(self, signature: str) -> Optional[dict]:
        cache_key = f"tx:{signature}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data

        result = await self._rpc_call(
            "getTransaction",
            [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
        )
        if result:
            self._cache[cache_key] = (time.time(), result)
            return result
        return None

    async def send_transaction(self, signed_tx_bytes: bytes) -> Optional[str]:
        encoded = base58.b58encode(signed_tx_bytes).decode("ascii")
        result = await self._rpc_call(
            "sendTransaction",
            [encoded, {"encoding": "base58", "skipPreflight": True, "maxRetries": 3}],
        )
        return result

    async def get_recent_blockhash(self) -> Optional[str]:
        result = await self._rpc_call("getRecentBlockhash", [])
        if result and "value" in result:
            return result["value"]["blockhash"]
        return None

    async def get_token_largest_accounts(self, mint: str) -> list:
        result = await self._rpc_call(
            "getTokenLargestAccounts", [mint]
        )
        if result and "value" in result:
            return result["value"]
        return []

    async def get_program_accounts(self, program_id: str, filters: list, limit: int = 0) -> list:
        params = [program_id, {"encoding": "jsonParsed", "filters": filters}]
        if limit:
            params[1]["dataSlice"] = {"offset": 0, "length": limit}
        result = await self._rpc_call("getProgramAccounts", params)
        if result:
            return result
        return []

    async def get_token_accounts_by_owner(self, owner: str) -> list:
        result = await self._rpc_call(
            "getTokenAccountsByOwner",
            [
                owner,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"},
            ],
        )
        if result and "value" in result:
            return result["value"]
        return []

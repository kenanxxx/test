import struct
import time
import asyncio
from typing import Optional, List
from datetime import datetime

from blockchain import SolanaClient
from models import (
    TokenInfo,
    TokenStatus,
    BondingCurveInfo,
    BondingCurveStage,
)
from config import (
    GRADUATION_THRESHOLD_SOL,
    PUMP_FUN_PROGRAM,
    fetch_sol_price,
    LOG_RPC_RAW,
)


class PumpFunAnalyzer:
    def __init__(self, solana_client: SolanaClient):
        self.client = solana_client
        self.tracked_tokens = {}
        self.graduation_callbacks = []

        # Caching and concurrency config
        self._decimals_cache = {}  # {mint: (decimals, expires_at)}
        self._largest_cache = {}  # {mint: (holders_list, expires_at)}
        self.decimals_cache_ttl = 3600  # seconds
        self.largest_cache_ttl = 120  # seconds

        # reduce concurrency to avoid heavy rate-limiting
        self.rpc_semaphore = asyncio.Semaphore(2)

        # rpc retry/backoff defaults
        self._rpc_retries = 8
        self._rpc_backoff = 1.5

    async def _rpc(self, func, *args, retries: int = None, backoff: float = None, **kwargs):
        if retries is None:
            retries = self._rpc_retries
        if backoff is None:
            backoff = self._rpc_backoff
        last_exc = None
        for attempt in range(retries):
            try:
                async with self.rpc_semaphore:
                    return await func(*args, **kwargs)
            except Exception as e:
                last_exc = e
                msg = str(e)
                if LOG_RPC_RAW:
                    try:
                        print(f"[RPC RAW ERROR attempt={attempt}] func={getattr(func,'__name__',str(func))} args={args} kwargs={kwargs} exc={e}")
                    except Exception:
                        pass
                # rate limit or transient network error -> backoff and retry
                if 'rate limited' in msg.lower() or 'rate limit' in msg.lower() or '429' in msg or '-32429' in msg:
                    await asyncio.sleep(backoff * (2 ** attempt))
                    continue
                await asyncio.sleep(backoff * (2 ** attempt))
        if last_exc:
            print(f"RPC error after retries: {last_exc}")
        return None

    def calculate_market_cap(self, virtual_sol: float, virtual_tokens: float, total_supply: float, sol_price_usd: float) -> float:
        if virtual_tokens == 0:
            return 0
        price_per_token_sol = virtual_sol / virtual_tokens
        market_cap_sol = price_per_token_sol * total_supply
        return market_cap_sol * sol_price_usd

    def determine_stage(self, sol_deposited: float) -> BondingCurveStage:
        completion = (sol_deposited / GRADUATION_THRESHOLD_SOL) * 100
        if completion < 25:
            return BondingCurveStage.EARLY
        elif completion < 50:
            return BondingCurveStage.MID
        elif completion < 90:
            return BondingCurveStage.LATE
        else:
            return BondingCurveStage.THRESHOLD

    async def get_bonding_curve_info(self, token_mint: str) -> Optional[BondingCurveInfo]:
        try:
            account = await self.client.get_account_info(token_mint)
            if not account:
                return None

            data = account.get("data")
            if not data:
                return None

            if isinstance(data, dict) and "parsed" in data:
                info = data["parsed"].get("info", {})
                token_data = info.get("data", {})
                parsed_info = token_data.get("parsed", {}).get("info", {})

                if "virtualSolReserves" in parsed_info:
                    virtual_sol = float(parsed_info.get("virtualSolReserves", 0)) / 1e9
                    virtual_tokens = float(parsed_info.get("virtualTokenReserves", 0)) / 1e6
                    real_sol = float(parsed_info.get("realSolReserves", 0)) / 1e9
                    real_tokens = float(parsed_info.get("realTokenReserves", 0)) / 1e6
                    total_supply = float(parsed_info.get("tokenTotalSupply", 1_000_000_000_000_000)) / 1e6

                    tokens_sold = total_supply - real_tokens
                    sol_price = await fetch_sol_price()
                    market_cap = self.calculate_market_cap(virtual_sol, virtual_tokens, total_supply, sol_price)
                    stage = self.determine_stage(real_sol)
                    completion = (real_sol / GRADUATION_THRESHOLD_SOL) * 100

                    return BondingCurveInfo(
                        token_mint=token_mint,
                        sol_deposited=real_sol,
                        tokens_sold=tokens_sold,
                        tokens_remaining=real_tokens,
                        virtual_sol_reserves=virtual_sol,
                        virtual_token_reserves=virtual_tokens,
                        market_cap_usd=market_cap,
                        stage=stage,
                        completion_percent=min(completion, 100),
                    )
        except Exception as e:
            print(f"Error fetching bonding curve for {token_mint}: {e}")
        return None

    async def check_graduation_status(self, token_mint: str) -> bool:
        try:
            account = await self.client.get_account_info(token_mint)
            if account:
                owner = account.get("owner", "")
                return owner != PUMP_FUN_PROGRAM
        except Exception as e:
            print(f"Error checking graduation status: {e}")
        return False

    def _normalize_amount_from_holder_entry(self, entry: dict, decimals: int) -> Optional[float]:
        # Prefer uiAmount/uiAmountString when present (already scaled)
        if entry.get("uiAmount") is not None:
            try:
                return float(entry.get("uiAmount"))
            except Exception:
                pass
        if entry.get("uiAmountString") is not None:
            try:
                return float(entry.get("uiAmountString"))
            except Exception:
                pass

        ta = entry.get("tokenAmount") or {}
        if isinstance(ta, dict):
            if ta.get("uiAmount") is not None:
                try:
                    return float(ta.get("uiAmount"))
                except Exception:
                    pass
            if ta.get("uiAmountString") is not None:
                try:
                    return float(ta.get("uiAmountString"))
                except Exception:
                    pass
            if ta.get("amount") is not None:
                try:
                    return float(ta.get("amount")) / (10 ** int(ta.get("decimals", decimals)))
                except Exception:
                    pass

        if entry.get("amount") is not None:
            try:
                return float(entry.get("amount")) / (10 ** decimals)
            except Exception:
                pass

        return None

    async def get_decimals_for_mint(self, token_mint: str, fallback: int = 6) -> int:
        now = time.time()
        entry = self._decimals_cache.get(token_mint)
        if entry and entry[1] > now:
            return entry[0]

        mint_decimals = None
        supply_func = getattr(self.client, "get_token_supply", None)
        if callable(supply_func):
            try:
                resp = await self._rpc(supply_func, token_mint)
                if resp:
                    if isinstance(resp, dict):
                        if "value" in resp and isinstance(resp["value"], dict):
                            mint_decimals = int(resp["value"].get("decimals", fallback))
                        else:
                            mint_decimals = int(resp.get("decimals", fallback))
            except Exception:
                mint_decimals = None

        if mint_decimals is None:
            request_func = getattr(self.client, "request", None)
            if callable(request_func):
                try:
                    resp = await self._rpc(request_func, "getTokenSupply", [token_mint])
                    if resp and isinstance(resp, dict):
                        if "result" in resp and isinstance(resp["result"], dict):
                            mint_decimals = int(resp["result"].get("value", {}).get("decimals", fallback))
                        elif "value" in resp:
                            mint_decimals = int(resp["value"].get("decimals", fallback))
                except Exception:
                    mint_decimals = None

        if mint_decimals is None:
            try:
                mint_info = await self._rpc(self.client.get_account_info, token_mint)
                if mint_info:
                    data = mint_info.get("data", mint_info)
                    if isinstance(data, dict) and "parsed" in data:
                        parsed = data["parsed"].get("info", {})
                        mint_decimals = int(parsed.get("decimals", fallback))
            except Exception:
                mint_decimals = None

        if mint_decimals is None:
            mint_decimals = fallback

        self._decimals_cache[token_mint] = (mint_decimals, now + self.decimals_cache_ttl)
        return mint_decimals

    async def analyze_holders(self, token_mint: str, fresh_threshold: int = 6000, tx_scan_limit: int = 50) -> tuple:
        try:
            decimals = await self.get_decimals_for_mint(token_mint)

            now = time.time()
            cached = self._largest_cache.get(token_mint)
            if cached and cached[1] > now:
                largest = cached[0]
            else:
                largest_resp = await self._rpc(self.client.get_token_largest_accounts, token_mint)
                largest = largest_resp or []
                self._largest_cache[token_mint] = (largest, now + self.largest_cache_ttl)

            holders = []
            if largest:
                for a in largest[:10]:
                    addr = a.get("address") or a.get("pubkey") or a.get("account")
                    amount = self._normalize_amount_from_holder_entry(a, decimals)
                    if amount is None:
                        continue
                    holders.append({"address": addr, "amount": amount})
            else:
                accounts = await self._rpc(
                    self.client.get_program_accounts,
                    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    [{"dataSize": 165}, {"memcmp": {"offset": 0, "bytes": token_mint}}],
                )
                if not accounts:
                    return ("?", "?")
                accounts.sort(
                    key=lambda a: float(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]),
                    reverse=True,
                )
                for a in accounts[:10]:
                    info = a["account"]["data"]["parsed"]["info"]
                    amt_raw = float(info["tokenAmount"]["amount"])
                    dec = int(info["tokenAmount"].get("decimals", decimals))
                    holders.append({"address": a["pubkey"], "amount": amt_raw / (10 ** dec)})

            if not holders:
                return ("?", "?")

            holder_map = {h["address"]: h["amount"] for h in holders}
            holder_set = set(holder_map.keys())

            sigs = await self._rpc(self.client.get_signatures_for_address, token_mint, tx_scan_limit)
            if not sigs:
                print("No signatures available for tx-scan; cannot robustly detect bundles")
                return ("?", "?")

            async def fetch_tx(sig_info):
                sig = sig_info.get("signature")
                if not sig:
                    return None
                tx = await self._rpc(self.client.get_transaction, sig)
                if tx is None:
                    return None
                if not tx.get("slot"):
                    tx["slot"] = sig_info.get("slot")
                if not tx.get("blockTime"):
                    tx["blockTime"] = sig_info.get("blockTime")
                return tx

            sem = asyncio.Semaphore(2)
            async def sem_fetch(s):
                async with sem:
                    return await fetch_tx(s)

            txs = await asyncio.gather(*[sem_fetch(s) for s in sigs])
            txs_filtered = [t for t in txs if t]
            if not txs_filtered:
                print("No transactions available after fetch; aborting tx-scan")
                return ("?", "?")

            def tx_key(t):
                bt = t.get("blockTime")
                if bt is None:
                    return t.get("slot", 0)
                return int(bt)

            txs_filtered.sort(key=tx_key)

            holder_first_seen = {addr: (None, None) for addr in holder_set}
            slot_to_holders = {}

            for tx in txs_filtered:
                slot = tx.get("slot")
                block_time = tx.get("blockTime")
                message = tx.get("transaction", {}).get("message", {})
                account_keys = message.get("accountKeys", [])
                norm_keys = set()
                for k in account_keys:
                    if isinstance(k, str):
                        norm_keys.add(k)
                    elif isinstance(k, dict):
                        pk = k.get("pubkey") or k.get("pubkeyOrAddress") or k.get("address")
                        if pk:
                            norm_keys.add(pk)
                intersects = holder_set.intersection(norm_keys)
                if intersects:
                    for addr in intersects:
                        if holder_first_seen.get(addr)[0] is None:
                            holder_first_seen[addr] = (block_time, slot)
                if len(intersects) > 1 and slot is not None:
                    s = slot
                    slot_to_holders.setdefault(s, set()).update(intersects)

            total = sum(holder_map.values())
            if total == 0:
                return ("?", "?")

            fresh_total = 0.0
            for addr, amt in holder_map.items():
                seen = holder_first_seen.get(addr)
                if seen and seen[0] is not None:
                    try:
                        if (time.time() - float(seen[0])) < fresh_threshold:
                            fresh_total += amt
                    except Exception:
                        pass

            bundle_total = 0.0
            for s, addrs in slot_to_holders.items():
                slot_sum = sum(holder_map.get(a, 0) for a in addrs)
                bundle_total += slot_sum

            if bundle_total > total:
                bundle_total = total

            fresh_pct = round((fresh_total / total) * 100, 1)
            bundle_pct = round((bundle_total / total) * 100, 1)

            print(f"[analyze_holders] token={token_mint} total={total:.6f} fresh={fresh_total:.6f} bundle={bundle_total:.6f} decimals={decimals}")
            return (fresh_pct, bundle_pct)
        except Exception as e:
            print(f"analyze_holders error for {token_mint}: {e}")
            return ("?", "?")


class PumpFunDataParser:
    @staticmethod
    def parse_create_instruction(data: bytes) -> Optional[dict]:
        try:
            if len(data) < 8:
                return None
            discriminator = data[:8]
            if discriminator != b"\x18\x1e\xc8\x18\x1c\xcd\x7f\x00":
                return None
            offset = 8
            name_len = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            name = data[offset : offset + name_len].decode("utf-8")
            offset += name_len
            symbol_len = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            symbol = data[offset : offset + symbol_len].decode("utf-8")
            offset += symbol_len
            uri_len = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            uri = data[offset : offset + uri_len].decode("utf-8")
            return {"name": name, "symbol": symbol, "uri": uri}
        except Exception:
            return None

    @staticmethod
    def parse_buy_instruction(data: bytes) -> Optional[dict]:
        try:
            if len(data) < 8:
                return None
            discriminator = data[:8]
            if discriminator != b"\x66\x06\x3d\x12\x01\xda\xeb\xea":
                return None
            offset = 8
            amount = struct.unpack_from("<Q", data, offset)[0]
            offset += 8
            max_sol_cost = struct.unpack_from("<Q", data, offset)[0]
            return {"amount": amount, "max_sol_cost": max_sol_cost}
        except Exception:
            return None

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
from config import GRADUATION_THRESHOLD_SOL, PUMP_FUN_PROGRAM, fetch_sol_price


class PumpFunAnalyzer:
    def __init__(self, solana_client: SolanaClient):
        self.client = solana_client
        self.tracked_tokens = {}
        self.graduation_callbacks = []
        # limit concurrent RPC calls to avoid rate limiting
        self.rpc_semaphore = asyncio.Semaphore(8)

    async def _rpc(self, func, *args, retries: int = 4, backoff: float = 0.5, **kwargs):
        """Helper wrapper for RPC calls with semaphore, retries, and exponential backoff."""
        last_exc = None
        for attempt in range(retries):
            try:
                async with self.rpc_semaphore:
                    return await func(*args, **kwargs)
            except Exception as e:
                last_exc = e
                msg = str(e)
                # treat rate limit / RPC throttle similarly
                if 'rate limited' in msg.lower() or 'rate limit' in msg.lower() or '429' in msg or '-32429' in msg:
                    await asyncio.sleep(backoff * (2 ** attempt))
                    continue
                # non-rate-limit error -> wait a bit and retry
                await asyncio.sleep(backoff * (2 ** attempt))
        # final attempt failed
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

    async def monitor_token(self, token_mint: str) -> Optional[TokenInfo]:
        if token_mint in self.tracked_tokens:
            token = self.tracked_tokens[token_mint]

            if token.status == TokenStatus.BONDING_CURVE:
                curve_info = await self.get_bonding_curve_info(token_mint)
                if curve_info:
                    token.bonding_curve = curve_info
                    token.status = TokenStatus.GRADUATING

                    is_graduated = await self.check_graduation_status(token_mint)
                    if is_graduated:
                        token.status = TokenStatus.PUMP_SWAP
                        print(f"Token {token.symbol} graduated to PumpSwap!")

                        for callback in self.graduation_callbacks:
                            await callback(token)

            elif token.status == TokenStatus.PUMP_SWAP:
                if token.boost_start_time is None:
                    token.boost_start_time = datetime.now()
                    from datetime import timedelta
                    token.boost_end_time = token.boost_start_time + timedelta(seconds=300)
                    token.status = TokenStatus.BOOST_ACTIVE
                    print(f"BOOST started for {token.symbol}")

            elif token.status == TokenStatus.BOOST_ACTIVE:
                if datetime.now() >= token.boost_end_time:
                    token.status = TokenStatus.BOOST_COMPLETE
                    print(f"BOOST completed for {token.symbol}")

            return token

        curve_info = await self.get_bonding_curve_info(token_mint)
        if curve_info:
            token = TokenInfo(
                mint=token_mint,
                name="",
                symbol="",
                uri="",
                creator="",
                created_at=datetime.now(),
                bonding_curve=curve_info,
            )
            self.tracked_tokens[token_mint] = token
            return token

        return None

    async def scan_new_tokens(self) -> List[TokenInfo]:
        new_tokens = []
        try:
            signatures = await self._rpc(self.client.get_signatures_for_address, PUMP_FUN_PROGRAM, 20)
            if not signatures:
                return new_tokens

            for sig_info in signatures:
                sig = sig_info.get("signature")
                if not sig:
                    continue

                tx = await self._rpc(self.client.get_transaction, sig)
                if not tx:
                    continue

                meta = tx.get("meta", {})
                if not meta or meta.get("err"):
                    continue

                message = tx.get("transaction", {}).get("message", {})
                account_keys = message.get("accountKeys", [])

                for key in account_keys:
                    if isinstance(key, str) and len(key) >= 32 and len(key) <= 44:
                        try:
                            if key not in self.tracked_tokens:
                                token_info = await self.monitor_token(key)
                                if token_info and token_info.bonding_curve:
                                    new_tokens.append(token_info)
                        except Exception:
                            pass

        except Exception as e:
            print(f"Error scanning new tokens: {e}")

        return new_tokens

    def add_graduation_callback(self, callback):
        self.graduation_callbacks.append(callback)

    async def analyze_holders(self, token_mint: str, fresh_threshold: int = 6000, tx_scan_limit: int = 300) -> tuple:
        """
        Returns (fresh_pct, bundle_pct).
        - fresh_threshold: seconds to consider a wallet 'fresh'.
        - tx_scan_limit: how many recent transactions for the token to scan for bundle detection.

        New approach:
        - Determine decimals via get_token_supply (preferred) or mint account.
        - Get largest holder accounts and their amounts (ui or raw -> normalized using decimals).
        - For bundle detection: fetch recent transactions for the token mint, parse each transaction's accountKeys,
          and if a transaction contains more than one of the holders, count those holders' amounts toward bundle_total for that slot.
        - For fresh detection: instead of per-owner signature queries, derive first-seen blockTime per holder by scanning the same transaction list
          (the earliest tx in which the holder appears in this token's txs).
        This reduces per-owner RPC calls and avoids rate-limits.
        """
        try:
            # --- determine token decimals reliably ---
            decimals = 6  # default fallback

            # 1) preferred: token supply RPC
            mint_supply = await self._rpc(self.client.get_token_supply, token_mint)
            try:
                if mint_supply:
                    if isinstance(mint_supply, dict):
                        if "value" in mint_supply and isinstance(mint_supply["value"], dict):
                            decimals = int(mint_supply["value"].get("decimals", decimals))
                        else:
                            decimals = int(mint_supply.get("decimals", decimals))
            except Exception:
                pass

            # 2) fallback: mint account parsing
            if decimals == 6:
                mint_info = await self._rpc(self.client.get_account_info, token_mint)
                try:
                    if mint_info:
                        data = mint_info.get("data", mint_info)
                        if isinstance(data, dict) and "parsed" in data:
                            parsed = data["parsed"].get("info", {})
                            decimals = int(parsed.get("decimals", decimals))
                except Exception:
                    pass

            # --- largest accounts ---
            largest_resp = await self._rpc(self.client.get_token_largest_accounts, token_mint)
            largest = largest_resp or []

            holders = []
            if largest:
                for a in largest[:10]:
                    addr = a.get("address") or a.get("pubkey") or a.get("account")
                    raw_amount = None
                    if "amount" in a and a.get("amount") is not None:
                        raw_amount = a.get("amount")
                    elif "uiAmount" in a and a.get("uiAmount") is not None:
                        try:
                            raw_amount = float(a.get("uiAmount")) * (10 ** decimals)
                        except Exception:
                            raw_amount = None
                    elif isinstance(a.get("tokenAmount"), dict) and "amount" in a.get("tokenAmount"):
                        raw_amount = a["tokenAmount"]["amount"]

                    if raw_amount is None:
                        continue

                    try:
                        amount = float(raw_amount) / (10 ** decimals)
                    except Exception:
                        amount = 0.0

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

            # Build quick lookup
            holder_map = {h["address"]: h["amount"] for h in holders}
            holder_set = set(holder_map.keys())

            # --- Scan recent transactions for the token to detect bundles and first-seen times ---
            sigs = await self._rpc(self.client.get_signatures_for_address, token_mint, tx_scan_limit)
            if not sigs:
                # fallback to previous owner-based approach for fresh detection only
                print("No signatures available for tx-scan; cannot robustly detect bundles")
                # fallback: mark fresh as unknown
                total = sum(holder_map.values())
                return ("?", "?")

            # We'll fetch transactions concurrently but bounded
            async def fetch_tx(sig_info):
                sig = sig_info.get("signature")
                if not sig:
                    return None
                tx = await self._rpc(self.client.get_transaction, sig)
                # attach blockTime/slot from sig_info if missing
                if tx is None:
                    return None
                if not tx.get("slot"):
                    tx["slot"] = sig_info.get("slot")
                if not tx.get("blockTime"):
                    tx["blockTime"] = sig_info.get("blockTime")
                return tx

            # limit concurrency
            sem = asyncio.Semaphore(6)
            async def sem_fetch(s):
                async with sem:
                    return await fetch_tx(s)

            txs = await asyncio.gather(*[sem_fetch(s) for s in sigs])

            # Process txs from oldest to newest to capture first-seen times
            txs_filtered = [t for t in txs if t]
            # sort by slot/blockTime ascending
            def tx_key(t):
                bt = t.get("blockTime")
                if bt is None:
                    return t.get("slot", 0)
                return int(bt)

            txs_filtered.sort(key=tx_key)

            holder_first_seen = {addr: (None, None) for addr in holder_set}
            slot_map = {}

            for tx in txs_filtered:
                slot = tx.get("slot")
                block_time = tx.get("blockTime")
                message = tx.get("transaction", {}).get("message", {})
                account_keys = message.get("accountKeys", [])
                # normalize account keys to strings
                norm_keys = set()
                for k in account_keys:
                    if isinstance(k, str):
                        norm_keys.add(k)
                    elif isinstance(k, dict):
                        # some RPC return dicts with pubkey
                        pk = k.get("pubkey") or k.get("pubkeyOrAddress") or k.get("address")
                        if pk:
                            norm_keys.add(pk)
                # find intersection
                intersects = holder_set.intersection(norm_keys)
                if intersects:
                    for addr in intersects:
                        if holder_first_seen.get(addr)[0] is None:
                            holder_first_seen[addr] = (block_time, slot)
                if len(intersects) > 1 and slot is not None:
                    # sum amounts for the holders that appeared in this tx and add to slot_map
                    s = slot
                    slot_map.setdefault(s, 0)
                    for addr in intersects:
                        slot_map[s] += holder_map.get(addr, 0)

            total = sum(holder_map.values())
            if total == 0:
                return ("?", "?")

            # fresh_total: holders whose first-seen (in token txs) is within threshold
            fresh_total = 0.0
            for addr, amt in holder_map.items():
                seen = holder_first_seen.get(addr)
                if seen and seen[0] is not None:
                    try:
                        if (time.time() - float(seen[0])) < fresh_threshold:
                            fresh_total += amt
                    except Exception:
                        pass

            bundle_total = sum(v for v in slot_map.values() if v > 0)

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

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
            signatures = await self.client.get_signatures_for_address(
                PUMP_FUN_PROGRAM, limit=20
            )

            for sig_info in signatures:
                sig = sig_info.get("signature")
                if not sig:
                    continue

                tx = await self.client.get_transaction(sig)
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

    async def analyze_holders(self, token_mint: str) -> tuple:
        try:
            largest = await self.client.get_token_largest_accounts(token_mint)
            if largest:
                enriched = []
                for a in largest[:10]:
                    addr = a["address"]
                    amount = float(a["amount"]) / 1e6
                    info = await self.client.get_account_info(addr)
                    if info:
                        parsed = info.get("data", {}).get("parsed", {})
                        owner = parsed.get("info", {}).get("owner")
                    else:
                        owner = None
                    enriched.append({"address": addr, "amount": amount, "owner": owner})
                largest = enriched
            else:
                accounts = await self.client.get_program_accounts(
                    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    [{"dataSize": 165}, {"memcmp": {"offset": 0, "bytes": token_mint}}],
                )
                if not accounts:
                    return ("?", "?")
                accounts.sort(key=lambda a: float(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]), reverse=True)
                largest = []
                for a in accounts[:10]:
                    info = a["account"]["data"]["parsed"]["info"]
                    largest.append({
                        "address": a["pubkey"],
                        "amount": float(info["tokenAmount"]["amount"]) / 1e6,
                        "owner": info.get("owner"),
                    })

            fresh_threshold = 6000
            owner_cache = {}

            async def get_wallet_first_slot(owner):
                if not owner:
                    return (None, None)
                if owner in owner_cache:
                    return owner_cache[owner]
                sigs = await self.client.get_signatures_for_address(owner, 100)
                if sigs:
                    oldest = sigs[-1]
                    owner_cache[owner] = (oldest["blockTime"], oldest.get("slot"))
                else:
                    owner_cache[owner] = (None, None)
                return owner_cache[owner]

            async def process(acc):
                amount = acc["amount"]
                block_time, slot = await get_wallet_first_slot(acc["owner"])
                if block_time is None:
                    return (amount, False, None)
                is_fresh = (time.time() - block_time) < fresh_threshold
                return (amount, is_fresh, slot)

            results = await asyncio.gather(*[process(a) for a in largest])
            total = sum(r[0] for r in results)
            if total == 0:
                return ("?", "?")

            fresh_total = sum(r[0] for r in results if r[1])
            slot_map = {}
            for amt, _, slot in results:
                if slot is not None:
                    slot_map.setdefault(slot, []).append(amt)
            bundle_total = sum(sum(v) for v in slot_map.values() if len(v) > 1)

            fresh_pct = round((fresh_total / total) * 100, 1)
            bundle_pct = round((bundle_total / total) * 100, 1)
            return (fresh_pct, bundle_pct)
        except:
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

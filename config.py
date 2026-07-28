import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

_sol_price_data = {"price": 150.0, "updated": 0.0}


async def fetch_sol_price(client: httpx.AsyncClient = None) -> float:
    global _sol_price_data
    if time.time() - _sol_price_data["updated"] < 60:
        return _sol_price_data["price"]
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=5) as c:
                resp = await c.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
                data = resp.json()
                _sol_price_data["price"] = float(data["solana"]["usd"])
        else:
            resp = await client.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
            data = resp.json()
            _sol_price_data["price"] = float(data["solana"]["usd"])
        _sol_price_data["updated"] = time.time()
    except:
        pass
    return _sol_price_data["price"]

SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
SOLANA_WSS_URL = os.getenv("SOLANA_WSS_URL", "wss://api.mainnet-beta.solana.com")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_FUN_PROGRAM_V2 = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"

BOOST_SOL_AMOUNT = 17.6
BOOST_USDC_AMOUNT = 2516
BOOST_WINDOW_SECONDS = 300

GRADUATION_THRESHOLD_SOL = 85
GRADUATION_THRESHOLD_USD = 69000

SCAN_INTERVAL_SECONDS = 1
MIN_MARKET_CAP_USD = 50000
MAX_MARKET_CAP_USD = 100000

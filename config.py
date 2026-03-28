"""
Konfigürasyon yönetimi
"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Uygulama konfigürasyonu"""
    
    # Solana RPC
    SOLANA_RPC_URL = os.getenv(
        "SOLANA_RPC_URL", 
        "https://api.mainnet-beta.solana.com"
    )
    
    # Market Cap Aralığı
    MIN_MCAP = float(os.getenv("MIN_MCAP", "100000"))
    MAX_MCAP = float(os.getenv("MAX_MCAP", "10000000"))
    
    # Takip edilecek cüzdanlar (virgülle ayrılmış)
    WALLETS = os.getenv("WALLETS", "").split(",") if os.getenv("WALLETS") else []
    WALLETS = [w.strip() for w in WALLETS if w.strip()]
    
    # Web UI
    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
    
    # Polling interval (saniye) - İşlemleri kontrol etme sıklığı
    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))  # 5 saniye (daha hızlı)
    
    # Cache süresi (saniye)
    CACHE_DURATION = int(os.getenv("CACHE_DURATION", "300"))
    
    @classmethod
    def get_wallets(cls) -> List[str]:
        """Tüm cüzdanları döndür"""
        return cls.WALLETS.copy()
    
    @classmethod
    def validate(cls) -> bool:
        """Konfigürasyonu doğrula"""
        if not cls.WALLETS:
            return False
        if cls.MIN_MCAP >= cls.MAX_MCAP:
            return False
        return True

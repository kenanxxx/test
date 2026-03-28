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
    # Format: address veya emoji|name|address
    WALLETS = os.getenv("WALLETS", "").split(",") if os.getenv("WALLETS") else []
    WALLETS = [w.strip() for w in WALLETS if w.strip()]
    
    # Cüzdan etiketleri (emoji ve isim)
    WALLET_LABELS = {}
    
    # Web UI
    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
    
    # Polling interval (saniye) - İşlemleri kontrol etme sıklığı
    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))  # 5 saniye (daha hızlı)
    
    # Cache süresi (saniye)
    CACHE_DURATION = int(os.getenv("CACHE_DURATION", "300"))
    
    @classmethod
    def parse_wallet(cls, wallet_str: str) -> tuple:
        """Cüzdan string'ini parse et: emoji|name|address veya address"""
        if '|' in wallet_str:
            parts = wallet_str.split('|')
            if len(parts) == 3:
                emoji, name, address = parts
                return address.strip(), emoji.strip(), name.strip()
            elif len(parts) == 2:
                name, address = parts
                return address.strip(), '', name.strip()
        return wallet_str.strip(), '', ''
    
    @classmethod
    def get_wallets(cls) -> List[str]:
        """Tüm cüzdan adreslerini döndür"""
        wallets = []
        for w in cls.WALLETS:
            address, emoji, name = cls.parse_wallet(w)
            wallets.append(address)
            if name or emoji:
                cls.WALLET_LABELS[address] = {'emoji': emoji, 'name': name}
        return wallets
    
    @classmethod
    def get_wallet_label(cls, address: str) -> dict:
        """Cüzdan etiketini döndür"""
        return cls.WALLET_LABELS.get(address, {'emoji': '', 'name': ''})
    
    @classmethod
    def validate(cls) -> bool:
        """Konfigürasyonu doğrula"""
        if not cls.WALLETS:
            return False
        if cls.MIN_MCAP >= cls.MAX_MCAP:
            return False
        return True

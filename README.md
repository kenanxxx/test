# Solana Wallet Tracker

Solana ağında belirli market cap aralığında birden fazla cüzdanın token işlemlerini gerçek zamanlı takip eden Python uygulaması.

## Özellikler

✨ **Temel Özellikler:**
- 🔍 Birden fazla cüzdanı eş zamanlı takip
- 💰 Market cap aralığına göre filtreleme
- 📊 Gerçek zamanlı işlem bildirimleri
- 🎯 Token transfer tespiti
- ⚡ Async/await ile performanslı çalışma
- 💾 Market cap cache sistemi

## Kurulum

```bash
# Gereksinimleri yükle
pip install -r requirements.txt
```

## Kullanım

### Basit Kullanım

```python
import asyncio
from solana_wallet_tracker import SolanaWalletTracker

async def main():
    # Tracker oluştur
    tracker = SolanaWalletTracker(
        min_mcap=100000,      # 100K USD minimum market cap
        max_mcap=10000000,    # 10M USD maximum market cap
    )
    
    # Cüzdanları ekle
    tracker.add_wallets([
        "7YttLkHDoNj9wyDur5pM1ejNaAvT9X4eqaYcHQqtj2G5",
        "HN7cABqLq46Es1jh92dQQisAq662SmxELLLsHHe4YWrH",
    ])
    
    # Takibi başlat
    await tracker.start_tracking()

asyncio.run(main())
```

### Özelleştirilmiş RPC Endpoint

```python
# Custom RPC endpoint kullan (Helius, QuickNode, vb.)
tracker = SolanaWalletTracker(
    rpc_url="https://your-rpc-endpoint.com",
    min_mcap=50000,
    max_mcap=5000000
)
```

### Environment Variable ile RPC

```bash
# .env dosyası oluştur veya export et
export SOLANA_RPC_URL="https://your-rpc-endpoint.com"

# Scripti çalıştır
python solana_wallet_tracker.py
```

## Yapılandırma Parametreleri

| Parametre | Açıklama | Varsayılan |
|-----------|----------|------------|
| `rpc_url` | Solana RPC endpoint | `https://api.mainnet-beta.solana.com` |
| `min_mcap` | Minimum market cap (USD) | `100000` |
| `max_mcap` | Maximum market cap (USD) | `10000000` |

## Örnek Çıktı

```
🚀 Tracker başlatılıyor...
Market Cap Aralığı: $100,000 - $10,000,000
Takip edilen cüzdan sayısı: 2

================================================================================
🔔 YENİ İŞLEM TESPİT EDİLDİ!
Cüzdan: 7YttLkHD...4eqaYcHQ
Token: Example Token (EXMPL)
Market Cap: $5,234,567.89
Miktar: 1,234.5678 EXMPL
Tip: transferChecked
Zaman: 2026-03-28 10:30:45
Signature: 3kX7...9mNp
Solscan: https://solscan.io/tx/3kX7...9mNp
================================================================================
```

## API Kullanımı

Kod, token market cap bilgisi için **DexScreener API** kullanır. Rate limit'e dikkat edin.

### Alternatif API'ler

Aşağıdaki API'leri de kullanabilirsiniz:
- Jupiter API
- CoinGecko API  
- Birdeye API

## Notlar

⚠️ **Önemli:**
- Public RPC rate limit'e takılabilir. Üretim için özel RPC kullanın (Helius, QuickNode, vb.)
- Market cap verileri DexScreener'dan gelir ve birkaç saniye gecikmeli olabilir
- Cache sistemi 5 dakika boyunca market cap verilerini saklar

## Lisans

MIT

## Katkıda Bulunma

Pull request'ler memnuniyetle karşılanır!

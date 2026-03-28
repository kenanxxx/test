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
- 🌐 Web arayüzü ile kolay yönetim
- 🔗 Padre.gg trade entegrasyonu

## Kurulum

### 1. Gereksinimleri Yükle

```bash
pip install -r requirements.txt
```

### 2. RPC Endpoint Ayarla (🔥 ÖNEMLİ!)

**Public RPC yeterli değil!** 5 cüzdan takip için **ücretsiz premium RPC** gereklidir.

➡️ **[RPC_SETUP.md](RPC_SETUP.md) dosyasını okuyun!**

**Hızlı kurulum (Helius - Önerilen):**

1. https://www.helius.dev/ adresine kaydol
2. API key al
3. `.env` dosyasında güncelle:
   ```env
   SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY
   ```

**Ücretsiz RPC seçenekleri:**
- 🔥 **Helius:** 100,000 istek/gün
- ⚡ **QuickNode:** 250,000 istek/gün  
- 🚀 **Alchemy:** 300M compute units/ay
- 💪 **Ankr:** 500,000 istek/gün

## Kullanım

### Web Arayüzü ile Kullanım (Önerilen)

```bash
# .env dosyası oluştur
cp .env.example .env

# .env dosyasını düzenle ve cüzdanları ekle
# WALLETS=cuzdan1,cuzdan2,cuzdan3

# Web UI'yı başlat
python web_app.py

# Tarayıcıda aç
http://localhost:8080
```

**Web Arayüzü Özellikleri:**
- 📊 Canlı durum takibi
- ⚙️ Tüm ayarları web'den yönetme
- 📝 Cüzdan ekleme/çıkarma
- 💰 Market cap aralığını ayarlama
- 📈 İşlem geçmişi görüntüleme
- 🔗 Padre.gg trade linklerine tek tıkla erişim

### Basit Kullanım (Komut Satırı)

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

### Environment Variable ile Konfigürasyon

```bash
# .env.example'dan .env oluştur
cp .env.example .env

# .env dosyasını düzenle
nano .env
```

**.env Örnek:**
```env
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
MIN_MCAP=100000
MAX_MCAP=10000000
WALLETS=wallet1,wallet2,wallet3
WEB_PORT=8080
POLL_INTERVAL=10
```

## Yapılandırma Parametreleri

| Parametre | Açıklama | Varsayılan |
|-----------|----------|------------|
| `rpc_url` | Solana RPC endpoint | `https://api.mainnet-beta.solana.com` |
| `min_mcap` | Minimum market cap (USD) | `100000` |
| `max_mcap` | Maximum market cap (USD) | `10000000` |
| `wallets` | Takip edilecek cüzdanlar (virgülle ayrılmış) | - |
| `web_port` | Web UI portu | `8080` |
| `poll_interval` | İşlemleri kontrol etme sıklığı (saniye) | `5` |
| `cache_duration` | Cache süresi (saniye) | `300` |

### Polling Interval Ayarları

| Değer | Hız | Açıklama |
|-------|-----|------------|
| 1-3 saniye | ⚡ Çok Hızlı | Anlık tespit, RPC limiti riskli |
| **5 saniye** | 🚀 **Hızlı (Önerilen)** | **Hızlı tespit, güvenli** |
| 10 saniye | 🐢 Normal | Eski varsayılan, yavaş |
| 15+ saniye | 🐌 Yavaş | RPC dostu ama tespit gecikmeli |

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
Trade: https://trade.padre.gg/trade/solana/TokenAddress
================================================================================
```

## API Kullanımı

Kod, token market cap bilgisi için **DexScreener API** kullanır. Rate limit'e dikkat edin.

### Alternatif API'ler

Aşağıdaki API'leri de kullanabilirsiniz:
- Jupiter API
- CoinGecko API  
- Birdeye API

## ⚠️ Sorun Giderme

### RPC Testi

RPC endpoint'inizin çalışıp çalışmadığını test edin:

```bash
python test_rpc.py
```

Bu script:
- ✅ RPC sağlık kontrolü
- ✅ Slot okuma testi
- ✅ Cüzdan işlemleri okuma testi
- ✅ İşlem detayı okuma testi
- 📊 Birden fazla RPC karşılaştırma

### "RPC timeout" veya "429 Too Many Requests" hatası

**Sebep:** Public RPC rate limit yapıyor.

**Çözüm:** 
1. **`python test_rpc.py` çalıştırın** - RPC'yi test edin
2. **[RPC_SETUP.md](RPC_SETUP.md) dosyasını okuyun**
3. Ücretsiz Helius/QuickNode/Alchemy RPC kullanın
### İşlemler yakalanmıyor

**Kontrol listesi:**
1. ✅ RPC endpoint çalışıyor mu? (Premium RPC kullanın)
2. ✅ Cüzdanlar doğru mu?
3. ✅ Market cap aralığı uygun mu?
4. ✅ Cüzdanlarda işlem yapılıyor mu?

**Debug modu:**
Program her adımda detaylı log verir:
```
🔍 Yeni TX tespit edildi: 5aB2C3dE4fG5...
   ✓ 2 token değişimi bulundu
   🔎 Token kontrol ediliyor: 7xKXtg2CW...
   💰 Market Cap: $5,234,567
   ✅ Market cap aralıkta!
```

## Notlar

⚠️ **Önemli:**
- 🔥 **Public RPC yeterli değildir!** Premium RPC kullanın ([RPC_SETUP.md](RPC_SETUP.md))
- 📊 Market cap verileri DexScreener'dan gelir (birkaç saniye gecikme olabilir)
- 💾 Cache sistemi 5 dakika boyunca market cap verilerini saklar
- 🔄 Retry mekanizması timeout'larda otomatik yeniden deneme yapar

## Lisans

MIT

## Katkıda Bulunma

Pull request'ler memnuniyetle karşılanır!

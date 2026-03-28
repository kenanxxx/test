# RPC Endpoint Kurulumu

Public Solana RPC'si (`https://api.mainnet-beta.solana.com`) **çok fazla rate limit** yapar ve 5 cüzdan takip etmek için yeterli değildir.

## 🚨 Sorun

Public RPC:
- Saniyede 1-2 istek limiti
- Sık timeout
- 5 cüzdan × 10 saniyede bir polling = dakikada 30+ istek = rate limit

## ✅ Çözüm: Ücretsiz RPC Servisleri

### 1. **Helius (Önerilen)** 🔥
**Ücretsiz Plan:** 100,000 istek/gün

```bash
# Kayıt ol: https://www.helius.dev/
# API key al

# .env dosyasına ekle:
SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY
```

### 2. **QuickNode**
**Ücretsiz Plan:** 250,000 istek/gün

```bash
# Kayıt ol: https://www.quicknode.com/
# Solana Mainnet endpoint oluştur

# .env dosyasına ekle:
SOLANA_RPC_URL=https://your-endpoint.solana-mainnet.quiknode.pro/YOUR_TOKEN/
```

### 3. **Alchemy**
**Ücretsiz Plan:** 300M compute units/ay

```bash
# Kayıt ol: https://www.alchemy.com/
# Solana projesi oluştur

# .env dosyasına ekle:
SOLANA_RPC_URL=https://solana-mainnet.g.alchemy.com/v2/YOUR_API_KEY
```

### 4. **Ankr**
**Ücretsiz Plan:** 500,000 istek/gün

```bash
# Kayıt ol: https://www.ankr.com/rpc/
# API key al

# .env dosyasına ekle:
SOLANA_RPC_URL=https://rpc.ankr.com/solana/YOUR_API_KEY
```

### 5. **GetBlock**
**Ücretsiz Plan:** 40,000 istek/gün

```bash
# Kayıt ol: https://getblock.io/
# Solana endpoint oluştur

# .env dosyasına ekle:
SOLANA_RPC_URL=https://go.getblock.io/YOUR_API_KEY
```

## 🎯 Tavsiye Edilen: Helius

**Neden Helius?**
- En yüksek ücretsiz limit (100K/gün)
- Solana'ya özel optimize
- WebSocket desteği
- En hızlı yanıt süreleri
- Kolay kurulum

## 📝 Kurulum Adımları

1. **Helius'a kaydol:**
   - https://www.helius.dev/ adresine git
   - "Get Started Free" tıkla
   - Email ile kayıt ol

2. **Dashboard'dan API Key al:**
   - Dashboard > API Keys
   - "Create New Key" tıkla
   - Key'i kopyala

3. **.env dosyasını güncelle:**
   ```bash
   nano .env
   ```
   
   Şunu değiştir:
   ```env
   SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_HELIUS_API_KEY
   ```

4. **Programı yeniden başlat:**
   ```bash
   python web_app.py
   ```

## ⚡ Test Et

RPC'nin çalışıp çalışmadığını test et:

```bash
curl "https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```

Sonuç: `{"jsonrpc":"2.0","result":"ok","id":1}`

## 🔥 Hız Karşılaştırması

| RPC Provider | Response Time | Rate Limit | Ücretsiz |
|--------------|---------------|------------|----------|
| Public | 500-2000ms | ~100/min | ✅ |
| Helius | 50-200ms | 100K/gün | ✅ |
| QuickNode | 100-300ms | 250K/gün | ✅ |
| Alchemy | 100-250ms | 300M CU/ay | ✅ |
| Ankr | 200-400ms | 500K/gün | ✅ |

## 🚨 Hatalar ve Çözümleri

### Hata: "429 Too Many Requests"
**Çözüm:** RPC rate limit aşıldı. Premium RPC kullan.

### Hata: "Connection timeout"
**Çözüm:** RPC endpoint değiştir veya internet bağlantınızı kontrol edin.

### Hata: "Unauthorized"
**Çözüm:** API key doğru girilmemiş. .env dosyasını kontrol edin.

## 💡 İpuçları

1. **Birden fazla RPC kullan:** Fallback için birkaç endpoint tanımla
2. **Polling interval'ı artır:** 10 saniye yerine 15-20 saniye kullan
3. **Cüzdan sayısını azalt:** Önce 1-2 cüzdan ile test et
4. **WebSocket kullan:** Polling yerine WebSocket subscription kullan (gelişmiş)

## 📞 Destek

Sorun yaşıyorsanız:
1. `.env` dosyasını kontrol edin
2. API key'in doğru olduğundan emin olun
3. RPC provider'ın status sayfasını kontrol edin
4. Başka bir RPC provider deneyin

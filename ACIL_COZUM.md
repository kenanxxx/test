# 🚨 ACİL ÇÖZÜM - RPC Sorunu

## Sorun
```
❌ TX okunamadı: SolanaRpcException
```

Bu hata **Public Solana RPC'nin rate limit yaptığını** gösteriyor. 7 cüzdan takip etmek için yeterli değil.

## ✅ HEMEN ÇÖZÜM (5 Dakika)

### Adım 1: Helius'a Kaydol (Ücretsiz)

1. https://www.helius.dev/ adresine git
2. **Sign Up** tıkla
3. Email ile kayıt ol
4. Email'i onayla

### Adım 2: API Key Al

1. Dashboard'a gir
2. Sol menüden **"API Keys"** tıkla
3. **"Create New Key"** tıkla
4. Key'i kopyala (örnek: `a1b2c3d4-1234-5678-9abc-def123456789`)

### Adım 3: .env Dosyasını Güncelle

`.env` dosyasını aç ve şunu değiştir:

**ÖNCE:**
```env
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
```

**SONRA:**
```env
SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=BURAYA_API_KEY_YAPIŞTIR
```

### Adım 4: Programı Yeniden Başlat

```bash
# Ctrl+C ile durdur
# Sonra yeniden başlat:
python web_app.py
```

## 🎉 Sonuç

Artık:
- ✅ Rate limit YOK (100,000 istek/gün)
- ✅ Timeout YOK
- ✅ İşlemler yakalanıyor
- ✅ Hızlı yanıt (50-200ms)

## 🔄 Alternatif RPC'ler (Hepsi Ücretsiz)

### QuickNode
1. https://www.quicknode.com/ → Sign Up
2. Create Endpoint → Solana Mainnet
3. Copy HTTP URL
4. `.env` dosyasına yapıştır

### Alchemy
1. https://www.alchemy.com/ → Sign Up
2. Create App → Solana
3. Copy HTTPS URL
4. `.env` dosyasına yapıştır

### Ankr
1. https://www.ankr.com/rpc/ → Sign Up
2. Get Free RPC → Solana
3. Copy URL
4. `.env` dosyasına yapıştır

## ❓ Sık Sorulan Sorular

### Q: Ücretli mi?
**A:** Hayır! Hepsi ücretsiz planı var. Helius 100K istek/gün ücretsiz.

### Q: Kredi kartı istiyor mu?
**A:** Hayır, sadece email ile kayıt.

### Q: Ne kadar sürer?
**A:** Kayıt + API key alma 2-3 dakika. Toplam 5 dakika.

### Q: Public RPC neden çalışmıyor?
**A:** 7 cüzdan × 15 işlem × 10 saniyede bir = çok fazla istek. Public RPC dakikada 100 istek sınırı var.

## 🆘 Yardım

Hala sorun yaşıyorsanız:
1. `.env` dosyasının doğru olduğundan emin olun
2. API key'i tırnak işareti OLMADAN yapıştırın
3. Programı tamamen kapatıp yeniden başlatın
4. RPC URL'yi kontrol edin (https:// ile başlamalı)

## 📊 Test Et

Helius RPC çalışıyor mu test et:

```bash
curl "https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```

Sonuç: `{"jsonrpc":"2.0","result":"ok","id":1}` olmalı.

---

**TL;DR:** Public RPC yeterli değil. Helius kullan (ücretsiz, 5 dakika). ✅

# 🎣 Helius Webhook Kurulumu (Gerçek Zamanlı Takip)

Webhook ile işlemler **ANINDA** yakalanır! Polling yerine gerçek zamanlı bildirim.

---

## 📋 ADIM 1: Helius Hesabı Oluştur

1. **https://helius.dev** → Sign Up
2. Email ile kayıt ol (ÜCRETSİZ!)
3. Dashboard'a gir

---

## 📋 ADIM 2: API Key Al

1. Dashboard → **"Apps"** → **"Create New App"**
2. İsim: `Solana Tracker`
3. Network: **Mainnet**
4. **API Key'i kopyala** (örn: `abc123-...`)
5. `.env` dosyasına ekle:
   ```
   SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=BURAYA_API_KEY_YAPIŞTIR
   ```

---

## 📋 ADIM 3: Public URL Hazırla

Helius webhook'u **sizin sunucunuza POST request** atar. Bunun için:

### SEÇENEK A: ngrok (Yerel Test)
```bash
# ngrok indir: https://ngrok.com
ngrok http 8080

# Çıktı:
# Forwarding  https://abc123.ngrok.io -> http://localhost:8080
```

### SEÇENEK B: Public Server
- VPS/Cloud server kullanıyorsanız public IP'niz var
- Örn: `http://123.456.789.0:8080`

---

## 📋 ADIM 4: Webhook Oluştur

1. Helius Dashboard → **"Webhooks"** (sol menü)
2. **"Create Webhook"** tıkla
3. Ayarlar:

   **Webhook Type:** `Enhanced`  
   **Network:** `Mainnet`  
   **Transaction Types:**  
   - ✅ `SWAP`  
   - ✅ `TOKEN_TRANSFER` (opsiyonel)  
   
   **Webhook URL:**  
   ```
   https://abc123.ngrok.io/api/webhook
   ```
   (veya sizin public URL'niz)
   
   **Accounts (Addresses):**  
   ```
   CÜZDAN_ADRES_1
   CÜZDAN_ADRES_2
   CÜZDAN_ADRES_3
   ```
   (Her satıra bir cüzdan adresi)
   
   **Webhook Format:** `HELIUS_STANDARD`

4. **"Create Webhook"** tıkla

---

## 📋 ADIM 5: Uygulamayı Başlat

```bash
python web_app.py
```

Çıktı:
```
🌐 Web UI başlatıldı: http://0.0.0.0:8080
📊 Tarayıcınızda açın: http://localhost:8080
🎣 Webhook hazır: /api/webhook
```

---

## 📋 ADIM 6: Test Et

1. Helius Dashboard → Webhook'unuza tıkla
2. **"Test Webhook"** tıkla
3. Console'da şunu görmelisiniz:
   ```
   ⚡ WEBHOOK ALDI! 1 işlem
   ```

✅ **BAŞARILI!** Artık gerçek zamanlı takip aktif!

---

## 🔥 Avantajları

| Özellik | Polling | Webhook |
|---------|---------|---------|
| **Gecikme** | 2-5 saniye | <1 saniye |
| **RPC Kullanımı** | Yüksek | Çok Düşük |
| **İşlem Kaçırma** | Olabilir | Asla |
| **Maliyet** | Orta | Düşük |

---

## ⚠️ Dikkat

1. **Public URL gerekli** - Localhost çalışmaz (ngrok kullanın)
2. **HTTPS önerilir** - ngrok otomatik sağlıyor
3. **Port açık olmalı** - Firewall kontrolü yapın
4. **Helius limit**: 100K request/day (ücretsiz)

---

## 🧪 Debug

Webhook çalışmıyor mu?

### Health Check:
```bash
curl http://localhost:8080/api/webhook/health
```

Çıktı:
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00",
  "tracker_running": true
}
```

### Helius Test:
Dashboard'da **"View Logs"** → Son gönderilen webhook'ları gör

---

## 📞 Yardım

Sorun mu var?
1. Console çıktısını kontrol et
2. Helius Dashboard → Webhook Logs
3. ngrok web UI: http://127.0.0.1:4040

---

🎉 **TAMAMDIR! Artık gerçek zamanlı takip aktif!**

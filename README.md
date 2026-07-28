# Pump.fun BOOST Tracker Bot

Pump.fun platformundaki BOOST mekanizmasını izleyen ve analiz eden Python botu.

## BOOST Mekanizması Nedir?

- Token bonding curve'i tamamladığında PumpSwap'e geçer
- Geçiş sırasında ~17.6 SOL "ölü likidite" olarak ayrılırdı
- BOOST modu ile bu fonlar 5 dakika içinde TWAP ile token satın alır ve yakar
- Bu alım baskısı yaratır ve arzı azaltır

## Kurulum

```bash
cd pumpfun-boost-bot
pip install -r requirements.txt
```

## Yapılandırma

`.env` dosyasını oluşturun:

```bash
cp .env.example .env
```

Gerekli değerleri girin:

- `SOLANA_RPC_URL`: Solana RPC endpoint
- `SOLANA_WSS_URL`: Solana WebSocket endpoint
- `PRIVATE_KEY`: Cüzdan özel anahtarı
- `WALLET_ADDRESS`: Cüzdan adresi
- `TELEGRAM_BOT_TOKEN`: Telegram bot tokenı (opsiyonel)
- `TELEGRAM_CHAT_ID`: Telegram chat ID (opsiyonel)

## Çalıştırma

```bash
python bot.py
```

## Özellikler

- Token mezuniyetlerini izleme
- BOOST penceresini takip etme
- Ticaret sinyalleri üretme
- Portföy takibi
- Telegram bildirimleri

## Risk Uyarısı

Bu bot eğitim amaçlıdır. Kripto para ticareti yüksek risk içerir. Yatırım yapmadan önce araştırma yapın.

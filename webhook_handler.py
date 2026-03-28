"""
Helius Webhook Handler - Gerçek Zamanlı İşlem Yakalama
"""

from aiohttp import web
import asyncio
from datetime import datetime
from solana_wallet_tracker import SolanaWalletTracker

class WebhookHandler:
    def __init__(self, tracker: SolanaWalletTracker):
        self.tracker = tracker
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Webhook route'ları tanımla"""
        self.app.router.add_post('/webhook', self.handle_webhook)
        self.app.router.add_get('/webhook/health', self.health_check)
    
    async def health_check(self, request):
        """Webhook sağlık kontrolü"""
        return web.json_response({
            'status': 'ok',
            'timestamp': datetime.now().isoformat()
        })
    
    async def handle_webhook(self, request):
        """
        Helius webhook'undan gelen işlemi yakala
        
        Helius gönderdiği format:
        [
            {
                "type": "SWAP",
                "signature": "...",
                "slot": 123456,
                "timestamp": 1234567890,
                "accountData": [...],
                "nativeTransfers": [...],
                "tokenTransfers": [
                    {
                        "fromTokenAccount": "...",
                        "toTokenAccount": "...",
                        "fromUserAccount": "...",
                        "toUserAccount": "...",
                        "tokenAmount": 1000000,
                        "mint": "...",
                        "tokenStandard": "Fungible"
                    }
                ],
                ...
            }
        ]
        """
        try:
            # Webhook verisini al
            data = await request.json()
            
            print(f"\n⚡ WEBHOOK TETİKLENDİ! {len(data)} işlem alındı")
            
            # Her transaction için işle
            for tx_event in data:
                await self.process_webhook_transaction(tx_event)
            
            return web.json_response({'status': 'success'})
            
        except Exception as e:
            print(f"❌ Webhook hatası: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({'status': 'error', 'message': str(e)}, status=500)
    
    async def process_webhook_transaction(self, tx_event: dict):
        """Webhook transaction'ını işle"""
        try:
            signature = tx_event.get('signature')
            timestamp = tx_event.get('timestamp', int(datetime.now().timestamp()))
            token_transfers = tx_event.get('tokenTransfers', [])
            
            print(f"\n🔍 Webhook TX: {signature[:16]}...")
            
            # Token transferlerini kontrol et
            for transfer in token_transfers:
                # Takip edilen cüzdanlardan biri işlemde mi?
                from_wallet = transfer.get('fromUserAccount')
                to_wallet = transfer.get('toUserAccount')
                
                # Bizim takip ettiğimiz cüzdan BUY yapıyor mu? (token alıyor)
                for tracked_wallet in self.tracker.tracked_wallets:
                    # Cüzdan token alıyorsa = BUY
                    if to_wallet == tracked_wallet:
                        mint = transfer.get('mint')
                        amount = transfer.get('tokenAmount', 0)
                        
                        print(f"   ✅ ALIM TESPİT EDİLDİ!")
                        print(f"   Cüzdan: {tracked_wallet[:8]}...")
                        print(f"   Token: {mint[:8]}...")
                        print(f"   Miktar: {amount}")
                        
                        # Market cap kontrol et
                        mcap = await self.tracker.get_token_mcap(mint)
                        
                        if mcap:
                            print(f"   💰 Market Cap: ${mcap:,.0f}")
                            
                            if self.tracker.is_in_mcap_range(mcap):
                                print(f"   ✅ Market cap aralıkta! Bildirim gönderiliyor...")
                                
                                # Bildirim gönder
                                token_data = self.tracker.token_cache.get(mint, {})
                                
                                notification = {
                                    'wallet': tracked_wallet,
                                    'token_address': mint,
                                    'token_name': token_data.get('name', 'Unknown'),
                                    'token_symbol': token_data.get('symbol', mint[:8]),
                                    'market_cap': mcap,
                                    'amount': amount,
                                    'type': 'buy',
                                    'timestamp': timestamp,
                                    'signature': signature,
                                    'solscan_url': f"https://solscan.io/tx/{signature}",
                                    'trade_url': f"https://trade.padre.gg/trade/solana/{mint}"
                                }
                                
                                # Console output
                                print("\n" + "="*80)
                                print(f"🔔 WEBHOOK - YENİ İŞLEM TESPİT EDİLDİ!")
                                print(f"Cüzdan: {tracked_wallet[:8]}...{tracked_wallet[-8:]}")
                                print(f"Token: {notification['token_name']} ({notification['token_symbol']})")
                                print(f"Market Cap: ${mcap:,.2f}")
                                print(f"Signature: {signature}")
                                print(f"Trade: {notification['trade_url']}")
                                print("="*80)
                                
                                # Callback'leri çağır
                                for callback in self.tracker.transaction_callbacks:
                                    try:
                                        await callback(notification)
                                    except Exception as e:
                                        print(f"Callback hatası: {e}")
                            else:
                                print(f"   ❌ Market cap aralık dışı (${self.tracker.min_mcap:,.0f} - ${self.tracker.max_mcap:,.0f})")
                        else:
                            print(f"   ⚠️  Market cap bulunamadı")
                        
                        break  # Bu cüzdan için işlem tamamlandı
                        
        except Exception as e:
            print(f"❌ Transaction işleme hatası: {e}")
            import traceback
            traceback.print_exc()
    
    async def start(self, host='0.0.0.0', port=8081):
        """Webhook server'ı başlat"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        print(f"\n🎣 Webhook dinleniyor: http://{host}:{port}/webhook")
        print(f"🏥 Health check: http://{host}:{port}/webhook/health")
        print(f"\n📝 Helius Dashboard'da bu URL'yi kullanın:")
        print(f"   Webhook URL: http://YOUR_PUBLIC_IP:{port}/webhook")
        print(f"\n⚠️  NOT: Public IP veya ngrok kullanmalısınız!")
        

async def main():
    """Test için"""
    from config import Config
    
    # Tracker oluştur
    tracker = SolanaWalletTracker(
        rpc_url=Config.SOLANA_RPC_URL,
        min_mcap=Config.MIN_MCAP,
        max_mcap=Config.MAX_MCAP
    )
    tracker.add_wallets(Config.get_wallets())
    
    # Webhook handler başlat
    webhook = WebhookHandler(tracker)
    await webhook.start(port=8081)
    
    # Sonsuza kadar dinle
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n⏹️  Webhook durduruldu")


if __name__ == "__main__":
    asyncio.run(main())

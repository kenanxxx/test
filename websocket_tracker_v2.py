"""
WebSocket ile Gerçek Zamanlı Solana Wallet Tracker
Public RPC ile çalışır!
"""

import asyncio
import json
import websockets
from typing import List, Callable, Dict, Optional
from datetime import datetime
from solana_wallet_tracker import SolanaWalletTracker


class WebSocketTracker(SolanaWalletTracker):
    """WebSocket ile gerçek zamanlı takip"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ws_connections: Dict[str, any] = {}
        
    def get_ws_url(self) -> str:
        """RPC URL'den WebSocket URL'i oluştur"""
        # https:// -> wss:// , http:// -> ws://
        ws_url = self.rpc_url.replace('https://', 'wss://').replace('http://', 'ws://')
        print(f"🔌 WebSocket URL: {ws_url}")
        return ws_url
    
    async def subscribe_to_account(self, wallet_address: str):
        """
        WebSocket ile cüzdan değişikliklerini dinle
        accountSubscribe: Cüzdan balance değiştiğinde bildirim gelir
        """
        ws_url = self.get_ws_url()
        
        try:
            print(f"\n⚡ WebSocket bağlanıyor: {wallet_address[:8]}...")
            
            async with websockets.connect(ws_url, ping_timeout=60) as websocket:
                # accountSubscribe request
                subscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "accountSubscribe",
                    "params": [
                        wallet_address,
                        {
                            "encoding": "jsonParsed",
                            "commitment": "confirmed"
                        }
                    ]
                }
                
                await websocket.send(json.dumps(subscribe_request))
                
                # İlk yanıt: subscription ID
                response = await websocket.recv()
                response_data = json.loads(response)
                
                if 'result' in response_data:
                    subscription_id = response_data['result']
                    print(f"✅ WebSocket bağlandı! Sub ID: {subscription_id}")
                    print(f"🎧 {wallet_address[:8]}... dinleniyor...")
                    
                    # Sürekli dinle
                    while self.is_running:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=30)
                            await self.process_ws_message(wallet_address, message)
                        except asyncio.TimeoutError:
                            # Timeout normal, connection canlı tut
                            continue
                        except websockets.exceptions.ConnectionClosed:
                            print(f"⚠️  WebSocket bağlantı koptu: {wallet_address[:8]}...")
                            break
                else:
                    print(f"❌ WebSocket subscribe hatası: {response_data}")
                    
        except Exception as e:
            print(f"❌ WebSocket hatası {wallet_address[:8]}...: {e}")
            print(f"⏮️  Polling moduna geçiliyor...")
            # Fallback: Normal polling
            await self.track_wallet(wallet_address)
    
    async def process_ws_message(self, wallet_address: str, message: str):
        """WebSocket mesajını işle"""
        try:
            data = json.loads(message)
            
            # Notification mesajı mı?
            if 'method' in data and data['method'] == 'accountNotification':
                print(f"\n⚡ WebSocket Event! {wallet_address[:8]}...")
                print(f"   Account değişikliği tespit edildi!")
                
                # Son işlemleri kontrol et (WebSocket sadece değişikliği bildirir, detay vermez)
                # Bu yüzden RPC'ye son işlemleri sormamız gerekiyor
                await self.check_recent_transactions(wallet_address)
                
        except Exception as e:
            print(f"❌ WebSocket mesaj işleme hatası: {e}")
    
    async def check_recent_transactions(self, wallet_address: str):
        """WebSocket event geldiğinde son işlemleri kontrol et"""
        try:
            # Son 5 işlemi al (az tutuyoruz, zaten yeni işlem var)
            transactions = await self.get_wallet_transactions(wallet_address, limit=5)
            
            if not transactions:
                return
            
            # En son işlemi işle
            latest_tx = transactions[0]
            signature = latest_tx['signature']
            
            print(f"   🔍 Son işlem: {signature[:16]}...")
            
            # Parse et
            parsed = await self.parse_transaction(latest_tx)
            
            if parsed and parsed['tokens']:
                print(f"   ✓ {len(parsed['tokens'])} token değişimi bulundu")
                print(f"   📄 Token detay: {parsed['tokens']}")
                
                for token in parsed['tokens']:
                    if token.get('type') == 'buy' and token.get('mint'):
                        mint = token['mint']
                        print(f"   🎯 ALIM tespit edildi: {mint[:16]}...")
                        print(f"   🔍 DexScreener sorgulanıyor...")
                        
                        # Market cap kontrol (timeout ekle)
                        try:
                            mcap = await asyncio.wait_for(
                                self.get_token_mcap(mint),
                                timeout=10.0  # 10 saniye timeout
                            )
                        except asyncio.TimeoutError:
                            print(f"   ⏱️  DexScreener timeout! (10s)")
                            mcap = None
                        except Exception as e:
                            print(f"   ❌ Market cap hatası: {e}")
                            mcap = None
                        
                        if mcap:
                            print(f"   💰 Market Cap: ${mcap:,.0f}")
                            
                            if self.is_in_mcap_range(mcap):
                                print(f"   ✅ Market cap aralıkta! Bildirim gönderiliyor...")
                                await self.notify_transaction(
                                    wallet_address,
                                    parsed,
                                    token,
                                    mcap
                                )
                            else:
                                print(f"   ❌ Market cap aralık dışı (${self.min_mcap:,.0f} - ${self.max_mcap:,.0f})")
                        else:
                            print(f"   ⚠️  Market cap bulunamadı - Token: {mint}")
                            print(f"   ℹ️  Yeni token olabilir veya DexScreener'da yok")
            else:
                print(f"   ℹ️  Token değişimi yok (SOL transfer olabilir)")
                
        except Exception as e:
            print(f"❌ İşlem kontrol hatası: {e}")
    
    async def start_tracking(self):
        """WebSocket ile tracking başlat"""
        if not self.tracked_wallets:
            print("❌ Takip edilecek cüzdan eklenmedi!")
            return
        
        self.is_running = True
        print(f"\n🚀 WebSocket Tracker başlatılıyor...")
        print(f"Market Cap Aralığı: ${self.min_mcap:,.0f} - ${self.max_mcap:,.0f}")
        print(f"Takip edilen cüzdan sayısı: {len(self.tracked_wallets)}")
        print(f"Mode: WebSocket (Gerçek Zamanlı!)")
        
        # Her cüzdan için WebSocket bağlantısı
        tasks = [
            self.subscribe_to_account(wallet)
            for wallet in self.tracked_wallets
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)


async def main():
    """Test için"""
    import os
    from config import Config
    
    print("="*60)
    print("🎯 WEBSOCKET TRACKER - GERÇEK ZAMANLI TAKİP")
    print("="*60)
    
    # RPC URL kontrol
    rpc_url = Config.SOLANA_RPC_URL
    print(f"\n📡 RPC URL: {rpc_url}")
    
    # WebSocket URL'i göster
    ws_url = rpc_url.replace('https://', 'wss://').replace('http://', 'ws://')
    print(f"🔌 WebSocket URL: {ws_url}")
    
    # Public RPC uyarısı
    if 'mainnet-beta.solana.com' in rpc_url:
        print("\n⚠️  PUBLIC RPC KULLANIYORSUNUZ!")
        print("   WebSocket bağlantıları sınırlıdır.")
        print("   Daha iyi performans için Helius/QuickNode önerilir.")
    
    print("\n" + "="*60)
    
    # Tracker oluştur
    tracker = WebSocketTracker(
        rpc_url=Config.SOLANA_RPC_URL,
        min_mcap=Config.MIN_MCAP,
        max_mcap=Config.MAX_MCAP,
        poll_interval=Config.POLL_INTERVAL
    )
    
    # Cüzdanları ekle
    if Config.WALLETS:
        tracker.add_wallets(Config.get_wallets())
    else:
        print("\n❌ .env dosyasında WALLETS tanımlanmamış!")
        print("Örnek cüzdan ekleniyor...")
        # Test için örnek cüzdan
        tracker.add_wallet("7YttLkHDoNj9wyDur5pM1ejNaAvT9X4eqaYcHQqtj2G5")
    
    try:
        # WebSocket tracking başlat
        await tracker.start_tracking()
    except KeyboardInterrupt:
        print("\n\n⏹️  Tracker durduruldu")
    finally:
        await tracker.stop_tracking()
        await tracker.close()


if __name__ == "__main__":
    asyncio.run(main())

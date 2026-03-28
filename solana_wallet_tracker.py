"""
Solana Wallet Tracker - Belirli Market Cap Aralığında Token İşlemlerini Takip Eder
"""

import asyncio
import aiohttp
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from datetime import datetime
import json
from typing import List, Dict, Optional, Callable
import os


class SolanaWalletTracker:
    def __init__(
        self,
        rpc_url: str = "https://api.mainnet-beta.solana.com",
        min_mcap: float = 100000,  # Minimum market cap (USD)
        max_mcap: float = 10000000,  # Maximum market cap (USD)
        cache_duration: int = 300,  # Cache süresi (saniye)
        poll_interval: int = 10,  # Polling interval (saniye)
    ):
        self.rpc_url = rpc_url
        self.client = AsyncClient(rpc_url)
        self.min_mcap = min_mcap
        self.max_mcap = max_mcap
        self.cache_duration = cache_duration
        self.poll_interval = poll_interval
        self.tracked_wallets: List[str] = []
        self.token_cache: Dict[str, Dict] = {}
        self.transaction_callbacks: List[Callable] = []
        self.is_running = False
        
    async def close(self):
        """RPC client'ı kapat"""
        await self.client.close()
        
    def add_wallet(self, wallet_address: str):
        """Takip edilecek cüzdan ekle"""
        if wallet_address not in self.tracked_wallets:
            self.tracked_wallets.append(wallet_address)
            print(f"✓ Cüzdan eklendi: {wallet_address}")
    
    def add_wallets(self, wallet_addresses: List[str]):
        """Birden fazla cüzdan ekle"""
        for wallet in wallet_addresses:
            self.add_wallet(wallet)
    
    async def get_token_mcap(self, token_address: str) -> Optional[float]:
        """
        Token'ın market cap'ini al (örnek - gerçek uygulamada DexScreener, Jupiter vb. kullanılabilir)
        """
        # Cache kontrol
        if token_address in self.token_cache:
            cached_data = self.token_cache[token_address]
            if (datetime.now() - cached_data['timestamp']).seconds < self.cache_duration:
                return cached_data['mcap']
        
        try:
            # DexScreener API'den market cap bilgisi al
            async with aiohttp.ClientSession() as session:
                url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('pairs') and len(data['pairs']) > 0:
                            pair = data['pairs'][0]
                            mcap = float(pair.get('fdv', 0) or pair.get('marketCap', 0))
                            
                            # Cache'e kaydet
                            self.token_cache[token_address] = {
                                'mcap': mcap,
                                'timestamp': datetime.now(),
                                'name': pair.get('baseToken', {}).get('name', 'Unknown'),
                                'symbol': pair.get('baseToken', {}).get('symbol', 'Unknown')
                            }
                            return mcap
        except Exception as e:
            print(f"Market cap alınamadı {token_address}: {str(e)}")
        
        return None
    
    def is_in_mcap_range(self, mcap: Optional[float]) -> bool:
        """Market cap aralıkta mı kontrol et"""
        if mcap is None:
            return False
        return self.min_mcap <= mcap <= self.max_mcap
    
    async def get_wallet_transactions(
        self, 
        wallet_address: str, 
        limit: int = 10
    ) -> List[Dict]:
        """Cüzdan işlemlerini getir"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                pubkey = Pubkey.from_string(wallet_address)
                
                # Signatures'ları al
                signatures = await asyncio.wait_for(
                    self.client.get_signatures_for_address(pubkey, limit=limit),
                    timeout=30
                )
                
                if not signatures.value:
                    return []
                
                transactions = []
                # Her transaction'ı tek tek al (rate limit için küçük gecikme)
                for sig_info in signatures.value:
                    try:
                        tx = await asyncio.wait_for(
                            self.client.get_transaction(
                                sig_info.signature,
                                encoding="jsonParsed",
                                max_supported_transaction_version=0
                            ),
                            timeout=15
                        )
                        
                        if tx.value:
                            transactions.append({
                                'signature': str(sig_info.signature),
                                'slot': sig_info.slot,
                                'timestamp': sig_info.block_time,
                                'transaction': tx.value
                            })
                        
                        # Rate limit için küçük gecikme
                        await asyncio.sleep(0.1)
                        
                    except asyncio.TimeoutError:
                        print(f"   ⏱️  Timeout: {str(sig_info.signature)[:16]}... (RPC yanıt vermiyor)")
                        continue
                    except Exception as e:
                        print(f"   ❌ TX okunamadı {str(sig_info.signature)[:16]}...: {type(e).__name__} - {str(e)}")
                        continue
                
                return transactions
                
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    print(f"   ⚠️  RPC timeout, tekrar deneniyor ({attempt + 1}/{max_retries})...")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    print(f"❌ RPC timeout - maksimum deneme aşıldı {wallet_address[:8]}...")
                    return []
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"   ⚠️  Hata: {str(e)}, tekrar deneniyor ({attempt + 1}/{max_retries})...")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    print(f"❌ İşlemler alınamadı {wallet_address[:8]}...: {str(e)}")
                    return []
        
        return []
    
    async def parse_transaction(self, tx_data: Dict) -> Optional[Dict]:
        """İşlemi parse et ve token transferlerini çıkar"""
        try:
            tx = tx_data['transaction']
            
            if not tx.transaction.meta:
                return None
            
            # Timestamp'i direkt kullan (Unix timestamp)
            timestamp = tx_data['timestamp'] if tx_data['timestamp'] else int(datetime.now().timestamp())
            
            parsed_info = {
                'signature': tx_data['signature'],
                'timestamp': timestamp,  # Unix timestamp (int)
                'slot': tx_data['slot'],
                'success': tx.transaction.meta.err is None,
                'tokens': []
            }
            
            # Token değişikliklerini pre/post balances'dan al
            if hasattr(tx.transaction.meta, 'pre_token_balances') and hasattr(tx.transaction.meta, 'post_token_balances'):
                pre_balances = tx.transaction.meta.pre_token_balances or []
                post_balances = tx.transaction.meta.post_token_balances or []
                
                # Post balance'ları kontrol et
                for post in post_balances:
                    mint = post.mint
                    post_amount = int(post.ui_token_amount.amount)
                    decimals = post.ui_token_amount.decimals
                    
                    # Pre balance'ı bul
                    pre_amount = 0
                    for pre in pre_balances:
                        if pre.mint == mint and pre.account_index == post.account_index:
                            pre_amount = int(pre.ui_token_amount.amount)
                            break
                    
                    # Değişim varsa ekle - SADECE ALIM (BUY) işlemlerini kaydet!
                    if post_amount > pre_amount:  # SADECE ARTIŞ = BUY
                        token_info = {
                            'type': 'buy',
                            'mint': str(mint),
                            'amount': str(post_amount - pre_amount),  # Artış miktarı
                            'decimals': decimals,
                            'pre_balance': pre_amount,
                            'post_balance': post_amount
                        }
                        parsed_info['tokens'].append(token_info)
                    # SATIŞ işlemlerini tamamen atla (post_amount < pre_amount)
            
            # Alternatif: Instructions'dan parse et
            if not parsed_info['tokens'] and hasattr(tx.transaction.transaction, 'message'):
                message = tx.transaction.transaction.message
                
                if hasattr(message, 'instructions'):
                    for instruction in message.instructions:
                        if hasattr(instruction, 'parsed'):
                            parsed = instruction.parsed
                            if isinstance(parsed, dict):
                                # Token transfer kontrolü
                                if parsed.get('type') in ['transfer', 'transferChecked']:
                                    info = parsed.get('info', {})
                                    token_info = {
                                        'type': parsed.get('type'),
                                        'mint': info.get('mint'),
                                        'amount': info.get('amount') or info.get('tokenAmount', {}).get('amount'),
                                        'decimals': info.get('decimals') or info.get('tokenAmount', {}).get('decimals'),
                                        'source': info.get('source'),
                                        'destination': info.get('destination')
                                    }
                                    parsed_info['tokens'].append(token_info)
            
            return parsed_info if parsed_info['tokens'] else None
            
        except Exception as e:
            print(f"Parse hatası {tx_data.get('signature', 'unknown')}: {str(e)}")
            return None
    
    async def track_wallet(self, wallet_address: str):
        """Tek bir cüzdanı sürekli takip et"""
        print(f"\n📊 Takip ediliyor: {wallet_address}")
        last_signature = None
        first_run = True
        
        while self.is_running:
            try:
                # Son işlemleri al (limit artırıldı - daha fazla işlem tara)
                transactions = await self.get_wallet_transactions(wallet_address, limit=20)
                
                if first_run:
                    # İlk çalıştırmada sadece son signature'ı kaydet
                    if transactions:
                        last_signature = transactions[0]['signature']
                        print(f"✓ {wallet_address[:8]}...{wallet_address[-4:]} başlatıldı (son tx: {last_signature[:8]}...)")
                    first_run = False
                    # İLK ÇALIŞTIRMADA BEKLEMEDEN DEVAM ET! (hemen işlemleri kontrol et)
                    continue
                
                new_transactions = []
                for tx_data in transactions:
                    # Daha önce görülmüş mü?
                    if last_signature and tx_data['signature'] == last_signature:
                        break
                    new_transactions.append(tx_data)
                
                # Yeni işlemleri ters sırala (en eskiden en yeniye)
                new_transactions.reverse()
                
                for tx_data in new_transactions:
                    print(f"\n🔍 Yeni TX tespit edildi: {tx_data['signature'][:16]}...")
                    
                    # İşlemi parse et
                    parsed = await self.parse_transaction(tx_data)
                    
                    if parsed and parsed['tokens']:
                        print(f"   ✓ {len(parsed['tokens'])} token değişimi bulundu")
                        # Her token için market cap kontrol et
                        for token in parsed['tokens']:
                            # SADECE ALIM (İŞLEMLERİNİ YAKALA
                            if token.get('type') != 'buy':
                                print(f"   ⛔ Satış işlemi - atlanıyor (type: {token.get('type')})")
                                continue
                            
                            if token.get('mint'):
                                print(f"   🔎 Token kontrol ediliyor: {token['mint'][:16]}... (ALİM)")
                                mcap = await self.get_token_mcap(token['mint'])
                                
                                if mcap:
                                    print(f"   💰 Market Cap: ${mcap:,.0f}")
                                    if self.is_in_mcap_range(mcap):
                                        print(f"   ✅ Market cap aralıkta! Bildirim gönderiliyor...")
                                        # Bildiri göster
                                        await self.notify_transaction(
                                            wallet_address,
                                            parsed,
                                            token,
                                            mcap
                                        )
                                    else:
                                        print(f"   ❌ Market cap aralık dışı (${self.min_mcap:,.0f} - ${self.max_mcap:,.0f})")
                                else:
                                    print(f"   ⚠️  Market cap bulunamadı")
                    else:
                        print(f"   ⚠️  Token değişimi bulunamadı (swap/transfer değil)")
                
                # Son signature'ı güncelle
                if transactions:
                    last_signature = transactions[0]['signature']
                
                # Polling interval kadar bekle
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                print(f"❌ Hata oluştu {wallet_address[:8]}...{wallet_address[-4:]}: {str(e)}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(10)
    
    def add_transaction_callback(self, callback: Callable):
        """İşlem tespit edildiğinde çağrılacak callback ekle"""
        self.transaction_callbacks.append(callback)
    
    async def notify_transaction(
        self,
        wallet: str,
        tx_info: Dict,
        token_info: Dict,
        mcap: float
    ):
        """İşlem bildirimi göster"""
        token_data = self.token_cache.get(token_info['mint'], {})
        symbol = token_data.get('symbol', token_info['mint'][:8])
        name = token_data.get('name', 'Unknown')
        
        amount = int(token_info.get('amount', 0))
        decimals = int(token_info.get('decimals', 0))
        real_amount = amount / (10 ** decimals) if decimals > 0 else amount
        
        # Padre.gg trade URL
        trade_url = f"https://trade.padre.gg/trade/solana/{token_info['mint']}"
        
        # Notification data (JSON serializable) - timestamp zaten int
        notification = {
            'wallet': wallet,
            'token_address': token_info['mint'],
            'token_name': name,
            'token_symbol': symbol,
            'market_cap': mcap,
            'amount': real_amount,
            'type': 'buy',  # Sadece buy işlemleri buraya gelir
            'timestamp': tx_info['timestamp'],  # Zaten Unix timestamp (int)
            'signature': tx_info['signature'],
            'solscan_url': f"https://solscan.io/tx/{tx_info['signature']}",
            'trade_url': trade_url
        }
        
        # Console output
        print("\n" + "="*80)
        print(f"🔔 YENİ İŞLEM TESPİT EDİLDİ!")
        print(f"Cüzdan: {wallet[:8]}...{wallet[-8:]}")
        print(f"Token: {name} ({symbol})")
        print(f"Market Cap: ${mcap:,.2f}")
        print(f"Miktar: {real_amount:,.4f} {symbol}")
        print(f"Tip: {token_info['type']}")
        print(f"Zaman: {tx_info['timestamp']}")
        print(f"Signature: {tx_info['signature']}")
        print(f"Solscan: https://solscan.io/tx/{tx_info['signature']}")
        print(f"Trade: {trade_url}")
        print("="*80)
        
        # Callback'leri çağır
        for callback in self.transaction_callbacks:
            try:
                await callback(notification)
            except Exception as e:
                print(f"Callback hatası: {e}")
    
    async def start_tracking(self):
        """Tüm cüzdanları takip etmeye başla"""
        if not self.tracked_wallets:
            print("❌ Takip edilecek cüzdan eklenmedi!")
            return
        
        self.is_running = True
        print(f"\n🚀 Tracker başlatılıyor...")
        print(f"Market Cap Aralığı: ${self.min_mcap:,.0f} - ${self.max_mcap:,.0f}")
        print(f"Takip edilen cüzdan sayısı: {len(self.tracked_wallets)}")
        
        # Her cüzdan için ayrı task başlat
        tasks = [
            self.track_wallet(wallet)
            for wallet in self.tracked_wallets
        ]
        
        await asyncio.gather(*tasks)
    
    async def stop_tracking(self):
        """Tracking'i durdur"""
        self.is_running = False
        print("\n⏹️  Tracker durduruluyor...")
    
    def get_status(self) -> Dict:
        """Tracker durumunu döndür"""
        return {
            'is_running': self.is_running,
            'tracked_wallets': self.tracked_wallets,
            'min_mcap': self.min_mcap,
            'max_mcap': self.max_mcap,
            'rpc_url': self.rpc_url,
            'poll_interval': self.poll_interval,
            'cache_duration': self.cache_duration
        }


async def main():
    """Ana fonksiyon - Örnek kullanım"""
    
    # Tracker'ı oluştur
    tracker = SolanaWalletTracker(
        min_mcap=100000,      # 100K USD minimum
        max_mcap=10000000,    # 10M USD maximum
    )
    
    # Takip edilecek cüzdanları ekle (örnek cüzdanlar)
    wallets_to_track = [
        "7YttLkHDoNj9wyDur5pM1ejNaAvT9X4eqaYcHQqtj2G5",  # Örnek cüzdan 1
        "HN7cABqLq46Es1jh92dQQisAq662SmxELLLsHHe4YWrH",  # Örnek cüzdan 2
        # Buraya daha fazla cüzdan ekleyebilirsiniz
    ]
    
    tracker.add_wallets(wallets_to_track)
    
    try:
        # Takibi başlat
        await tracker.start_tracking()
    except KeyboardInterrupt:
        print("\n\n⏹️  Tracker durduruldu")
    finally:
        await tracker.close()


if __name__ == "__main__":
    # Gerekli environment variable'lar
    # RPC_URL environment variable'ı varsa kullan
    if os.getenv("SOLANA_RPC_URL"):
        print(f"Custom RPC kullanılıyor: {os.getenv('SOLANA_RPC_URL')}")
    
    asyncio.run(main())

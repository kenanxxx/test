"""
Web UI - Solana Wallet Tracker Kontrol Paneli
"""

from aiohttp import web
import aiohttp_jinja2
import jinja2
import asyncio
import os
from pathlib import Path
from datetime import datetime
from config import Config
from solana_wallet_tracker import SolanaWalletTracker
import json


class WebApp:
    def __init__(self):
        self.app = web.Application()
        self.tracker = None
        self.tracker_task = None
        self.transactions_history = []
        self.max_history = 100
        
        # Template dizini
        template_dir = Path(__file__).parent / 'templates'
        aiohttp_jinja2.setup(
            self.app,
            loader=jinja2.FileSystemLoader(str(template_dir))
        )
        
        # Routes
        self.setup_routes()
        
    def setup_routes(self):
        """Route'ları tanımla"""
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/api/status', self.get_status)
        self.app.router.add_get('/api/transactions', self.get_transactions)
        self.app.router.add_post('/api/transactions/clear', self.clear_transactions)
        self.app.router.add_post('/api/start', self.start_tracker)
        self.app.router.add_post('/api/stop', self.stop_tracker)
        self.app.router.add_post('/api/config', self.update_config)
        self.app.router.add_get('/api/config', self.get_config)
        self.app.router.add_static('/static', Path(__file__).parent / 'static')
    
    @aiohttp_jinja2.template('index.html')
    async def index(self, request):
        """Ana sayfa"""
        return {
            'config': {
                'min_mcap': Config.MIN_MCAP,
                'max_mcap': Config.MAX_MCAP,
                'wallets': Config.get_wallets(),
                'rpc_url': Config.SOLANA_RPC_URL,
                'poll_interval': Config.POLL_INTERVAL,
            }
        }
    
    async def get_status(self, request):
        """Tracker durumunu getir"""
        status = {
            'is_running': self.tracker is not None and self.tracker.is_running,
            'tracked_wallets': self.tracker.tracked_wallets if self.tracker else [],
            'transactions_count': len(self.transactions_history),
            'config': {
                'min_mcap': self.tracker.min_mcap if self.tracker else Config.MIN_MCAP,
                'max_mcap': self.tracker.max_mcap if self.tracker else Config.MAX_MCAP,
                'rpc_url': self.tracker.rpc_url if self.tracker else Config.SOLANA_RPC_URL,
                'poll_interval': self.tracker.poll_interval if self.tracker else Config.POLL_INTERVAL,
            }
        }
        return web.json_response(status)
    
    def serialize_transaction(self, tx: dict) -> dict:
        """Transaction objesini JSON serialize edilebilir hale getir"""
        serialized = tx.copy()
        
        # datetime objelerini ISO string'e çevir
        if 'timestamp' in serialized and serialized['timestamp']:
            if isinstance(serialized['timestamp'], datetime):
                serialized['timestamp'] = serialized['timestamp'].isoformat()
            elif isinstance(serialized['timestamp'], int):
                # Unix timestamp ise datetime'a çevir sonra ISO string'e
                serialized['timestamp'] = datetime.fromtimestamp(serialized['timestamp']).isoformat()
        
        if 'detected_at' in serialized and isinstance(serialized['detected_at'], datetime):
            serialized['detected_at'] = serialized['detected_at'].isoformat()
        
        return serialized
    
    async def get_transactions(self, request):
        """İşlem geçmişini getir"""
        # Son 50 işlemi serialize et
        transactions = [
            self.serialize_transaction(tx) 
            for tx in self.transactions_history[-50:][::-1]
        ]
        
        return web.json_response({
            'transactions': transactions
        })
    
    async def clear_transactions(self, request):
        """İşlem geçmişini temizle"""
        self.transactions_history = []
        return web.json_response({
            'success': True,
            'message': 'İşlem geçmişi temizlendi'
        })
    
    async def get_config(self, request):
        """Mevcut konfigürasyonu getir"""
        config = {
            'min_mcap': Config.MIN_MCAP,
            'max_mcap': Config.MAX_MCAP,
            'wallets': Config.get_wallets(),
            'rpc_url': Config.SOLANA_RPC_URL,
            'poll_interval': Config.POLL_INTERVAL,
            'cache_duration': Config.CACHE_DURATION,
        }
        return web.json_response(config)
    
    async def update_config(self, request):
        """Konfigürasyonu güncelle"""
        try:
            data = await request.json()
            
            # Tracker çalışıyorsa durdur
            if self.tracker and self.tracker.is_running:
                return web.json_response({
                    'success': False,
                    'error': 'Tracker çalışırken ayarlar değiştirilemez. Önce durdurun.'
                }, status=400)
            
            # Config'i güncelle
            if 'min_mcap' in data:
                Config.MIN_MCAP = float(data['min_mcap'])
            if 'max_mcap' in data:
                Config.MAX_MCAP = float(data['max_mcap'])
            if 'wallets' in data:
                # Wallets liste veya virgülle ayrılmış string olabilir
                wallets = data['wallets']
                if isinstance(wallets, str):
                    wallets = [w.strip() for w in wallets.split(',') if w.strip()]
                Config.WALLETS = wallets
            if 'rpc_url' in data:
                Config.SOLANA_RPC_URL = data['rpc_url']
            if 'poll_interval' in data:
                Config.POLL_INTERVAL = int(data['poll_interval'])
            
            # .env dosyasını güncelle
            self.save_env_file()
            
            return web.json_response({
                'success': True,
                'message': 'Ayarlar güncellendi'
            })
            
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=400)
    
    def save_env_file(self):
        """Config'i .env dosyasına kaydet"""
        env_path = Path(__file__).parent / '.env'
        with open(env_path, 'w') as f:
            f.write(f"SOLANA_RPC_URL={Config.SOLANA_RPC_URL}\n")
            f.write(f"MIN_MCAP={Config.MIN_MCAP}\n")
            f.write(f"MAX_MCAP={Config.MAX_MCAP}\n")
            f.write(f"WALLETS={','.join(Config.WALLETS)}\n")
            f.write(f"POLL_INTERVAL={Config.POLL_INTERVAL}\n")
            f.write(f"CACHE_DURATION={Config.CACHE_DURATION}\n")
            f.write(f"WEB_HOST={Config.WEB_HOST}\n")
            f.write(f"WEB_PORT={Config.WEB_PORT}\n")
    
    async def start_tracker(self, request):
        """Tracker'ı başlat"""
        try:
            if self.tracker and self.tracker.is_running:
                return web.json_response({
                    'success': False,
                    'error': 'Tracker zaten çalışıyor'
                }, status=400)
            
            # Yeni tracker oluştur
            self.tracker = SolanaWalletTracker(
                rpc_url=Config.SOLANA_RPC_URL,
                min_mcap=Config.MIN_MCAP,
                max_mcap=Config.MAX_MCAP,
                cache_duration=Config.CACHE_DURATION,
                poll_interval=Config.POLL_INTERVAL
            )
            
            # Cüzdanları ekle
            self.tracker.add_wallets(Config.get_wallets())
            
            # Transaction callback ekle
            self.tracker.add_transaction_callback(self.on_transaction)
            
            # Tracker'ı arka planda başlat
            self.tracker_task = asyncio.create_task(self.tracker.start_tracking())
            
            return web.json_response({
                'success': True,
                'message': 'Tracker başlatıldı'
            })
            
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    async def stop_tracker(self, request):
        """Tracker'ı durdur"""
        try:
            if not self.tracker or not self.tracker.is_running:
                return web.json_response({
                    'success': False,
                    'error': 'Tracker çalışmıyor'
                }, status=400)
            
            await self.tracker.stop_tracking()
            
            if self.tracker_task:
                self.tracker_task.cancel()
                try:
                    await self.tracker_task
                except asyncio.CancelledError:
                    pass
            
            await self.tracker.close()
            self.tracker = None
            self.tracker_task = None
            
            return web.json_response({
                'success': True,
                'message': 'Tracker durduruldu'
            })
            
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    async def on_transaction(self, notification: dict):
        """Transaction tespit edildiğinde çağrılır"""
        # Timestamp ekle
        notification['detected_at'] = datetime.now().isoformat()
        
        # History'e ekle
        self.transactions_history.append(notification)
        
        # Max history limitini kontrol et
        if len(self.transactions_history) > self.max_history:
            self.transactions_history = self.transactions_history[-self.max_history:]
    
    async def start(self):
        """Web server'ı başlat"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, Config.WEB_HOST, Config.WEB_PORT)
        await site.start()
        
        print(f"\n🌐 Web UI başlatıldı: http://{Config.WEB_HOST}:{Config.WEB_PORT}")
        print(f"📊 Tarayıcınızda açın: http://localhost:{Config.WEB_PORT}")
        
        # Eğer config'de cüzdanlar varsa otomatik başlat
        if Config.WALLETS and Config.validate():
            print("\n🚀 Otomatik başlatılıyor...")
            self.tracker = SolanaWalletTracker(
                rpc_url=Config.SOLANA_RPC_URL,
                min_mcap=Config.MIN_MCAP,
                max_mcap=Config.MAX_MCAP,
                cache_duration=Config.CACHE_DURATION,
                poll_interval=Config.POLL_INTERVAL
            )
            self.tracker.add_wallets(Config.get_wallets())
            self.tracker.add_transaction_callback(self.on_transaction)
            self.tracker_task = asyncio.create_task(self.tracker.start_tracking())


async def main():
    """Ana fonksiyon"""
    app = WebApp()
    await app.start()
    
    # Sonsuza kadar çalış
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n\n⏹️  Uygulama kapatılıyor...")
        if app.tracker:
            await app.tracker.stop_tracking()
            await app.tracker.close()


if __name__ == "__main__":
    asyncio.run(main())

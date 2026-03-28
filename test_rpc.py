"""
RPC Endpoint Test Script
Bu script RPC endpoint'inizin çalışıp çalışmadığını test eder
"""

import asyncio
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Test edilecek cüzdan
TEST_WALLET = "4VR5eVLqnqvHZASaGVyUjSY67U7hHgFAqyhAHPNK2pbs"

async def test_rpc(rpc_url: str):
    """RPC endpoint'i test et"""
    print(f"\n{'='*80}")
    print(f"RPC Test: {rpc_url}")
    print(f"{'='*80}\n")
    
    try:
        client = AsyncClient(rpc_url)
        
        # 1. Health check
        print("1️⃣ Health Check...")
        try:
            health = await asyncio.wait_for(client.get_health(), timeout=10)
            print(f"   ✅ Sağlık: {health}")
        except Exception as e:
            print(f"   ❌ Health check başarısız: {e}")
            return False
        
        # 2. Slot test
        print("\n2️⃣ Slot Test...")
        try:
            slot = await asyncio.wait_for(client.get_slot(), timeout=10)
            print(f"   ✅ Mevcut slot: {slot.value}")
        except Exception as e:
            print(f"   ❌ Slot alınamadı: {e}")
            return False
        
        # 3. Signatures test
        print(f"\n3️⃣ Cüzdan İşlemleri Test ({TEST_WALLET[:8]}...)...")
        try:
            pubkey = Pubkey.from_string(TEST_WALLET)
            signatures = await asyncio.wait_for(
                client.get_signatures_for_address(pubkey, limit=5),
                timeout=30
            )
            
            if signatures.value:
                print(f"   ✅ {len(signatures.value)} işlem bulundu")
                
                # İlk işlemi detaylı al
                first_sig = signatures.value[0]
                print(f"\n4️⃣ İşlem Detay Test ({str(first_sig.signature)[:16]}...)...")
                
                tx = await asyncio.wait_for(
                    client.get_transaction(
                        first_sig.signature,
                        encoding="jsonParsed",
                        max_supported_transaction_version=0
                    ),
                    timeout=30
                )
                
                if tx.value:
                    print(f"   ✅ İşlem detayı alındı")
                    print(f"   Slot: {tx.value.slot}")
                    print(f"   Block Time: {tx.value.block_time}")
                    
                    # Token balance değişikliklerini kontrol et
                    if hasattr(tx.value.transaction.meta, 'pre_token_balances'):
                        pre = tx.value.transaction.meta.pre_token_balances or []
                        post = tx.value.transaction.meta.post_token_balances or []
                        print(f"   Token Balances: {len(pre)} pre, {len(post)} post")
                else:
                    print(f"   ⚠️  İşlem detayı bulunamadı")
            else:
                print(f"   ⚠️  İşlem bulunamadı")
        except Exception as e:
            print(f"   ❌ İşlem testi başarısız: {type(e).__name__} - {e}")
            return False
        
        await client.close()
        
        print(f"\n{'='*80}")
        print("🎉 TÜM TESTLER BAŞARILI!")
        print(f"{'='*80}\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Genel hata: {type(e).__name__} - {e}")
        return False


async def test_multiple_rpcs():
    """Birden fazla RPC endpoint'i test et"""
    
    # .env'den RPC al
    current_rpc = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    
    rpcs = [
        ("Mevcut RPC (.env)", current_rpc),
        ("Public Solana", "https://api.mainnet-beta.solana.com"),
        ("Helius (Ücretsiz)", "https://mainnet.helius-rpc.com/?api-key=DEMO"),
    ]
    
    print("\n" + "="*80)
    print("🔍 SOLANA RPC ENDPOINT TESTİ")
    print("="*80)
    
    results = []
    for name, rpc_url in rpcs:
        success = await test_rpc(rpc_url)
        results.append((name, rpc_url, success))
        await asyncio.sleep(2)  # Rate limit için bekle
    
    # Sonuçları özet
    print("\n" + "="*80)
    print("📊 TEST SONUÇLARI")
    print("="*80 + "\n")
    
    for name, rpc_url, success in results:
        status = "✅ ÇALIŞIYOR" if success else "❌ ÇALIŞMIYOR"
        print(f"{status} - {name}")
        print(f"   URL: {rpc_url[:60]}...")
        print()
    
    # Tavsiye
    working_rpcs = [r for r in results if r[2]]
    if working_rpcs:
        print("\n💡 TAVSİYE:")
        print(f"   Çalışan RPC: {working_rpcs[0][0]}")
        print(f"   .env dosyasına ekleyin:")
        print(f"   SOLANA_RPC_URL={working_rpcs[0][1]}")
    else:
        print("\n⚠️  UYARI: Hiçbir RPC çalışmıyor!")
        print("   1. İnternet bağlantınızı kontrol edin")
        print("   2. RPC_SETUP.md dosyasını okuyun")
        print("   3. Premium RPC servisi kullanın (Helius önerilir)")


if __name__ == "__main__":
    print("\n🧪 Solana RPC Test Script")
    print("Bu script RPC endpoint'inizin çalışıp çalışmadığını test eder.\n")
    
    try:
        asyncio.run(test_multiple_rpcs())
    except KeyboardInterrupt:
        print("\n\n⏹️  Test iptal edildi")
        sys.exit(0)

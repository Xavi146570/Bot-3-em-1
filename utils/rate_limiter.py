import asyncio
import time
from datetime import datetime, timedelta
from collections import deque
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Sistema de rate limiting para controlar frequência de chamadas"""
    
    def __init__(self, max_calls: int = 20, time_window: int = 60, name: str = "RateLimiter"):
        self.max_calls = max_calls
        self.time_window = time_window
        self.name = name
        self.calls = deque()
        self.total_calls = 0
        self.total_waits = 0
        
        logger.info(f"🚦 {self.name} inicializado: {max_calls} calls/{time_window}s")
    
    async def wait_if_needed(self) -> bool:
        """Aguarda se necessário para respeitar rate limit"""
        now = time.time()
        
        # Remove chamadas antigas da janela
        while self.calls and self.calls[0] < now - self.time_window:
            self.calls.popleft()
        
        # Verifica se precisa aguardar
        if len(self.calls) >= self.max_calls:
            oldest_call = self.calls[0]
            wait_time = oldest_call + self.time_window - now
            
            if wait_time > 0:
                logger.debug(f"⏳ {self.name}: aguardando {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self.total_waits += 1
                return True
        
        # Registra a nova chamada
        self.calls.append(now)
        self.total_calls += 1
        return False
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do rate limiter"""
        now = time.time()
        current_calls = sum(1 for call_time in self.calls if call_time > now - self.time_window)
        
        return {
            "name": self.name,
            "current_calls": current_calls,
            "max_calls": self.max_calls,
            "total_calls": self.total_calls,
            "total_waits": self.total_waits
        }

# Teste do rate limiter
async def test_rate_limiter():
    """Testa o funcionamento do rate limiter"""
    print("🧪 Testando Rate Limiter...")
    
    rl = RateLimiter(max_calls=3, time_window=5, name="Teste")
    start_time = time.time()
    
    for i in range(6):
        print(f"📞 Chamada {i+1}")
        waited = await rl.wait_if_needed()
        if waited:
            print(f"   ⏳ Aguardou rate limit")
        
        elapsed = time.time() - start_time
        print(f"   ⏰ Tempo: {elapsed:.2f}s")
        
        if i < 5:
            await asyncio.sleep(0.5)
    
    stats = rl.get_stats()
    print(f"\n📊 Estatísticas: {stats}")

if __name__ == "__main__":
    asyncio.run(test_rate_limiter())


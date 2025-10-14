import asyncio
import aiohttp
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class KeepAlive:
    """Mantém o serviço acordado no Render Free"""
    
    def __init__(self):
        self.url = "https://bot-3-em-1.onrender.com/health"
        self.interval = 840  # 14 minutos (antes dos 15min de sleep)
        self.running = False
    
    async def ping_self(self):
        """Ping interno para evitar sleep"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, timeout=10) as response:
                    if response.status == 200:
                        logger.info("✅ Keep-alive: Serviço mantido acordado")
                        return True
        except Exception as e:
            logger.warning(f"⚠️ Keep-alive falhou: {e}")
        return False
    
    async def start(self):
        """Inicia loop de keep-alive"""
        self.running = True
        logger.info(f"🔄 Keep-alive ativo (ping a cada {self.interval//60} min)")
        
        # Aguardar 2 minutos antes do primeiro ping (dar tempo para inicializar)
        await asyncio.sleep(120)
        
        while self.running:
            await self.ping_self()
            await asyncio.sleep(self.interval)
    
    def stop(self):
        """Para keep-alive"""
        self.running = False

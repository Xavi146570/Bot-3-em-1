import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import TelegramError, RetryAfter, BadRequest, Forbidden
from config import Config
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class TelegramClientError(Exception):
    """Exceção customizada para erros do cliente Telegram"""
    pass

class TelegramClient:
    """Cliente Telegram unificado com rate limiting e tratamento de erros"""
    
    def __init__(self):
        if not Config.TELEGRAM_BOT_TOKEN:
            raise TelegramClientError("TELEGRAM_BOT_TOKEN não configurado")
        
        self.bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
        self.rate_limiter = RateLimiter(
            max_calls=Config.TELEGRAM_RATE_LIMIT_CALLS,
            time_window=Config.TELEGRAM_RATE_LIMIT_WINDOW,
            name="Telegram"
        )
        
        # Estatísticas
        self.messages_sent = 0
        self.messages_failed = 0
        self.start_time = datetime.now()
        
        logger.info("🤖 Cliente Telegram inicializado")
    
    async def verify_connection(self) -> bool:
        """Verifica se o bot está conectado corretamente"""
        try:
            bot_info = await self.bot.get_me()
            logger.info(f"✅ Bot conectado: @{bot_info.username} ({bot_info.first_name})")
            return True
        except Exception as e:
            logger.error(f"❌ Erro na conexão: {e}")
            return False
    
    async def send_message(self, chat_id: str, message: str, 
                          parse_mode: str = 'HTML',
                          disable_preview: bool = True,
                          max_retries: int = 3) -> bool:
        """Envia mensagem com rate limiting e retry automático"""
        
        if not chat_id or not message:
            logger.warning("Chat ID ou mensagem vazios")
            return False
        
        if Config.DRY_RUN:
            logger.info(f"[DRY RUN] Mensagem para {chat_id}:\n{message[:200]}...")
            return True
        
        # Truncar mensagem se muito longa
        if len(message) > 4096:
            message = message[:4090] + "..."
            logger.warning("Mensagem truncada por exceder limite do Telegram")
        
        for attempt in range(max_retries):
            try:
                # Rate limiting
                await self.rate_limiter.wait_if_needed()
                
                # Enviar mensagem
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_preview
                )
                
                self.messages_sent += 1
                logger.info(f"📨 Mensagem enviada para {chat_id}")
                return True
                
            except RetryAfter as e:
                wait_time = e.retry_after + 1
                logger.warning(f"⏳ Rate limit Telegram: aguardando {wait_time}s")
                await asyncio.sleep(wait_time)
                continue
                
            except BadRequest as e:
                logger.error(f"❌ Erro de formato para {chat_id}: {e}")
                self.messages_failed += 1
                return False
                
            except Forbidden as e:
                logger.error(f"🚫 Bot sem permissão no chat {chat_id}: {e}")
                self.messages_failed += 1
                return False
                
            except TelegramError as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"⚠️ Erro Telegram (tentativa {attempt + 1}): {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ Falha final para {chat_id}: {e}")
                    self.messages_failed += 1
                    return False
        
        return False
    
    async def send_admin_message(self, message: str) -> bool:
        """Envia mensagem para o administrador"""
        if not Config.ADMIN_CHAT_ID:
            return False
        
        admin_message = f"🚨 ADMIN: {message}"
        return await self.send_message(Config.ADMIN_CHAT_ID, admin_message)
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cliente"""
        uptime = datetime.now() - self.start_time
        
        return {
            "uptime_seconds": uptime.total_seconds(),
            "messages_sent": self.messages_sent,
            "messages_failed": self.messages_failed,
            "success_rate": (self.messages_sent / (self.messages_sent + self.messages_failed) * 100) 
                           if (self.messages_sent + self.messages_failed) > 0 else 0
        }

# Teste do cliente
async def test_telegram_client():
    """Testa o cliente Telegram"""
    try:
        print("🧪 Testando Cliente Telegram...")
        
        client = TelegramClient()
        
        # Testar conexão
        connected = await client.verify_connection()
        if not connected:
            print("❌ Falha na conexão")
            return False
        
        # Testar mensagem admin se configurado
        if Config.ADMIN_CHAT_ID:
            test_message = "🧪 Teste de conexão do Bot Futebol Consolidado"
            success = await client.send_message(Config.ADMIN_CHAT_ID, test_message)
            
            if success:
                print("✅ Mensagem de teste enviada")
            else:
                print("❌ Falha ao enviar mensagem")
        
        # Mostrar estatísticas
        stats = client.get_stats()
        print(f"📊 Estatísticas: {stats}")
        
        return True
        
    except Exception as e:
        print(f"💥 Erro no teste: {e}")
        return False

if __name__ == "__main__":
    from config import setup_logging, Config
    
    setup_logging()
    
    try:
        Config.validate()
        asyncio.run(test_telegram_client())
    except Exception as e:
        print(f"❌ Erro: {e}")


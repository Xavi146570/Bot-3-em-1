import httpx
import logging
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

class TelegramClient:
    """Cliente Telegram otimizado para envio de mensagens"""
    
    def __init__(self, token: str):
        """
        Inicializa o cliente Telegram
        
        Args:
            token (str): Token do bot do Telegram
        """
        if not token:
            raise ValueError("Token do Telegram é obrigatório")
        
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        
        logger.info("📱 TelegramClient inicializado")
    
    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """
        Envia mensagem para um chat específico
        
        Args:
            chat_id (str): ID do chat
            text (str): Texto da mensagem
            parse_mode (str): Modo de parsing (HTML ou Markdown)
            
        Returns:
            bool: True se enviado com sucesso
        """
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        logger.info(f"📨 Mensagem enviada para {chat_id}")
                        return True
                    else:
                        error_description = result.get("description", "Erro desconhecido")
                        logger.error(f"❌ Erro de formato para {chat_id}: {error_description}")
                        return False
                else:
                    logger.error(f"❌ Erro HTTP {response.status_code} para {chat_id}")
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"❌ Timeout ao enviar mensagem para {chat_id}")
            return False
        except httpx.RequestError as e:
            logger.error(f"❌ Erro de rede ao enviar mensagem para {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro crítico ao enviar mensagem para {chat_id}: {e}")
            return False
    
    async def send_admin_message(self, text: str) -> bool:
        """
        Envia mensagem para o chat de administração
        
        Args:
            text (str): Texto da mensagem
            
        Returns:
            bool: True se enviado com sucesso
        """
        # Tentar ADMIN_CHAT_ID primeiro, depois fallback para CHAT_ID_ELITE
        admin_chat_id = getattr(Config, 'ADMIN_CHAT_ID', None)
        if not admin_chat_id:
            admin_chat_id = getattr(Config, 'CHAT_ID_ELITE', None)
        
        if not admin_chat_id:
            logger.error("❌ Nenhum chat de admin configurado (ADMIN_CHAT_ID ou CHAT_ID_ELITE)")
            return False
        
        logger.debug(f"📨 Enviando mensagem de admin para {admin_chat_id}")
        return await self.send_message(admin_chat_id, text)
    
    async def test_connection(self) -> bool:
        """
        Testa a conexão com a API do Telegram
        
        Returns:
            bool: True se conexão OK
        """
        try:
            url = f"{self.base_url}/getMe"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        bot_info = result.get("result", {})
                        bot_name = bot_info.get("first_name", "Bot")
                        logger.info(f"✅ Conexão Telegram OK - Bot: {bot_name}")
                        return True
                    else:
                        logger.error("❌ Resposta da API Telegram inválida")
                        return False
                else:
                    logger.error(f"❌ Erro na conexão Telegram: HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Erro ao testar conexão Telegram: {e}")
            return False

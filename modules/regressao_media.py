import logging
from datetime import datetime
from config import Config
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from data.leagues_config import REGRESSAO_LEAGUES

logger = logging.getLogger(__name__)

class RegressaoMediaModule:
    """Módulo para detectar oportunidades de regressão à média"""
    
    def __init__(self, telegram_client: TelegramClient, api_client: ApiFootballClient):
        self.telegram_client = telegram_client
        self.api_client = api_client
        self.allowed_leagues = REGRESSAO_LEAGUES
        logger.info(f"Módulo Regressão inicializado com {len(self.allowed_leagues)} ligas")

    async def execute(self):
        """Executa o monitoramento de regressão à média"""
        if not Config.REGRESSAO_ENABLED:
            return
        
        logger.info("Executando módulo Regressão à Média...")
        
        # A lógica completa será implementada no Passo 3
        
        await self.telegram_client.send_admin_message("Módulo Regressão executado (esqueleto)")
        logger.info("Módulo Regressão concluído")


# integrations/botscore_integration.py
import logging
import os
from supabase import create_client, Client
from datetime import datetime

logger = logging.getLogger(__name__)

class BotScoreProIntegration:
    """Integração com Supabase para envio de oportunidades"""
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        self.client: Client = None
        
        if not self.supabase_url or not self.supabase_key:
            logger.error("❌ SUPABASE_URL ou SUPABASE_SERVICE_KEY não configurados")
            return
        
        try:
            self.client = create_client(self.supabase_url, self.supabase_key)
            logger.info("✅ BotScoreProIntegration inicializado com sucesso")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar Supabase client: {e}")
    
    def send_opportunity(self, opportunity_data: dict) -> bool:
        """
        Envia oportunidade para Supabase
        
        Args:
            opportunity_data: dict com campos obrigatórios:
                - bot_name (str): "elite", "regressao", "campeonatos", "santo_graal"
                - match_info (str): "Time Casa vs Time Fora"
                - league (str): Nome da liga
                - market (str): Mercado de aposta
                - odd (float): Odd decimal
                - confidence (int): 0-100
                - status (str): "pre-match", "live", "finished"
                - match_date (str): ISO 8601 format
                - analysis (str): Análise detalhada (opcional)
        
        Returns:
            bool: True se sucesso, False se erro
        """
        if not self.client:
            logger.error("❌ Supabase client não inicializado")
            return False
        
        # Validar campos obrigatórios
        required_fields = ['bot_name', 'match_info', 'league', 'market', 'odd', 'confidence', 'status', 'match_date']
        missing = [f for f in required_fields if f not in opportunity_data]
        
        if missing:
            logger.error(f"❌ Campos obrigatórios faltando: {missing}")
            return False
        
        # Log do payload para debug
        logger.info(f"📤 Enviando para Supabase: bot_name={opportunity_data['bot_name']}, match={opportunity_data['match_info']}")
        
        try:
            # Inserir no Supabase
            response = self.client.table('opportunities').insert(opportunity_data).execute()
            
            if response.data:
                logger.info(f"✅ Oportunidade enviada ao Supabase: {opportunity_data['match_info']}")
                return True
            else:
                logger.error(f"❌ Resposta vazia do Supabase: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar para Supabase: {e}")
            logger.error(f"   Payload: {opportunity_data}")
            return False

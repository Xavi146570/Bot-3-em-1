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
    
    def test_connection(self) -> bool:
        """
        Testa a conexão com Supabase fazendo uma query simples
        
        Returns:
            bool: True se conexão OK, False se erro
        """
        if not self.client:
            logger.error("❌ Supabase client não inicializado")
            return False
        
        try:
            # Tentar fazer SELECT na tabela opportunities (limit 1 para ser rápido)
            response = self.client.table('opportunities').select("id").limit(1).execute()
            logger.info("✅ Conexão com Supabase OK")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao testar conexão Supabase: {e}")
            return False
    
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
            logger.error(f"   Payload recebido: {opportunity_data}")
            return False
        
        # Validar tipos
        try:
            # Garantir que odd é float
            opportunity_data['odd'] = float(opportunity_data['odd'])
            
            # Garantir que confidence é int
            opportunity_data['confidence'] = int(opportunity_data['confidence'])
            
            # Validar confidence range
            if not (0 <= opportunity_data['confidence'] <= 100):
                logger.error(f"❌ Confidence fora do range (0-100): {opportunity_data['confidence']}")
                return False
            
            # Validar bot_name
            valid_bots = ['elite', 'regressao', 'campeonatos', 'santo_graal']
            if opportunity_data['bot_name'] not in valid_bots:
                logger.warning(f"⚠️ bot_name '{opportunity_data['bot_name']}' não está na lista recomendada: {valid_bots}")
            
            # Validar status
            valid_status = ['pre-match', 'live', 'finished', 'pending', 'active', 'won', 'lost', 'cancelled']
            if opportunity_data['status'] not in valid_status:
                logger.warning(f"⚠️ status '{opportunity_data['status']}' não está na lista válida: {valid_status}")
        
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Erro na validação de tipos: {e}")
            return False
        
        # Log do payload para debug
        logger.info(f"📤 Enviando para Supabase:")
        logger.info(f"   bot_name: {opportunity_data['bot_name']}")
        logger.info(f"   match: {opportunity_data['match_info']}")
        logger.info(f"   league: {opportunity_data['league']}")
        logger.info(f"   market: {opportunity_data['market']}")
        logger.info(f"   odd: {opportunity_data['odd']}")
        logger.info(f"   confidence: {opportunity_data['confidence']}%")
        logger.info(f"   status: {opportunity_data['status']}")
        
        try:
            # Inserir no Supabase
            response = self.client.table('opportunities').insert(opportunity_data).execute()
            
            if response.data:
                logger.info(f"✅ Oportunidade enviada ao Supabase com sucesso!")
                logger.info(f"   ID: {response.data[0].get('id', 'N/A')}")
                return True
            else:
                logger.error(f"❌ Resposta vazia do Supabase")
                logger.error(f"   Response: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar para Supabase: {e}")
            logger.error(f"   Tipo do erro: {type(e).__name__}")
            logger.error(f"   Payload completo: {opportunity_data}")
            return False

"""
Integração com Supabase para enviar oportunidades detectadas pelos bots
para o app ScorePro em tempo real
"""

import os
import logging
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class BotScoreProIntegration:
    """Classe para integração dos bots de futebol com o app ScorePro via Supabase"""
    
    def __init__(self):
        """Inicializa conexão com Supabase"""
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            logger.error("❌ SUPABASE_URL ou SUPABASE_SERVICE_KEY não configurados!")
            self.supabase = None
            return
        
        try:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("✅ Conexão com Supabase estabelecida")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar com Supabase: {e}")
            self.supabase = None
    
    def send_opportunity(self, opportunity_data: dict) -> bool:
        """
        Envia uma oportunidade detectada para o Supabase
        
        Args:
            opportunity_data (dict): Dados da oportunidade com os campos:
                - bot_name (str): Nome do bot que detectou
                - match_info (str): Informação do jogo (ex: "Manchester City vs Liverpool")
                - league (str): Nome da liga/competição
                - market (str): Mercado recomendado (ex: "Over 2.5 Goals")
                - odd (float): Odd estimada
                - confidence (int): Confiança 0-100
                - status (str): 'pre-match' ou 'live'
                - match_date (str, opcional): Data/hora do jogo (ISO format)
                - analysis (str, opcional): Análise detalhada
        
        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        
        if not self.supabase:
            logger.warning("⚠️ Supabase não disponível - oportunidade não enviada")
            return False
        
        try:
            # Validar campos obrigatórios
            required_fields = ['bot_name', 'match_info', 'league', 'market', 'odd', 'confidence']
            missing_fields = [field for field in required_fields if field not in opportunity_data]
            
            if missing_fields:
                logger.error(f"❌ Campos obrigatórios faltando: {missing_fields}")
                return False
            
            # Preparar dados para inserção
            data_to_insert = {
                'bot_name': opportunity_data['bot_name'],
                'match_info': opportunity_data['match_info'],
                'league': opportunity_data['league'],
                'market': opportunity_data['market'],
                'odd': float(opportunity_data['odd']),
                'confidence': int(opportunity_data['confidence']),
                'status': opportunity_data.get('status', 'pre-match'),
                'match_date': opportunity_data.get('match_date'),
                'analysis': opportunity_data.get('analysis'),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Inserir no Supabase
            result = self.supabase.table('opportunities').insert(data_to_insert).execute()
# O supabase-py já retorna os dados por padrão, mas verifique se há erro silencioso
if hasattr(result, 'error') and result.error:
    logger.error(f"Erro do Supabase: {result.error}")
            
            if result.data:
                logger.info(f"✅ Oportunidade enviada: {opportunity_data['match_info']} ({opportunity_data['market']})")
                return True
            else:
                logger.error(f"❌ Falha ao enviar oportunidade: sem dados retornados")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar oportunidade para Supabase: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Testa a conexão com o Supabase"""
        if not self.supabase:
            logger.error("❌ Supabase não inicializado")
            return False
        
        try:
            # Tentar fazer uma query simples
            result = self.supabase.table('opportunities').select("id").limit(1).execute()
            logger.info("✅ Teste de conexão com Supabase: OK")
            return True
        except Exception as e:
            logger.error(f"❌ Teste de conexão com Supabase falhou: {e}")
            return False


# Teste standalone (executar com: python PYTHON_BOT_EXAMPLE.py)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Testando integração com Supabase...\n")
    
    # Inicializar
    integration = BotScoreProIntegration()
    
    # Testar conexão
    if integration.test_connection():
        print("✅ Conexão OK!\n")
        
        # Enviar oportunidade de teste
        test_opportunity = {
            'bot_name': 'Bot Teste',
            'match_info': 'Manchester City vs Liverpool',
            'league': 'Premier League',
            'market': 'Over 2.5 Goals',
            'odd': 1.85,
            'confidence': 85,
            'status': 'pre-match',
            'match_date': datetime.utcnow().isoformat(),
            'analysis': 'Teste de integração - ambas equipes com média alta de gols'
        }
        
        print("📤 Enviando oportunidade de teste...")
        success = integration.send_opportunity(test_opportunity)
        
        if success:
            print("✅ Oportunidade de teste enviada com sucesso!")
            print("\n🎉 Integração funcionando perfeitamente!")
        else:
            print("❌ Falha ao enviar oportunidade de teste")
    else:
        print("❌ Falha na conexão com Supabase")
        print("\n⚠️ Verifique se as variáveis de ambiente estão configuradas:")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_SERVICE_KEY")

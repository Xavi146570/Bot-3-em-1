import os
import json
import logging
from typing import Dict, Optional, List
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """Exceção customizada para erros de configuração"""
    pass

class Config:
    """Sistema de configuração centralizado com validação completa"""
    
    # ==========================================
    # TOKENS E APIS (OBRIGATÓRIOS)
    # ==========================================
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
    LIVESCORE_API_KEY = os.getenv("LIVESCORE_API_KEY", API_FOOTBALL_KEY)
    
    # ==========================================
    # CHAT IDS
    # ==========================================
    CHAT_ID_ELITE = os.getenv("CHAT_ID_ELITE")
    CHAT_ID_REGRESSAO = os.getenv("CHAT_ID_REGRESSAO")
    CHAT_ID_CAMPEONATOS = os.getenv("CHAT_ID_CAMPEONATOS")
    ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
    
    # Mapeamento JSON para campeonatos específicos
    TELEGRAM_CHAT_MAP = os.getenv("TELEGRAM_CHAT_MAP", "{}")
    
    # ==========================================
    # CONFIGURAÇÕES MÓDULO ELITE
    # ==========================================
    ELITE_ENABLED = os.getenv("ELITE_ENABLED", "true").lower() == "true"
    ELITE_GOALS_THRESHOLD = float(os.getenv("ELITE_GOALS_THRESHOLD", "2.3"))
    ELITE_INTERVAL_HOURS = int(os.getenv("ELITE_INTERVAL_HOURS", "24"))
    
    # ==========================================
    # CONFIGURAÇÕES MÓDULO REGRESSÃO
    # ==========================================
    REGRESSAO_ENABLED = os.getenv("REGRESSAO_ENABLED", "true").lower() == "true"
    MAX_LAST_MATCH_AGE_DAYS = int(os.getenv("MAX_LAST_MATCH_AGE_DAYS", "10"))
    REGRESSAO_INTERVAL_MINUTES = int(os.getenv("REGRESSAO_INTERVAL_MINUTES", "30"))
    REGRESSAO_ACTIVE_HOURS_START = int(os.getenv("REGRESSAO_ACTIVE_HOURS_START", "8"))
    REGRESSAO_ACTIVE_HOURS_END = int(os.getenv("REGRESSAO_ACTIVE_HOURS_END", "23"))
    
    # ==========================================
    # CONFIGURAÇÕES MÓDULO CAMPEONATOS
    # ==========================================
    CAMPEONATOS_ENABLED = os.getenv("CAMPEONATOS_ENABLED", "true").lower() == "true"
    ENABLE_REAL_LEAGUE_STATS = os.getenv("ENABLE_REAL_LEAGUE_STATS", "true").lower() == "true"
    ENABLE_HT_ANALYSIS = os.getenv("ENABLE_HT_ANALYSIS", "true").lower() == "true"
    SHOW_PEAK_MINUTES = os.getenv("SHOW_PEAK_MINUTES", "true").lower() == "true"
    SHOW_LEAGUE_STATS = os.getenv("SHOW_LEAGUE_STATS", "true").lower() == "true"
    
    # ==========================================
    # CONFIGURAÇÕES TÉCNICAS
    # ==========================================
    PORT = int(os.getenv("PORT", "8080"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    MAX_API_REQUESTS = int(os.getenv("MAX_API_REQUESTS", "200"))
    API_REQUEST_DELAY = float(os.getenv("API_REQUEST_DELAY", "0.7"))
    
    # Rate limiting Telegram
    TELEGRAM_RATE_LIMIT_CALLS = int(os.getenv("TELEGRAM_RATE_LIMIT_CALLS", "20"))
    TELEGRAM_RATE_LIMIT_WINDOW = int(os.getenv("TELEGRAM_RATE_LIMIT_WINDOW", "60"))
    
    # Desenvolvimento e Debug
    DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
    DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
    
    @classmethod
    def validate(cls):
        """Valida todas as configurações obrigatórias"""
        errors = []
        warnings = []
        
        # ===== VALIDAÇÕES OBRIGATÓRIAS =====
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN é obrigatório")
        
        if not cls.API_FOOTBALL_KEY:
            errors.append("API_FOOTBALL_KEY é obrigatório")
        
        # ===== VALIDAÇÃO DE CHATS =====
        chat_ids = [cls.CHAT_ID_ELITE, cls.CHAT_ID_REGRESSAO, cls.CHAT_ID_CAMPEONATOS]
        valid_chats = [chat for chat in chat_ids if chat and chat.strip()]
        chat_map = cls.get_chat_map()
        
        if not valid_chats and not chat_map:
            errors.append("Configure pelo menos um CHAT_ID ou TELEGRAM_CHAT_MAP")
        
        # ===== VALIDAÇÕES DE VALORES =====
        if not (0 <= cls.ELITE_GOALS_THRESHOLD <= 10):
            errors.append("ELITE_GOALS_THRESHOLD deve estar entre 0 e 10")
        
        if not (1 <= cls.MAX_LAST_MATCH_AGE_DAYS <= 30):
            errors.append("MAX_LAST_MATCH_AGE_DAYS deve estar entre 1 e 30")
        
        if not (0 <= cls.REGRESSAO_ACTIVE_HOURS_START <= 23):
            errors.append("REGRESSAO_ACTIVE_HOURS_START deve estar entre 0 e 23")
        
        if not (0 <= cls.REGRESSAO_ACTIVE_HOURS_END <= 23):
            errors.append("REGRESSAO_ACTIVE_HOURS_END deve estar entre 0 e 23")
        
        if cls.REGRESSAO_ACTIVE_HOURS_START >= cls.REGRESSAO_ACTIVE_HOURS_END:
            errors.append("REGRESSAO_ACTIVE_HOURS_START deve ser menor que END")
        
        # ===== VALIDAÇÃO DO CHAT MAP =====
        try:
            cls.get_chat_map()
        except json.JSONDecodeError:
            errors.append("TELEGRAM_CHAT_MAP deve ser um JSON válido")
        
        # ===== LANÇAR ERROS =====
        if errors:
            error_msg = "❌ ERROS DE CONFIGURAÇÃO:\n" + "\n".join([f"  • {error}" for error in errors])
            if warnings:
                error_msg += "\n\n⚠️ AVISOS:\n" + "\n".join([f"  • {warning}" for warning in warnings])
            raise ConfigError(error_msg)
        
        if warnings:
            warning_msg = "⚠️ AVISOS:\n" + "\n".join([f"  • {warning}" for warning in warnings])
            print(warning_msg)
    
    @classmethod
    def get_chat_map(cls) -> Dict[str, str]:
        """Retorna mapeamento de chats por liga"""
        try:
            chat_map = json.loads(cls.TELEGRAM_CHAT_MAP)
            return chat_map if isinstance(chat_map, dict) else {}
        except:
            return {}
    
    @classmethod
    def get_enabled_modules(cls) -> Dict[str, Dict]:
        """Retorna módulos habilitados com suas configurações"""
        modules = {}
        
        if cls.ELITE_ENABLED and cls.CHAT_ID_ELITE:
            modules["elite"] = {
                "enabled": True,
                "chat_id": cls.CHAT_ID_ELITE,
                "threshold": cls.ELITE_GOALS_THRESHOLD,
                "interval_hours": cls.ELITE_INTERVAL_HOURS
            }
        
        if cls.REGRESSAO_ENABLED and cls.CHAT_ID_REGRESSAO:
            modules["regressao"] = {
                "enabled": True,
                "chat_id": cls.CHAT_ID_REGRESSAO,
                "max_days": cls.MAX_LAST_MATCH_AGE_DAYS,
                "interval_minutes": cls.REGRESSAO_INTERVAL_MINUTES,
                "active_hours": f"{cls.REGRESSAO_ACTIVE_HOURS_START}-{cls.REGRESSAO_ACTIVE_HOURS_END}"
            }
        
        if cls.CAMPEONATOS_ENABLED and (cls.CHAT_ID_CAMPEONATOS or cls.get_chat_map()):
            modules["campeonatos"] = {
                "enabled": True,
                "chat_id": cls.CHAT_ID_CAMPEONATOS,
                "chat_map": cls.get_chat_map(),
                "real_stats": cls.ENABLE_REAL_LEAGUE_STATS,
                "ht_analysis": cls.ENABLE_HT_ANALYSIS
            }
        
        return modules
    
    @classmethod
    def print_summary(cls):
        """Imprime resumo detalhado da configuração"""
        enabled_modules = cls.get_enabled_modules()
        
        print("\n" + "="*60)
        print("🚀 BOT FUTEBOL CONSOLIDADO - CONFIGURAÇÃO")
        print("="*60)
        
        print("🔑 CREDENCIAIS:")
        print(f"   📱 Telegram Token: {'✅ Configurado' if cls.TELEGRAM_BOT_TOKEN else '❌ Faltando'}")
        print(f"   ⚽ API Football: {'✅ Configurado' if cls.API_FOOTBALL_KEY else '❌ Faltando'}")
        
        print(f"\n📦 MÓDULOS HABILITADOS ({len(enabled_modules)}):")
        if not enabled_modules:
            print("   ❌ Nenhum módulo habilitado")
        else:
            for name, config in enabled_modules.items():
                print(f"   ✅ {name.upper()}")
                if name == "elite":
                    print(f"      🎯 Threshold: {config['threshold']} gols")
                    print(f"      ⏰ Intervalo: {config['interval_hours']}h")
                elif name == "regressao":
                    print(f"      📅 Max dias: {config['max_days']}")
                    print(f"      ⏰ Intervalo: {config['interval_minutes']}min")
                    print(f"      🕐 Horário ativo: {config['active_hours']}")
                elif name == "campeonatos":
                    print(f"      📊 Stats reais: {'✅' if config['real_stats'] else '❌'}")
                    print(f"      🕐 Análise HT: {'✅' if config['ht_analysis'] else '❌'}")
        
        print(f"\n⚙️ CONFIGURAÇÕES TÉCNICAS:")
        print(f"   🌐 Porta: {cls.PORT}")
        print(f"   📈 Max API Requests: {cls.MAX_API_REQUESTS}")
        print(f"   ⏱️ API Delay: {cls.API_REQUEST_DELAY}s")
        print(f"   🔧 Debug: {'✅' if cls.DEBUG_MODE else '❌'}")
        print(f"   🧪 Dry Run: {'✅' if cls.DRY_RUN else '❌'}")
        
        print("="*60)

def setup_logging():
    """Configura sistema de logging"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Reduzir verbosidade de bibliotecas externas
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)

def test_config():
    """Função de teste da configuração"""
    try:
        print("🔍 Testando configuração...")
        Config.validate()
        Config.print_summary()
        print("\n✅ CONFIGURAÇÃO VÁLIDA!")
        return True
    except ConfigError as e:
        print(f"\n{e}")
        return False
    except Exception as e:
        print(f"\n💥 ERRO INESPERADO: {e}")
        return False

if __name__ == "__main__":
    setup_logging()
    success = test_config()
    
    if not success:
        print("\n📝 DICAS PARA CORRIGIR:")
        print("1. Copie .env.example para .env")
        print("2. Edite .env com suas credenciais reais")
        print("3. Execute novamente: python config.py")
        exit(1)


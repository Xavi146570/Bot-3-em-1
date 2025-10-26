import os
from typing import Optional

def _getenv_bool(key: str, default: bool = False) -> bool:
    """Parse robusto de variáveis booleanas"""
    val = os.getenv(key)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "t", "yes", "y", "on")

def _getenv_int(key: str, default: int) -> int:
    """Parse robusto de variáveis inteiras"""
    val = os.getenv(key)
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(str(val).strip())
    except ValueError:
        return default

def _getenv_float(key: str, default: float) -> float:
    """Parse robusto de variáveis float (suporta vírgula decimal)"""
    val = os.getenv(key)
    if val is None or str(val).strip() == "":
        return default
    try:
        return float(str(val).strip().replace(",", "."))
    except ValueError:
        return default

class Config:
    """
    Configurações centralizadas do Bot Futebol Consolidado
    Otimizado para conta paga com quota diária de 2000 requests
    """
    
    # ============================================================
    # 🔑 CREDENCIAIS OBRIGATÓRIAS
    # ============================================================
    
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    API_FOOTBALL_KEY: str = os.getenv('API_FOOTBALL_KEY', '')
    
    # ============================================================
    # 💬 CONFIGURAÇÕES DO TELEGRAM
    # ============================================================
    
    # Chat IDs - usar o mesmo ID correto para todos por simplicidade
    CHAT_ID_ELITE: str = os.getenv('CHAT_ID_ELITE', '')
    CHAT_ID_REGRESSAO: str = os.getenv('CHAT_ID_REGRESSAO', '') or CHAT_ID_ELITE
    CHAT_ID_CAMPEONATOS: str = os.getenv('CHAT_ID_CAMPEONATOS', '') or CHAT_ID_ELITE
    ADMIN_CHAT_ID: str = os.getenv('ADMIN_CHAT_ID', '') or CHAT_ID_ELITE
    
    # ============================================================
    # 🔧 MÓDULOS HABILITADOS
    # ============================================================
    
    ELITE_ENABLED: bool = _getenv_bool('ELITE_ENABLED', True)
    REGRESSAO_ENABLED: bool = _getenv_bool('REGRESSAO_ENABLED', True)
    CAMPEONATOS_ENABLED: bool = _getenv_bool('CAMPEONATOS_ENABLED', True)
    
    # ============================================================
    # 🌟 CONFIGURAÇÕES DO MÓDULO ELITE
    # ============================================================
    
    # Threshold mínimo de gols por jogo para considerar "elite"
    ELITE_GOALS_THRESHOLD: float = _getenv_float('ELITE_GOALS_THRESHOLD', 2.3)
    
    # Quantos dias à frente procurar (1 = apenas hoje)
    ELITE_DAYS_AHEAD: int = _getenv_int('ELITE_DAYS_AHEAD', 1)
    
    # ============================================================
    # 📈 CONFIGURAÇÕES DO MÓDULO REGRESSÃO À MÉDIA
    # ============================================================
    
    # Horário ativo em Lisboa (24h format)
    REGRESSAO_ACTIVE_HOURS_START: int = _getenv_int('REGRESSAO_ACTIVE_HOURS_START', 8)
    REGRESSAO_ACTIVE_HOURS_END: int = _getenv_int('REGRESSAO_ACTIVE_HOURS_END', 23)
    
    # Idade máxima do último jogo para considerar na análise (dias)
    MAX_LAST_MATCH_AGE_DAYS: int = _getenv_int('MAX_LAST_MATCH_AGE_DAYS', 10)
    
    # ============================================================
    # 🏆 CONFIGURAÇÕES DO MÓDULO CAMPEONATOS
    # ============================================================
    
    # Confiança mínima para enviar alerta (1-4)
    CAMPEONATOS_MIN_CONFIDENCE: int = _getenv_int('CAMPEONATOS_MIN_CONFIDENCE', 2)
    
    # ============================================================
    # 🔧 CONFIGURAÇÕES DA API
    # ============================================================
    
    # Limite diário de requests para este bot (de 7500 totais da conta)
    API_DAILY_LIMIT: int = _getenv_int('API_DAILY_LIMIT', 2000)
    
    # Threshold para avisos (75% do limite)
    API_WARNING_THRESHOLD: float = _getenv_float('API_WARNING_THRESHOLD', 0.75)
    
    # Threshold para bloqueio preventivo (95% do limite)
    API_BLOCK_THRESHOLD: float = _getenv_float('API_BLOCK_THRESHOLD', 0.95)
    
    # Timeout para requests HTTP (segundos)
    API_TIMEOUT: int = _getenv_int('API_TIMEOUT', 30)
    
    # ============================================================
    # 🌐 CONFIGURAÇÕES DO SERVIDOR
    # ============================================================
    
    # Porta do servidor web (Render define automaticamente)
    PORT: int = _getenv_int('PORT', 8080)
    
    # Modo debug
    DEBUG: bool = _getenv_bool('DEBUG', False)
    
    # Ambiente (production, development, test)
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'production')
    
    # ============================================================
    # 📊 CONFIGURAÇÕES DE LOGGING
    # ============================================================
    
    # Nível de logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # ============================================================
    # ⏰ HORÁRIOS DE EXECUÇÃO OTIMIZADOS
    # ============================================================
    
    # Elite: 4 execuções diárias (horas UTC)
    ELITE_EXECUTION_HOURS: list = [
        int(x.strip()) for x in os.getenv('ELITE_EXECUTION_HOURS', '7,11,15,19').split(',')
    ]
    
    # Regressão: 6 execuções diárias (horas UTC)
    REGRESSAO_EXECUTION_HOURS: list = [
        int(x.strip()) for x in os.getenv('REGRESSAO_EXECUTION_HOURS', '8,10,12,14,17,20').split(',')
    ]
    
    # Monitor API: 3 execuções diárias (horas UTC)
    API_MONITOR_HOURS: list = [
        int(x.strip()) for x in os.getenv('API_MONITOR_HOURS', '8,14,20').split(',')
    ]
    
    # ============================================================
    # 🧪 CONFIGURAÇÕES DE TESTE
    # ============================================================
    
    # Ativar testes imediatos no startup
    ENABLE_IMMEDIATE_TESTS: bool = _getenv_bool('ENABLE_IMMEDIATE_TESTS', True)
    
    # Delay para testes imediatos (minutos)
    TEST_DELAY_ELITE: int = _getenv_int('TEST_DELAY_ELITE', 2)
    TEST_DELAY_REGRESSAO: int = _getenv_int('TEST_DELAY_REGRESSAO', 4)
    
    # Modo dry-run (não envia mensagens reais)
    DRY_RUN: bool = _getenv_bool('DRY_RUN', False)
    
    # ============================================================
    # 📱 CONFIGURAÇÕES DE NOTIFICAÇÕES
    # ============================================================
    
    # Formato de data para mensagens
    DATE_FORMAT: str = os.getenv('DATE_FORMAT', '%d/%m/%Y')
    TIME_FORMAT: str = os.getenv('TIME_FORMAT', '%H:%M')
    DATETIME_FORMAT: str = f"{DATE_FORMAT} às {TIME_FORMAT}"
    
    # ============================================================
    # 📊 MÉTODOS DE UTILIDADE
    # ============================================================
    
    @classmethod
    def validate(cls) -> bool:
        """Valida se todas as configurações obrigatórias estão presentes e corretas"""
        errors = []
        
        # Verificar credenciais obrigatórias
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN não configurado")
        
        if not cls.API_FOOTBALL_KEY:
            errors.append("API_FOOTBALL_KEY não configurado")
        
        if not cls.CHAT_ID_ELITE:
            errors.append("CHAT_ID_ELITE não configurado")
        
        # Verificar valores numéricos
        if cls.API_DAILY_LIMIT <= 0:
            errors.append("API_DAILY_LIMIT deve ser maior que 0")
        
        if not (0 <= cls.API_WARNING_THRESHOLD <= 1):
            errors.append("API_WARNING_THRESHOLD deve estar entre 0 e 1")
        
        if not (0 <= cls.API_BLOCK_THRESHOLD <= 1):
            errors.append("API_BLOCK_THRESHOLD deve estar entre 0 e 1")
        
        if cls.API_WARNING_THRESHOLD >= cls.API_BLOCK_THRESHOLD:
            errors.append("API_WARNING_THRESHOLD deve ser menor que API_BLOCK_THRESHOLD")
        
        if not (0 <= cls.REGRESSAO_ACTIVE_HOURS_START <= 23):
            errors.append("REGRESSAO_ACTIVE_HOURS_START deve estar entre 0 e 23")
        
        if not (0 <= cls.REGRESSAO_ACTIVE_HOURS_END <= 23):
            errors.append("REGRESSAO_ACTIVE_HOURS_END deve estar entre 0 e 23")
        
        if cls.ELITE_GOALS_THRESHOLD <= 0:
            errors.append("ELITE_GOALS_THRESHOLD deve ser maior que 0")
        
        # Reportar erros se existirem
        if errors:
            for error in errors:
                print(f"❌ Erro de configuração: {error}")
            return False
        
        return True
    
    @classmethod
    def print_startup_info(cls):
        """Imprime informações de configuração no startup"""
        print("=" * 60)
        print("🚀 BOT FUTEBOL CONSOLIDADO - CONFIGURAÇÃO OTIMIZADA")
        print("=" * 60)
        print("🔑 CREDENCIAIS:")
        print(f"   📱 Telegram Token: {'✅ Configurado' if cls.TELEGRAM_BOT_TOKEN else '❌ Não configurado'}")
        print(f"   ⚽ API Football: {'✅ Configurado' if cls.API_FOOTBALL_KEY else '❌ Não configurado'}")
        print("📦 MÓDULOS HABILITADOS:")
        print(f"   {'✅' if cls.ELITE_ENABLED else '❌'} ELITE ({len(cls.ELITE_EXECUTION_HOURS)}x/dia)")
        print(f"   {'✅' if cls.REGRESSAO_ENABLED else '❌'} REGRESSÃO ({len(cls.REGRESSAO_EXECUTION_HOURS)}x/dia)")
        print(f"   {'✅' if cls.CAMPEONATOS_ENABLED else '❌'} CAMPEONATOS (1x/dia)")
        print("⚙️ CONFIGURAÇÕES TÉCNICAS:")
        print(f"   🌐 Porta: {cls.PORT}")
        print(f"   📈 Limite API: {cls.API_DAILY_LIMIT} requests/dia")
        print(f"   ⚠️ Aviso em: {cls.API_WARNING_THRESHOLD:.0%}")
        print(f"   🚫 Bloqueio em: {cls.API_BLOCK_THRESHOLD:.0%}")
        print(f"   🔧 Ambiente: {cls.ENVIRONMENT}")
        print(f"   🧪 Testes imediatos: {'✅' if cls.ENABLE_IMMEDIATE_TESTS else '❌'}")
        print(f"   🔇 Modo dry-run: {'✅' if cls.DRY_RUN else '❌'}")
        print("=" * 60)
    
    @classmethod
    def get_summary(cls) -> dict:
        """Retorna resumo das configurações principais para logs"""
        return {
            'modules': {
                'elite': cls.ELITE_ENABLED,
                'regressao': cls.REGRESSAO_ENABLED,
                'campeonatos': cls.CAMPEONATOS_ENABLED
            },
            'api': {
                'daily_limit': cls.API_DAILY_LIMIT,
                'warning_threshold': cls.API_WARNING_THRESHOLD,
                'block_threshold': cls.API_BLOCK_THRESHOLD
            },
            'execution_hours': {
                'elite': cls.ELITE_EXECUTION_HOURS,
                'regressao': cls.REGRESSAO_EXECUTION_HOURS,
                'api_monitor': cls.API_MONITOR_HOURS
            },
            'environment': cls.ENVIRONMENT,
            'debug': cls.DEBUG,
            'dry_run': cls.DRY_RUN
        }

# Validar configurações automaticamente ao importar
if not Config.validate():
    raise RuntimeError("❌ Configuração inválida - verifique as variáveis de ambiente")

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import Config
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from utils.keep_alive import keep_alive
from modules.jogos_elite import JogosEliteModule
from modules.regressao_media import RegressaoMediaModule

# Filtro para censurar tokens nos logs (COMPLETO)
class RedactSecretsFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.token_pattern = re.compile(r'bot\d{6,}:[A-Za-z0-9_-]+')
    
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if self.token:
            msg = msg.replace(self.token, "<REDACTED>")
        msg = self.token_pattern.sub("bot<REDACTED>", msg)
        record.msg = msg
        record.args = ()
        return True

# Configurar logging ANTES de qualquer uso
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Aplicar filtro e reduzir verbosidade
redact_filter = RedactSecretsFilter()
for handler in logging.getLogger().handlers:
    handler.addFilter(redact_filter)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Variável global para acesso ao bot (APÓS configuração de logging)
bot_instance = None

class BotConsolidado:
    """Bot de Futebol Consolidado - VERSÃO OTIMIZADA PARA ECONOMIA DE API"""
    
    def __init__(self):
        global bot_instance
        bot_instance = self  # Permitir acesso global ao bot
        
        logger.info("🚀 Iniciando Bot Futebol Consolidado - MODO ECONOMIA")
        
        # Inicializar clientes
        self.telegram_client = TelegramClient(Config.TELEGRAM_BOT_TOKEN)
        self.api_client = ApiFootballClient(Config.API_FOOTBALL_KEY)
        
        # Inicializar módulos
        self.modules = {}
        
        if Config.ELITE_ENABLED:
            try:
                self.modules['elite'] = JogosEliteModule(self.telegram_client, self.api_client)
                logger.info("✅ Módulo Elite inicializado")
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar módulo Elite: {e}")
        
        if Config.REGRESSAO_ENABLED:
            try:
                self.modules['regressao'] = RegressaoMediaModule(self.telegram_client, self.api_client)
                logger.info("✅ Módulo Regressão inicializado")
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar módulo Regressão: {e}")
        
        logger.info("⚠️ Módulo Campeonatos desativado temporariamente para economia de API")
        
        # Inicializar scheduler
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._setup_scheduler()
        
        logger.info(f"📦 Módulos ativos: {list(self.modules.keys())}")
    
    def _setup_scheduler(self):
    """Configura agendamento otimizado para 2000 requests/dia"""
    
    # === EXECUÇÕES ESTRATÉGICAS PARA MÁXIMA COBERTURA ===
    
    # Elite: 4x por dia (cobertura completa sem desperdício)
    if Config.ELITE_ENABLED and 'elite' in self.modules:
        elite_hours = [7, 11, 15, 19]  # 08:00, 12:00, 16:00, 20:00 Lisboa
        for i, hour in enumerate(elite_hours):
            self.scheduler.add_job(
                self.modules['elite'].execute,
                'cron',
                hour=hour,
                minute=0,
                id=f'elite_{i+1}',
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600
            )
        logger.info("⏰ Elite agendado: 4x/dia (08:00, 12:00, 16:00, 20:00 Lisboa)")
    
    # Regressão: 6x por dia (análise frequente para oportunidades)
    if Config.REGRESSAO_ENABLED and 'regressao' in self.modules:
        regressao_hours = [8, 10, 12, 14, 17, 20]  # Horários estratégicos
        for i, hour in enumerate(regressao_hours):
            self.scheduler.add_job(
                self.modules['regressao'].execute,
                'cron',
                hour=hour,
                minute=30,  # 30 min após Elite para evitar conflitos
                id=f'regressao_{i+1}',
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600
            )
        logger.info("⏰ Regressão agendado: 6x/dia (horários otimizados)")
    
    # Campeonatos: Re-ativado 1x por dia
    if hasattr(Config, 'CAMPEONATOS_ENABLED') and Config.CAMPEONATOS_ENABLED:
        if 'campeonatos' in self.modules:
            self.scheduler.add_job(
                self.modules['campeonatos'].execute,
                'cron',
                hour=9,
                minute=0,
                id='campeonatos_daily',
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600
            )
            logger.info("⏰ Campeonatos agendado: 1x/dia às 10:00 Lisboa")
    
    # === TESTE IMEDIATO PARA VERIFICAÇÃO ===
    from datetime import timedelta
    
    now_utc = datetime.now(timezone.utc)
    
    # Teste Elite em 2 minutos
    if Config.ELITE_ENABLED and 'elite' in self.modules:
        test_time = now_utc + timedelta(minutes=2)
        self.scheduler.add_job(
            self.modules['elite'].execute,
            'date',
            run_date=test_time,
            id='elite_test_now',
            max_instances=1
        )
        logger.info(f"🧪 TESTE Elite: {test_time.strftime('%H:%M:%S')} UTC")
    
    # Teste Regressão em 4 minutos
    if Config.REGRESSAO_ENABLED and 'regressao' in self.modules:
        test_time = now_utc + timedelta(minutes=4)
        self.scheduler.add_job(
            self.modules['regressao'].execute,
            'date',
            run_date=test_time,
            id='regressao_test_now',
            max_instances=1
        )
        logger.info(f"🧪 TESTE Regressão: {test_time.strftime('%H:%M:%S')} UTC")
    
    # Monitor API: 3x por dia
    self.scheduler.add_job(
        self.log_api_usage,
        'cron',
        hour='8,14,20',
        minute=45,
        id='api_monitor'
    )
    
    # Keep-alive: 30 min
    self.scheduler.add_job(
        keep_alive, 
        'interval', 
        minutes=30,
        id='keep_alive'
    )

async def log_api_usage(self):
    """Monitor API com informações da conta"""
    try:
        stats = self.api_client.get_daily_usage_stats()
        
        # Status baseado no uso do bot
        if stats['bot_percentage'] < 40:
            status_emoji = "🟢"
            status_text = "EXCELENTE"
        elif stats['bot_percentage'] < 60:
            status_emoji = "🟡" 
            status_text = "BOM"
        elif stats['bot_percentage'] < 80:
            status_emoji = "🟠"
            status_text = "ATENÇÃO"
        else:
            status_emoji = "🔴"
            status_text = "CRÍTICO"
        
        # Informações da conta (se disponíveis)
        account_info = ""
        if stats['account_remaining'] is not None:
            account_info = f"\n🏦 **Conta:** {stats['account_remaining']}/{stats['account_limit']} restantes"
        
        message = f"""{status_emoji} **Relatório API Diário**

🤖 **Bot:** {stats['bot_used']}/{stats['bot_limit']} ({stats['bot_percentage']}%)
⚡ **Restante Bot:** {stats['bot_remaining']} requests{account_info}
📅 **Reset:** {stats['reset_time']}
🗓️ **Data:** {stats['date']}

💡 **Status:** {status_text}
🎯 **Estratégia:** Elite 4x + Regressão 6x + Campeonatos 1x/dia
📊 **Quota Alocada:** 2000/7500 requests totais da conta"""
        
        await self.telegram_client.send_admin_message(message)
        logger.info(f"📊 API Usage: {stats['bot_used']}/{stats['bot_limit']} ({stats['bot_percentage']}%) - {status_text}")
        
    except Exception as e:
        logger.error(f"❌ Erro no monitor de API: {e}")


    async def send_startup_message(self):
        """Envia mensagem de inicialização"""
        try:
            api_stats = self.api_client.get_monthly_usage_stats()
            
            startup_message = f"""🚀 **BOT FUTEBOL CONSOLIDADO INICIADO**

🔧 **MODO ECONOMIA ATIVADO**
📊 Módulos ativos: {len(self.modules)}
⏰ Jobs agendados: {len(self.scheduler.get_jobs())}

📈 **Módulos:**
""" + (f"✅ Elite: 1x/dia às 08:00 Lisboa\n" if 'elite' in self.modules else "") + \
(f"✅ Regressão: 1x/dia às 10:00 Lisboa\n" if 'regressao' in self.modules else "") + \
f"❌ Campeonatos: Desativado (economia)" + f"""

🔧 **API Status:**
📊 Usado: {api_stats['used']}/{api_stats['limit']} ({api_stats['percentage_used']}%)
⚠️ Restante: {api_stats['remaining']} requests
📅 Mês: {api_stats['month']}

💡 Otimização implementada para trabalhar dentro do limite gratuito
⏰ {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC"""
            
            await self.telegram_client.send_admin_message(startup_message)
            logger.info("📨 Mensagem de startup enviada")
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem de startup: {e}")

    async def start(self):
        """Inicia o bot"""
        try:
            self.scheduler.start()
            logger.info("⏰ Scheduler iniciado")
            
            await self.send_startup_message()
            await keep_alive()
            
            logger.info("✅ Bot iniciado com sucesso!")
            logger.info(f"📦 Módulos ativos: {list(self.modules.keys())}")
            logger.info(f"⏰ Jobs agendados: {len(self.scheduler.get_jobs())}")
            logger.info("🔄 Entrando no loop principal...")
            
            while True:
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("🛑 Interrupção do usuário detectada")
        except Exception as e:
            logger.error(f"💥 Erro crítico: {e}")
            await self.telegram_client.send_admin_message(f"💥 Erro crítico no bot: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Encerra o bot graciosamente"""
        logger.info("🛑 Encerrando bot...")
        
        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("⏰ Scheduler encerrado")
        
        # Parar servidor keep-alive
        try:
            from utils.keep_alive import stop_server
            await stop_server()
        except Exception as e:
            logger.warning(f"⚠️ Erro ao parar keep-alive: {e}")
        
        try:
            await self.telegram_client.send_admin_message("🛑 Bot encerrado")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao enviar mensagem de shutdown: {e}")
        
        logger.info("👋 Bot encerrado com sucesso")

async def main():
    """Função principal"""
    # Dashboard de configuração
    print("=" * 60)
    print("🚀 BOT FUTEBOL CONSOLIDADO - CONFIGURAÇÃO")
    print("=" * 60)
    print("🔑 CREDENCIAIS:")
    print(f"   📱 Telegram Token: {'✅ Configurado' if Config.TELEGRAM_BOT_TOKEN else '❌ Não configurado'}")
    print(f"   ⚽ API Football: {'✅ Configurado' if Config.API_FOOTBALL_KEY else '❌ Não configurado'}")
    print("📦 MÓDULOS HABILITADOS:")
    print(f"   {'✅' if Config.ELITE_ENABLED else '❌'} ELITE (1x/dia às 08:00 Lisboa)")
    print(f"   {'✅' if Config.REGRESSAO_ENABLED else '❌'} REGRESSAO (1x/dia às 10:00 Lisboa)")
    print(f"   ❌ CAMPEONATOS (desativado temporariamente)")
    print("⚙️ CONFIGURAÇÕES TÉCNICAS:")
    print(f"   🌐 Porta: {os.getenv('PORT', 8080)}")
    print(f"   📈 Limite API: 2000 requests/mês")
    print(f"   🔧 Modo: Economia")
    print("=" * 60)
    
    # Verificar variáveis obrigatórias
    required_vars = ['TELEGRAM_BOT_TOKEN', 'API_FOOTBALL_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Variáveis de ambiente não configuradas: {missing_vars}")
        return
    
    bot = BotConsolidado()
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Aplicação interrompida pelo usuário")
    except Exception as e:
        logger.error(f"💥 Erro fatal: {e}")

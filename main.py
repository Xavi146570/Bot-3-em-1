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

# Filtro para censurar tokens nos logs
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

# Configurar logging
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

class BotConsolidado:
    """Bot de Futebol Consolidado - VERSÃO OTIMIZADA PARA ECONOMIA DE API"""
    
    def __init__(self):
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
        """Configura o agendamento dos módulos - VERSÃO OTIMIZADA"""
        
        # Elite: 1x por dia às 08:00 Lisboa (07:00 UTC)
        if Config.ELITE_ENABLED and 'elite' in self.modules:
            self.scheduler.add_job(
                self.modules['elite'].execute,
                'cron',
                hour=7,
                minute=0,
                id='elite_daily',
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600
            )
            logger.info("⏰ Elite agendado: 1x/dia às 08:00 Lisboa (07:00 UTC)")
        
        # Regressão: 1x por dia às 10:00 Lisboa (09:00 UTC)
        if Config.REGRESSAO_ENABLED and 'regressao' in self.modules:
            self.scheduler.add_job(
                self.modules['regressao'].execute,
                'cron',
                hour=9,
                minute=0,
                id='regressao_daily',
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600
            )
            logger.info("⏰ Regressão agendado: 1x/dia às 10:00 Lisboa (09:00 UTC)")
        
        # Monitor API: 2x por dia
        self.scheduler.add_job(
            self.log_api_usage,
            'cron',
            hour='8,20',
            minute=30,
            id='api_monitor'
        )
        logger.info("⏰ Monitor API agendado: 2x/dia (08:30 e 20:30 UTC)")
        
        # Keep-alive: 30 min
        self.scheduler.add_job(
            keep_alive, 
            'interval', 
            minutes=30,
            id='keep_alive'
        )
        logger.info("⏰ Keep-alive agendado: a cada 30 minutos")

    async def log_api_usage(self):
        """Monitoriza e reporta uso da API"""
        try:
            stats = self.api_client.get_monthly_usage_stats()
            
            if stats['percentage_used'] < 50:
                status_emoji = "🟢"
                status_text = "OK"
            elif stats['percentage_used'] < 75:
                status_emoji = "🟡"
                status_text = "ATENÇÃO"
            elif stats['percentage_used'] < 90:
                status_emoji = "🟠"
                status_text = "CUIDADO"
            else:
                status_emoji = "🔴"
                status_text = "CRÍTICO"
            
            message = f"""{status_emoji} **Relatório de API**

📊 **Usado:** {stats['used']}/{stats['limit']} ({stats['percentage_used']}%)
⚡ **Restante:** {stats['remaining']} requisições
📅 **Reset:** Dia 1 do próximo mês
🗓️ **Mês atual:** {stats['month']}

💡 **Status:** {status_text}
🔧 **Modo:** Economia ativado (1x/dia por módulo)"""
            
            await self.telegram_client.send_admin_message(message)
            logger.info(f"📊 API Usage: {stats['used']}/{stats['limit']} ({stats['percentage_used']}%) - {status_text}")
            
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
        
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("⏰ Scheduler encerrado")
        
        await self.telegram_client.send_admin_message("🛑 Bot encerrado")
        logger.info("👋 Bot encerrado com sucesso")

async def main():
    """Função principal"""
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

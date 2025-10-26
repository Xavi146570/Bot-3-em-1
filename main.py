import asyncio
import logging
import os
import re
from datetime import datetime, timezone, timedelta
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

# Variável global para acesso ao bot
bot_instance = None

class BotConsolidado:
    """Bot de Futebol Consolidado - VERSÃO OTIMIZADA PARA 2000 REQUESTS/DIA"""
    
    def __init__(self):
        global bot_instance
        bot_instance = self
        
        logger.info("🚀 Iniciando Bot Futebol Consolidado - MODO OTIMIZADO")
        
        # Inicializar clientes
        self.telegram_client = TelegramClient(Config.TELEGRAM_BOT_TOKEN)
        self.api_client = ApiFootballClient(Config.API_FOOTBALL_KEY, Config.API_DAILY_LIMIT)
        
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
        
        if Config.CAMPEONATOS_ENABLED:
            try:
                from modules.campeonatos_padrao import CampeonatosPadraoModule
                self.modules['campeonatos'] = CampeonatosPadraoModule(self.telegram_client, self.api_client)
                logger.info("✅ Módulo Campeonatos inicializado")
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar módulo Campeonatos: {e}")
        else:
            logger.info("⚠️ Módulo Campeonatos desabilitado na configuração")
        
        # Inicializar scheduler
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._setup_scheduler()
        
        logger.info(f"📦 Módulos ativos: {list(self.modules.keys())}")
    
    def _setup_scheduler(self):
        """Configura agendamento otimizado para 2000 requests/dia"""
        
        # === EXECUÇÕES ESTRATÉGICAS PARA MÁXIMA COBERTURA ===
        
        # Elite: múltiplas execuções por dia
        if Config.ELITE_ENABLED and 'elite' in self.modules:
            for i, hour in enumerate(Config.ELITE_EXECUTION_HOURS):
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
            logger.info(f"⏰ Elite agendado: {len(Config.ELITE_EXECUTION_HOURS)}x/dia (Horários UTC: {Config.ELITE_EXECUTION_HOURS})")
        
        # Regressão: múltiplas execuções por dia
        if Config.REGRESSAO_ENABLED and 'regressao' in self.modules:
            for i, hour in enumerate(Config.REGRESSAO_EXECUTION_HOURS):
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
            logger.info(f"⏰ Regressão agendado: {len(Config.REGRESSAO_EXECUTION_HOURS)}x/dia (Horários UTC: {Config.REGRESSAO_EXECUTION_HOURS})")
        
        # Campeonatos: 1x por dia
        if Config.CAMPEONATOS_ENABLED and 'campeonatos' in self.modules:
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
            logger.info("⏰ Campeonatos agendado: 1x/dia às 09:00 UTC")
        
        # === TESTES IMEDIATOS PARA VERIFICAÇÃO ===
        if Config.ENABLE_IMMEDIATE_TESTS:
            now_utc = datetime.now(timezone.utc)
            
            # Teste Elite
            if Config.ELITE_ENABLED and 'elite' in self.modules:
                test_time = now_utc + timedelta(minutes=Config.TEST_DELAY_ELITE)
                self.scheduler.add_job(
                    self.modules['elite'].execute,
                    'date',
                    run_date=test_time,
                    id='elite_test_now',
                    max_instances=1
                )
                logger.info(f"🧪 TESTE Elite: {test_time.strftime('%H:%M:%S')} UTC")
            
            # Teste Regressão
            if Config.REGRESSAO_ENABLED and 'regressao' in self.modules:
                test_time = now_utc + timedelta(minutes=Config.TEST_DELAY_REGRESSAO)
                self.scheduler.add_job(
                    self.modules['regressao'].execute,
                    'date',
                    run_date=test_time,
                    id='regressao_test_now',
                    max_instances=1
                )
                logger.info(f"🧪 TESTE Regressão: {test_time.strftime('%H:%M:%S')} UTC")
        
        # Monitor API: múltiplas execuções por dia
        for i, hour in enumerate(Config.API_MONITOR_HOURS):
            self.scheduler.add_job(
                self.log_api_usage,
                'cron',
                hour=hour,
                minute=45,
                id=f'api_monitor_{i+1}',
                max_instances=1,
                coalesce=True
            )
        logger.info(f"⏰ Monitor API agendado: {len(Config.API_MONITOR_HOURS)}x/dia (Horários UTC: {Config.API_MONITOR_HOURS})")
        
        # Keep-alive: 30 min
        self.scheduler.add_job(
            keep_alive, 
            'interval', 
            minutes=30,
            id='keep_alive',
            max_instances=1,
            coalesce=True
        )
        logger.info("⏰ Keep-alive agendado: a cada 30 minutos")

    async def log_api_usage(self):
        """Monitor API com informações detalhadas da quota diária"""
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
            if stats.get('account_remaining') is not None:
                account_info = f"\n🏦 **Conta:** {stats['account_remaining']}/{stats['account_limit']} restantes"
            
            message = f"""{status_emoji} **Relatório API Diário**

🤖 **Bot:** {stats['bot_used']}/{stats['bot_limit']} ({stats['bot_percentage']}%)
⚡ **Restante:** {stats['bot_remaining']} requests{account_info}
📅 **Reset:** {stats['reset_time']}
🗓️ **Data:** {stats['date']}

💡 **Status:** {status_text}
🎯 **Estratégia:** Elite {len(Config.ELITE_EXECUTION_HOURS)}x + Regressão {len(Config.REGRESSAO_EXECUTION_HOURS)}x + Campeonatos 1x/dia
📊 **Quota Alocada:** {Config.API_DAILY_LIMIT} requests/dia de 7500 totais"""
            
            await self.telegram_client.send_admin_message(message)
            logger.info(f"📊 API Usage: {stats['bot_used']}/{stats['bot_limit']} ({stats['bot_percentage']}%) - {status_text}")
            
        except Exception as e:
            logger.error(f"❌ Erro no monitor de API: {e}")

    async def send_startup_message(self):
        """Envia mensagem de inicialização otimizada"""
        try:
            stats = self.api_client.get_daily_usage_stats()
            
            modules_text = ""
            if 'elite' in self.modules:
                modules_text += f"✅ Elite: {len(Config.ELITE_EXECUTION_HOURS)}x/dia\n"
            if 'regressao' in self.modules:
                modules_text += f"✅ Regressão: {len(Config.REGRESSAO_EXECUTION_HOURS)}x/dia\n"
            if 'campeonatos' in self.modules:
                modules_text += f"✅ Campeonatos: 1x/dia\n"
            
            startup_message = f"""🚀 **BOT FUTEBOL CONSOLIDADO INICIADO**

🔧 **MODO OTIMIZADO PARA 2000 REQUESTS/DIA**
📊 Módulos ativos: {len(self.modules)}
⏰ Jobs agendados: {len(self.scheduler.get_jobs())}

📈 **Módulos:**
{modules_text}
🔧 **API Status:**
📊 Usado hoje: {stats['bot_used']}/{stats['bot_limit']} ({stats['bot_percentage']}%)
⚠️ Restante: {stats['bot_remaining']} requests
📅 Data: {stats['date']}

💡 Otimização implementada para trabalhar dentro do limite de {Config.API_DAILY_LIMIT} requests/dia
⏰ {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC"""
            
            await self.telegram_client.send_admin_message(startup_message)
            logger.info("📨 Mensagem de startup enviada")
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem de startup: {e}")

    async def start(self):
        """Inicia o bot com configurações otimizadas"""
        try:
            # Testar conexão Telegram
            telegram_ok = await self.telegram_client.test_connection()
            if not telegram_ok:
                logger.error("❌ Falha na conexão com Telegram - verificar token")
                return
            
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
            await self.telegram_client.send_admin_message("🛑 Bot encerrado graciosamente")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao enviar mensagem de shutdown: {e}")
        
        logger.info("👋 Bot encerrado com sucesso")

async def main():
    """Função principal com dashboard de configuração"""
    
    # Dashboard de configuração no console
    Config.print_startup_info()
    
    # Verificar variáveis críticas
    required_vars = ['TELEGRAM_BOT_TOKEN', 'API_FOOTBALL_KEY', 'CHAT_ID_ELITE']
    missing_vars = []
    
    for var in required_vars:
        if not getattr(Config, var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Variáveis críticas não configuradas: {missing_vars}")
        return
    
    # Inicializar e executar bot
    bot = BotConsolidado()
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Aplicação interrompida pelo usuário")
    except Exception as e:
        logger.error(f"💥 Erro fatal: {e}")

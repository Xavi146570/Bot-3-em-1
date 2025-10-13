import asyncio
import logging
import signal
from config import Config
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from scheduler_manager import SchedulerManager
from web_server import WebServer
from modules.jogos_elite import JogosEliteModule
from modules.regressao_media import RegressaoMediaModule
from modules.campeonatos_padrao import CampeonatosPadraoModule

# Configurar logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BotConsolidado:
    def __init__(self):
        self.telegram_client = TelegramClient()
        self.api_client = ApiFootballClient()
        self.scheduler = SchedulerManager()
        self.running = False
        
        # Inicializar módulos
        self.modules = {}
        if Config.CHAT_ID_ELITE:
            self.modules['elite'] = JogosEliteModule(self.telegram_client, self.api_client)
        
        if Config.CHAT_ID_REGRESSAO:
            self.modules['regressao'] = RegressaoMediaModule(self.telegram_client, self.api_client)
        
        if Config.CHAT_ID_CAMPEONATOS or Config.get_chat_map():
            self.modules['campeonatos'] = CampeonatosPadraoModule(self.telegram_client, self.api_client)
        
        self.web_server = WebServer(self.modules)
    
    def setup_jobs(self):
        # Job Elite - a cada 24h
        if 'elite' in self.modules:
            self.scheduler.add_interval_job(
                self.modules['elite'].execute,
                Config.ELITE_INTERVAL_HOURS * 60,
                'job_elite'
            )
        
        # Job Regressão - a cada 30min
        if 'regressao' in self.modules:
            self.scheduler.add_interval_job(
                self.modules['regressao'].execute,
                Config.REGRESSAO_INTERVAL_MINUTES,
                'job_regressao'
            )
        
        # Job Campeonatos - 2x por dia
        if 'campeonatos' in self.modules:
            self.scheduler.add_cron_job(
                self.modules['campeonatos'].execute,
                9, 0,  # 09:00
                'job_campeonatos_manha'
            )
            self.scheduler.add_cron_job(
                self.modules['campeonatos'].execute,
                18, 0,  # 18:00
                'job_campeonatos_tarde'
            )
    
    async def start(self):
        logger.info("🚀 Iniciando Bot Futebol Consolidado")
        
        # Verificar conexão Telegram
        try:
            bot_info = await self.telegram_client.bot.get_me()
            logger.info(f"✅ Bot conectado: @{bot_info.username}")
        except Exception as e:
            logger.error(f"❌ Erro conectando Telegram: {e}")
            return
        
        # Configurar e iniciar serviços
        self.setup_jobs()
        await self.web_server.start_server()
        self.scheduler.start()
        
        logger.info(f"📦 Módulos ativos: {list(self.modules.keys())}")
        logger.info(f"⏰ Jobs agendados: {len(self.scheduler.jobs)}")
        
        # Notificar admin
        if Config.ADMIN_CHAT_ID:
            await self.telegram_client.send_message(
                Config.ADMIN_CHAT_ID,
                f"🚀 Bot Consolidado iniciado!\n"
                f"📦 Módulos: {', '.join(self.modules.keys())}\n"
                f"🌐 Porta: {Config.PORT}"
            )
        
        self.running = True
        
        # Manter rodando
        try:
            while self.running:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            logger.info("Interrupção recebida")
        finally:
            await self.stop()
    
    async def stop(self):
        logger.info("🛑 Parando bot consolidado")
        self.running = False
        self.scheduler.shutdown()
        
        if Config.ADMIN_CHAT_ID:
            try:
                await self.telegram_client.send_message(
                    Config.ADMIN_CHAT_ID,
                    "🛑 Bot Consolidado parado"
                )
            except:
                pass

async def main():
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"❌ Erro de configuração: {e}")
        return
    
    bot = BotConsolidado()
    
    def signal_handler(signum, frame):
        logger.info(f"Sinal {signum} recebido")
        asyncio.create_task(bot.stop())
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())

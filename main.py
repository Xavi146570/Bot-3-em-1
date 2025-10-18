import logging

# Configuração básica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 🔐 SEGURANÇA: Ocultar tokens nos logs
logging.getLogger("httpx").setLevel(logging.WARNING)  # Só warnings e erros
logging.getLogger("httpcore").setLevel(logging.WARNING)  # Biblioteca base do httpx

logger = logging.getLogger(__name__)
logger.info("🔐 Sistema de logging seguro ativado - tokens ocultos")

import asyncio
import logging
import signal
from datetime import datetime
from config import Config, setup_logging
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from utils.keep_alive import KeepAlive
from scheduler_manager import SchedulerManager
from web_server import WebServer

# Imports dos módulos
from modules.jogos_elite import JogosEliteModule
from modules.regressao_media import RegressaoMediaModule
from modules.campeonatos_padrao import CampeonatosPadraoModule

logger = logging.getLogger(__name__)

class BotConsolidado:
    """Sistema consolidado dos três bots de futebol"""
    
    def __init__(self):
        logger.info("🚀 Inicializando Bot Consolidado...")
        
        # Clientes principais
        self.telegram_client = TelegramClient()
        self.api_client = ApiFootballClient()
        self.scheduler = SchedulerManager()
        
        # Keep-Alive para evitar sleep no Render Free
        self.keep_alive = KeepAlive()
        self.keep_alive_task = None
        
        self.running = False
        
        # Inicializar módulos baseado na configuração
        self.modules = {}
        enabled_modules = Config.get_enabled_modules()
        
        if enabled_modules.get('elite', {}).get('enabled'):
            self.modules['elite'] = JogosEliteModule(self.telegram_client, self.api_client)
            logger.info("✅ Módulo Elite habilitado")
        
        if enabled_modules.get('regressao', {}).get('enabled'):
            self.modules['regressao'] = RegressaoMediaModule(self.telegram_client, self.api_client)
            logger.info("✅ Módulo Regressão habilitado")
        
        if enabled_modules.get('campeonatos', {}).get('enabled'):
            self.modules['campeonatos'] = CampeonatosPadraoModule(self.telegram_client, self.api_client)
            logger.info("✅ Módulo Campeonatos habilitado")
        
        self.web_server = WebServer(self.modules)
        logger.info(f"📦 Bot inicializado com {len(self.modules)} módulos")
    
    def setup_jobs(self):
        """Configura jobs do scheduler com execução imediata para testes"""
        logger.info("⏰ Configurando jobs...")
        
        # Job Elite - executar imediatamente + a cada 24h
        if 'elite' in self.modules:
            self.scheduler.add_interval_job(
                self.modules['elite'].execute,
                Config.ELITE_INTERVAL_HOURS * 60,  # converter para minutos
                'job_elite',
                run_immediately=True  # EXECUÇÃO IMEDIATA
            )
        
        # Job Regressão - executar imediatamente + a cada 30min
        if 'regressao' in self.modules:
            self.scheduler.add_interval_job(
                self.modules['regressao'].execute,
                Config.REGRESSAO_INTERVAL_MINUTES,
                'job_regressao',
                run_immediately=True  # EXECUÇÃO IMEDIATA
            )
        
        # Jobs Campeonatos permanecem nos horários fixos
        if 'campeonatos' in self.modules:
            self.scheduler.add_cron_job(
                self.modules['campeonatos'].execute,
                9, 0, 'job_campeonatos_manha'
            )
            self.scheduler.add_cron_job(
                self.modules['campeonatos'].execute,
                18, 0, 'job_campeonatos_tarde'
            )
    
    async def start(self):
        """Inicia o bot consolidado com tratamento robusto de erros"""
        logger.info("🚀 Iniciando Bot Futebol Consolidado")
        
        try:
            # Verificar conexão Telegram
            connected = await self.telegram_client.verify_connection()
            if not connected:
                logger.error("❌ Falha na conexão Telegram")
                return
            logger.info("✅ Conexão Telegram verificada")
            
            # Iniciar serviços
            logger.info("🌐 Iniciando servidor web...")
            await self.web_server.start_server()
            logger.info("✅ Servidor web iniciado")
            
            logger.info("⏰ Configurando jobs...")
            self.setup_jobs()
            logger.info("✅ Jobs configurados")
            
            logger.info("📅 Iniciando scheduler...")
            self.scheduler.start()
            logger.info("✅ Scheduler iniciado")
            
            logger.info("🔄 Iniciando keep-alive...")
            self.keep_alive_task = asyncio.create_task(self.keep_alive.start())
            logger.info("✅ Keep-Alive iniciado - serviço permanecerá ativo 24/7")
            
            # Enviar mensagem de startup
            if Config.ADMIN_CHAT_ID:
                modules_list = "\n".join([f"  • {name.title()}" for name in self.modules.keys()]) or "  • (nenhum módulo ativo)"
                startup_msg = f"""🚀 <b>Bot Consolidado Iniciado</b>

📦 <b>Módulos:</b> {len(self.modules)}
{modules_list}

⏰ <b>Jobs:</b> {len(self.scheduler.jobs)}
🌐 <b>Porta:</b> {Config.PORT}
🔄 <b>Keep-Alive:</b> Ativo (anti-sleep)

✅ <b>Sistema funcionando 24/7!</b>
🎯 Aguarde os alertas automáticos nos horários programados."""
                
                await self.telegram_client.send_message(Config.ADMIN_CHAT_ID, startup_msg)
                logger.info("📨 Mensagem de startup enviada")
            
            self.running = True
            logger.info("✅ Bot iniciado com sucesso!")
            logger.info(f"📦 Módulos ativos: {list(self.modules.keys())}")
            logger.info(f"⏰ Jobs agendados: {len(self.scheduler.jobs)}")
            
            # Loop principal
            logger.info("🔄 Entrando no loop principal...")
            while self.running:
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"❌ Erro crítico: {e}", exc_info=True)
            if Config.ADMIN_CHAT_ID:
                await self.telegram_client.send_admin_message(f"Erro crítico: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Para o bot com shutdown gracioso"""
        logger.info("🛑 Parando bot consolidado")
        self.running = False
        
        try:
            # Parar keep-alive
            if self.keep_alive:
                self.keep_alive.stop()
            
            # Cancelar task do keep-alive
            if self.keep_alive_task and not self.keep_alive_task.done():
                self.keep_alive_task.cancel()
                try:
                    await self.keep_alive_task
                except asyncio.CancelledError:
                    pass
            
            # Parar scheduler
            self.scheduler.shutdown()
            
            # Notificar admin
            if Config.ADMIN_CHAT_ID:
                await self.telegram_client.send_message(
                    Config.ADMIN_CHAT_ID, "🛑 Bot Consolidado parado"
                )
                
        except Exception as e:
            logger.error(f"Erro durante shutdown: {e}")

async def main():
    """Função principal"""
    try:
        # Setup logging
        setup_logging()
        
        # Validar configuração
        Config.validate()
        Config.print_summary()
        
        # Criar e iniciar bot
        bot = BotConsolidado()
        
        # Signal handlers para shutdown gracioso
        def signal_handler(signum, frame):
            logger.info(f"Sinal {signum} recebido")
            asyncio.create_task(bot.stop())
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Iniciar bot
        await bot.start()
        
    except Exception as e:
        logger.error(f"💥 Erro crítico: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

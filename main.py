import asyncio
import logging
import signal
from datetime import datetime
from config import Config, setup_logging
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from utils.keep_alive import KeepAlive  # <- KEEP-ALIVE ANTI-SLEEP
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
        """Configura jobs do scheduler"""
        logger.info("⏰ Configurando jobs...")
        
        # Job Elite - a cada X horas
        if 'elite' in self.modules:
            self.scheduler.add_interval_job(
                self.modules['elite'].execute,
                Config.ELITE_INTERVAL_HOURS * 60,  # converter para minutos
                'job_elite'
            )
        
        # Job Regressão - a cada X minutos
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
                9, 0, 'job_campeonatos_manha'
            )
            self.scheduler.add_cron_job(
                self.modules['campeonatos'].execute,
                18, 0, 'job_campeonatos_tarde'
            )
    
    async def start(self):
        """Inicia o bot consolidado"""
        logger.info("🚀 Iniciando Bot Futebol Consolidado")
        
        # Verificar conexão Telegram
        try:
            connected = await self.telegram_client.verify_connection()
            if not connected:
                logger.error("❌ Falha na conexão Telegram")
                return
        except Exception as e:
            logger.error(f"❌ Erro Telegram: {e}")
            return
        
        # Iniciar serviços
        try:
            # Web server
            await self.web_server.start_server()
            
            # Scheduler e Jobs
            self.setup_jobs()
            self.scheduler.start()
            
            # INICIAR KEEP-ALIVE EM BACKGROUND (ANTI-SLEEP)
            self.keep_alive_task = asyncio.create_task(self.keep_alive.start())
            logger.info("🔄 Keep-Alive iniciado - serviço permanecerá ativo 24/7")
            
            # Notificar admin
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
            
            self.running = True
            logger.info("✅ Bot iniciado com sucesso!")
            logger.info(f"📦 Módulos ativos: {list(self.modules.keys())}")
            logger.info(f"⏰ Jobs agendados: {len(self.scheduler.jobs)}")
            
            # Manter rodando
            try:
                while self.running:
                    await asyncio.sleep(60)
            except KeyboardInterrupt:
                logger.info("⚠️ Interrupção recebida")
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Para o bot com shutdown gracioso"""
        logger.info("🛑 Parando bot consolidado")
        self.running = False
        
        try:
            # Parar keep-alive primeiro
            if self.keep_alive:
                self.keep_alive.stop()
                logger.info("🔄 Keep-Alive parado")
            
            # Cancelar task do keep-alive se existir
            if self.keep_alive_task and not self.keep_alive_task.done():
                self.keep_alive_task.cancel()
                try:
                    await self.keep_alive_task
                except asyncio.CancelledError:
                    logger.info("🔄 Task Keep-Alive cancelada")
            
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

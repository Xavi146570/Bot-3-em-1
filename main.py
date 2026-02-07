import asyncio
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from utils.keep_alive import keep_alive
from modules.jogos_elite import JogosEliteModule
from modules.regressao_media import RegressaoMediaModule

# ===== CONFIGURAÇÃO DE LOGGING =====

class RedactSecretsFilter(logging.Filter):
    """Filtro para censurar tokens sensíveis nos logs"""
    
    def __init__(self):
        super().__init__()
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.token_pattern = re.compile(r'bot\d{6,}:[A-Za-z0-9_-]+')
    
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if self.token:
            msg = msg.replace(self.token, "<​REDACTED>")
        msg = self.token_pattern.sub("bot<REDACTED>", msg)
        record.msg = msg
        record.args = ()
        return True


def setup_logging():
    """Configura sistema de logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Aplicar filtro de segurança
    redact_filter = RedactSecretsFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redact_filter)
    
    # Reduzir verbosidade de bibliotecas externas
    for lib in ["httpx", "httpcore", "aiohttp.access", "apscheduler"]:
        logging.getLogger(lib).setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)

# ===== INTEGRAÇÃO SUPABASE =====

def initialize_supabase() -> Optional[Any]:
    """Inicializa integração com Supabase de forma segura"""
    try:
        from integrations.botscore_integration import BotScoreProIntegration
        
        botscore = BotScoreProIntegration()
        logger.info("✅ BotScoreProIntegration inicializado")
        
        # Testar conexão
        if botscore.test_connection():
            logger.info("✅ Conexão Supabase testada com sucesso")
            return botscore
        else:
            logger.warning("⚠️ Teste de conexão Supabase falhou")
            return None
            
    except ImportError as e:
        logger.warning(f"⚠️ Módulo BotScoreProIntegration não disponível: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar BotScoreProIntegration: {e}", exc_info=True)
        return None


botscore = initialize_supabase()

# ===== CLASSE PRINCIPAL =====

class BotConsolidado:
    """Bot de Futebol Consolidado - VERSÃO OTIMIZADA PARA 2000 REQUESTS/DIA"""
    
    def __init__(self):
        logger.info("🚀 Iniciando Bot Futebol Consolidado - MODO OTIMIZADO")
        
        # Validar configuração
        self._validate_config()
        
        # Inicializar clientes
        self.telegram_client = TelegramClient(Config.TELEGRAM_BOT_TOKEN)
        self.api_client = ApiFootballClient(Config.API_FOOTBALL_KEY, Config.API_DAILY_LIMIT)
        
        # Inicializar módulos
        self.modules: Dict[str, Any] = {}
        self._initialize_modules()
        
        # Inicializar scheduler
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._setup_scheduler()
        
        logger.info(f"📦 Módulos ativos: {list(self.modules.keys())}")
    
    def _validate_config(self):
        """Valida configurações críticas"""
        required_attrs = [
            'TELEGRAM_BOT_TOKEN',
            'API_FOOTBALL_KEY',
            'CHAT_ID_ELITE',
            'API_DAILY_LIMIT'
        ]
        
        missing = [attr for attr in required_attrs if not getattr(Config, attr, None)]
        
        if missing:
            raise ValueError(f"❌ Configurações obrigatórias ausentes: {missing}")
        
        # Validar horários de execução
        if Config.ELITE_ENABLED and not hasattr(Config, 'ELITE_EXECUTION_HOURS'):
            raise ValueError("❌ ELITE_EXECUTION_HOURS não configurado")
        
        if Config.REGRESSAO_ENABLED and not hasattr(Config, 'REGRESSAO_EXECUTION_HOURS'):
            raise ValueError("❌ REGRESSAO_EXECUTION_HOURS não configurado")
    
    def _initialize_modules(self):
        """Inicializa módulos de forma segura"""
        module_configs = [
            ('elite', Config.ELITE_ENABLED, JogosEliteModule, "Elite"),
            ('regressao', Config.REGRESSAO_ENABLED, RegressaoMediaModule, "Regressão"),
        ]
        
        for key, enabled, module_class, name in module_configs:
            if enabled:
                try:
                    self.modules[key] = module_class(self.telegram_client, self.api_client)
                    logger.info(f"✅ Módulo {name} inicializado")
                except Exception as e:
                    logger.error(f"❌ Erro ao inicializar módulo {name}: {e}")
        
        # Campeonatos (import dinâmico)
        if Config.CAMPEONATOS_ENABLED:
            try:
                from modules.campeonatos_padrao import CampeonatosPadraoModule
                self.modules['campeonatos'] = CampeonatosPadraoModule(
                    self.telegram_client, 
                    self.api_client
                )
                logger.info("✅ Módulo Campeonatos inicializado")
            except ImportError:
                logger.warning("⚠️ Módulo Campeonatos não encontrado")
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar módulo Campeonatos: {e}")
    
    def _setup_scheduler(self):
        """Configura agendamento otimizado para 2000 requests/dia"""
        
        job_config = {
            'max_instances': 1,
            'coalesce': True,
            'misfire_grace_time': 3600
        }
        
        # Elite: múltiplas execuções por dia
        if Config.ELITE_ENABLED and 'elite' in self.modules:
            for i, hour in enumerate(Config.ELITE_EXECUTION_HOURS):
                self.scheduler.add_job(
                    self.modules['elite'].execute,
                    'cron',
                    hour=hour,
                    minute=0,
                    id=f'elite_{i+1}',
                    **job_config
                )
            logger.info(
                f"⏰ Elite agendado: {len(Config.ELITE_EXECUTION_HOURS)}x/dia "
                f"(Horários UTC: {Config.ELITE_EXECUTION_HOURS})"
            )
        
        # Regressão: múltiplas execuções por dia
        if Config.REGRESSAO_ENABLED and 'regressao' in self.modules:
            for i, hour in enumerate(Config.REGRESSAO_EXECUTION_HOURS):
                self.scheduler.add_job(
                    self.modules['regressao'].execute,
                    'cron',
                    hour=hour,
                    minute=30,  # 30 min após Elite para evitar conflitos
                    id=f'regressao_{i+1}',
                    **job_config
                )
            logger.info(
                f"⏰ Regressão agendado: {len(Config.REGRESSAO_EXECUTION_HOURS)}x/dia "
                f"(Horários UTC: {Config.REGRESSAO_EXECUTION_HOURS})"
            )
        
        # Campeonatos: 1x por dia
        if Config.CAMPEONATOS_ENABLED and 'campeonatos' in self.modules:
            self.scheduler.add_job(
                self.modules['campeonatos'].execute,
                'cron',
                hour=9,
                minute=0,
                id='campeonatos_daily',
                **job_config
            )
            logger.info("⏰ Campeonatos agendado: 1x/dia às 09:00 UTC")
        
        # Testes imediatos (apenas em desenvolvimento)
        if getattr(Config, 'ENABLE_IMMEDIATE_TESTS', False):
            self._schedule_immediate_tests()
        
        # Monitor API
        if hasattr(Config, 'API_MONITOR_HOURS'):
            for i, hour in enumerate(Config.API_MONITOR_HOURS):
                self.scheduler.add_job(
                    self.log_api_usage,
                    'cron',
                    hour=hour,
                    minute=45,
                    id=f'api_monitor_{i+1}',
                    **job_config
                )
            logger.info(
                f"⏰ Monitor API agendado: {len(Config.API_MONITOR_HOURS)}x/dia "
                f"(Horários UTC: {Config.API_MONITOR_HOURS})"
            )
        
        # Keep-alive
        self.scheduler.add_job(
            keep_alive,
            'interval',
            minutes=30,
            id='keep_alive',
            **job_config
        )
        logger.info("⏰ Keep-alive agendado: a cada 30 minutos")
    
    def _schedule_immediate_tests(self):
        """Agenda testes imediatos (apenas desenvolvimento)"""
        now_utc = datetime.now(timezone.utc)
        
        test_configs = [
            ('elite', Config.ELITE_ENABLED, Config.TEST_DELAY_ELITE),
            ('regressao', Config.REGRESSAO_ENABLED, Config.TEST_DELAY_REGRESSAO)
        ]
        
        for module_name, enabled, delay in test_configs:
            if enabled and module_name in self.modules:
                test_time = now_utc + timedelta(minutes=delay)
                self.scheduler.add_job(
                    self.modules[module_name].execute,
                    'date',
                    run_date=test_time,
                    id=f'{module_name}_test_now',
                    max_instances=1
                )
                logger.info(
                    f"🧪 TESTE {module_name.capitalize()}: "
                    f"{test_time.strftime('%H:%M:%S')} UTC"
                )
    
    async def log_api_usage(self):
        """Monitor API com informações detalhadas da quota diária"""
        try:
            stats = self.api_client.get_daily_usage_stats()
            
            # Determinar status
            status_map = [
                (40, "🟢", "EXCELENTE"),
                (60, "🟡", "BOM"),
                (80, "🟠", "ATENÇÃO"),
                (100, "🔴", "CRÍTICO")
            ]
            
            status_emoji, status_text = "🔴", "CRÍTICO"
            for threshold, emoji, text in status_map:
                if stats['bot_percentage'] < threshold:
                    status_emoji, status_text = emoji, text
                    break
            
            # Informações da conta
            account_info = ""
            if stats.get('account_remaining') is not None:
                account_info = (
                    f"\n🏦 **Conta:** {stats['account_remaining']}/"
                    f"{stats['account_limit']} restantes"
                )
            
            message = f"""{status_emoji} **Relatório API Diário**

🤖 **Bot:** {stats['bot_used']}/{stats['bot_limit']} ({stats['bot_percentage']}%)
⚡ **Restante:** {stats['bot_remaining']} requests{account_info}
📅 **Reset:** {stats['reset_time']}
🗓️ **Data:** {stats['date']}

💡 **Status:** {status_text}
🎯 **Estratégia:** Elite {len(Config.ELITE_EXECUTION_HOURS)}x + Regressão {len(Config.REGRESSAO_EXECUTION_HOURS)}x + Campeonatos 1x/dia
📊 **Quota Alocada:** {Config.API_DAILY_LIMIT} requests/dia de 7500 totais"""
            
            await self.telegram_client.send_admin_message(message)
            logger.info(
                f"📊 API Usage: {stats['bot_used']}/{stats['bot_limit']} "
                f"({stats['bot_percentage']}%) - {status_text}"
            )
            
        except Exception as e:
            logger.error(f"❌ Erro no monitor de API: {e}", exc_info=True)
    
    async def send_startup_message(self):
        """Envia mensagem de inicialização otimizada"""
        try:
            stats = self.api_client.get_daily_usage_stats()
            
            modules_text = "\n".join([
                f"✅ {name.capitalize()}: {len(getattr(Config, f'{name.upper()}_EXECUTION_HOURS', [1]))}x/dia"
                for name in self.modules.keys()
            ])
            
            startup_message = f"""🚀 **BOT FUTEBOL CONSOLIDADO INICIADO**

🔧 **MODO OTIMIZADO PARA 2000 REQUESTS/DIA**
📊 Módulos ativos: {len(self.modules)}
⏰ Jobs agendados: {len(self.scheduler.get_jobs())}

📈 **Módulos:**
{modules_text}

🔧 **API Status:**
📊 Usado hoje: {stats['bot_used']}/{stats['bot_limit']} ({stats['bot_percentage']}%)
⚡ Restante: {stats['bot_remaining']} requests
📅 Data: {stats['date']}

💡 Otimização implementada para trabalhar dentro do limite de {Config.API_DAILY_LIMIT} requests/dia
⏰ {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC"""
            
            await self.telegram_client.send_admin_message(startup_message)
            logger.info("📨 Mensagem de startup enviada")
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem de startup: {e}", exc_info=True)
    
    async def start(self):
        """Inicia o bot com configurações otimizadas"""
        try:
            # Testar conexão Telegram
            telegram_ok = await self.telegram_client.test_connection()
            if not telegram_ok:
                raise ConnectionError("❌ Falha na conexão com Telegram - verificar token")
            
            self.scheduler.start()
            logger.info("⏰ Scheduler iniciado")
            
            await self.send_startup_message()
            await keep_alive()
            
            logger.info("✅ Bot iniciado com sucesso!")
            logger.info(f"📦 Módulos ativos: {list(self.modules.keys())}")
            logger.info(f"⏰ Jobs agendados: {len(self.scheduler.get_jobs())}")
            logger.info("🔄 Entrando no loop principal...")
            
            # Loop principal
            while True:
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("🛑 Interrupção do usuário detectada")
        except Exception as e:
            logger.error(f"💥 Erro crítico: {e}", exc_info=True)
            try:
                await self.telegram_client.send_admin_message(f"💥 Erro crítico no bot: {e}")
            except:
                pass
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Encerra o bot graciosamente"""
        logger.info("🛑 Encerrando bot...")
        
        # Parar scheduler
        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("⏰ Scheduler encerrado")
        
        # Fechar conexões HTTP
        if hasattr(self, 'api_client'):
            try:
                await self.api_client.close()
                logger.info("🔌 Conexões API fechadas")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao fechar API client: {e}")
        
        # Parar servidor keep-alive
        try:
            from utils.keep_alive import stop_server
            await stop_server()
            logger.info("🌐 Keep-alive encerrado")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao parar keep-alive: {e}")
        
        # Mensagem final
        try:
            await self.telegram_client.send_admin_message("🛑 Bot encerrado graciosamente")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao enviar mensagem de shutdown: {e}")
        
        logger.info("👋 Bot encerrado com sucesso")


# ===== FUNÇÃO PRINCIPAL =====

async def main():
    """Função principal com dashboard de configuração"""
    
    # Dashboard de configuração no console
    if hasattr(Config, 'print_startup_info'):
        Config.print_startup_info()
    
    # Inicializar e executar bot
    bot = BotConsolidado()
    await bot.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Aplicação interrompida pelo usuário")
    except Exception as e:
        logger.error(f"💥 Erro fatal: {e}", exc_info=True)

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

class SchedulerManager:
    """Gerenciador de tarefas agendadas"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.jobs = {}
        logger.info("📅 Scheduler Manager inicializado")
    
    def add_interval_job(self, func, interval_minutes, job_id, run_immediately=False, *args, **kwargs):
        """Adiciona job com intervalo em minutos - OPÇÃO DE EXECUÇÃO IMEDIATA"""
        try:
            job = self.scheduler.add_job(
                func,
                IntervalTrigger(minutes=interval_minutes),
                args=args,
                kwargs=kwargs,
                id=job_id,
                replace_existing=True,
                max_instances=1,
                next_run_time=(datetime.now() if run_immediately else None)  # EXECUÇÃO IMEDIATA
            )
            self.jobs[job_id] = job
            execution_info = "execução imediata + " if run_immediately else ""
            logger.info(f"⏰ Job '{job_id}' adicionado - {execution_info}intervalo: {interval_minutes} min")
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar job '{job_id}': {e}", exc_info=True)
    
    def add_cron_job(self, func, hour, minute, job_id, *args, **kwargs):
        """Adiciona job com horário específico"""
        try:
            job = self.scheduler.add_job(
                func,
                CronTrigger(hour=hour, minute=minute),
                args=args,
                kwargs=kwargs,
                id=job_id,
                replace_existing=True,
                max_instances=1
            )
            self.jobs[job_id] = job
            logger.info(f"⏰ Job '{job_id}' adicionado - horário: {hour:02d}:{minute:02d}")
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar cron job '{job_id}': {e}", exc_info=True)
    
    def start(self):
        """Inicia o scheduler"""
        try:
            self.scheduler.start()
            logger.info(f"✅ Scheduler iniciado com {len(self.jobs)} jobs")
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar scheduler: {e}", exc_info=True)
    
    def shutdown(self):
        """Para o scheduler"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("🛑 Scheduler parado")
            else:
                logger.info("ℹ️ Scheduler já estava parado")
        except Exception as e:
            logger.error(f"❌ Erro ao parar scheduler: {e}", exc_info=True)

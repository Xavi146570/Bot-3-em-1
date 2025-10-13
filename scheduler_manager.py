import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

logger = logging.getLogger(__name__)

class SchedulerManager:
    """Gerenciador de tarefas agendadas"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.jobs = {}
        logger.info("📅 Scheduler Manager inicializado")
    
    def add_interval_job(self, func, interval_minutes, job_id, *args, **kwargs):
        """Adiciona job com intervalo em minutos"""
        try:
            job = self.scheduler.add_job(
                func,
                IntervalTrigger(minutes=interval_minutes),
                args=args,
                kwargs=kwargs,
                id=job_id,
                replace_existing=True,
                max_instances=1
            )
            self.jobs[job_id] = job
            logger.info(f"⏰ Job '{job_id}' adicionado - intervalo: {interval_minutes} min")
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar job '{job_id}': {e}")
    
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
            logger.error(f"❌ Erro ao adicionar cron job '{job_id}': {e}")
    
    def start(self):
        """Inicia o scheduler"""
        try:
            self.scheduler.start()
            logger.info(f"✅ Scheduler iniciado com {len(self.jobs)} jobs")
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar scheduler: {e}")
    
    def shutdown(self):
        """Para o scheduler"""
        try:
            self.scheduler.shutdown()
            logger.info("🛑 Scheduler parado")
        except Exception as e:
            logger.error(f"❌ Erro ao parar scheduler: {e}")


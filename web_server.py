import asyncio
import logging
from aiohttp import web
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class WebServer:
    """Servidor web para health checks e controle"""
    
    def __init__(self, modules):
        self.modules = modules
        self.app = web.Application()
        self.setup_routes()
        logger.info("🌐 Web Server inicializado")
    
    def setup_routes(self):
        """Configura rotas com suporte a múltiplos métodos HTTP"""
        # Health check aceita qualquer método (resolve erro 405)
        self.app.router.add_route('*', '/', self.health_check)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_head('/health', self.health_check)
        
        self.app.router.add_get('/status', self.get_status)
        self.app.router.add_post('/trigger/{module}', self.trigger_module)
    
    async def health_check(self, request):
        """Health check robusto para Render"""
        return web.json_response({
            "status": "healthy",
            "service": "Bot Futebol Consolidado",
            "timestamp": datetime.now().isoformat(),
            "modules_count": len(self.modules),
            "version": "1.0.0",
            "method": request.method,
            "uptime": "running"
        })
    
    async def get_status(self, request):
        """Status detalhado do sistema"""
        try:
            enabled_modules = Config.get_enabled_modules()
            
            return web.json_response({
                "system": {
                    "uptime": datetime.now().isoformat(),
                    "debug_mode": Config.DEBUG_MODE,
                    "dry_run": Config.DRY_RUN,
                    "port": Config.PORT
                },
                "modules": {
                    name: {"enabled": True, "config": config} 
                    for name, config in enabled_modules.items()
                },
                "endpoints": {
                    "health": "/health",
                    "status": "/status",
                    "trigger_elite": "/trigger/elite",
                    "trigger_regressao": "/trigger/regressao",
                    "trigger_campeonatos": "/trigger/campeonatos"
                }
            })
        except Exception as e:
            logger.error(f"Erro no /status: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def trigger_module(self, request):
        """Executa módulo manualmente via API"""
        module_name = request.match_info['module']
        
        if module_name not in self.modules:
            return web.json_response({
                "error": "Módulo não encontrado",
                "available_modules": list(self.modules.keys()),
                "usage": f"POST /trigger/{{module}} onde module = {list(self.modules.keys())}"
            }, status=404)
        
        try:
            logger.info(f"🎯 Executando '{module_name}' via API trigger")
            
            # Executar módulo em background para resposta rápida
            asyncio.create_task(self.modules[module_name].execute())
            
            return web.json_response({
                "status": "success",
                "message": f"Módulo '{module_name}' iniciado com sucesso",
                "module": module_name,
                "timestamp": datetime.now().isoformat(),
                "execution": "background"
            })
            
        except Exception as e:
            logger.error(f"❌ Erro no trigger do módulo '{module_name}': {e}")
            return web.json_response({
                "error": f"Erro ao executar módulo: {str(e)}",
                "module": module_name,
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def start_server(self):
        """Inicia servidor web"""
        try:
            runner = web.AppRunner(self.app)
            await runner.setup()
            
            site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
            await site.start()
            
            logger.info(f"🌐 Servidor iniciado na porta {Config.PORT}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar servidor: {e}")
            raise

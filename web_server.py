from aiohttp import web
from datetime import datetime
from config import Config
import logging

logger = logging.getLogger(__name__)

class WebServer:
    def __init__(self, modules):
        self.modules = modules
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        self.app.router.add_get('/', self.health_check)
        self.app.router.add_get('/status', self.get_status)
        self.app.router.add_post('/trigger/{module}', self.trigger_module)
    
    async def health_check(self, request):
        return web.json_response({
            "status": "active",
            "service": "Bot Futebol Consolidado",
            "timestamp": datetime.now().isoformat(),
            "modules": list(self.modules.keys())
        })
    
    async def get_status(self, request):
        return web.json_response({
            "modules": {name: "active" for name in self.modules.keys()},
            "config": {
                "elite_threshold": Config.ELITE_GOALS_THRESHOLD,
                "regressao_max_days": Config.MAX_LAST_MATCH_AGE_DAYS
            }
        })
    
    async def trigger_module(self, request):
        module_name = request.match_info['module']
        
        if module_name not in self.modules:
            return web.json_response({"error": "Módulo não encontrado"}, status=404)
        
        try:
            await self.modules[module_name].execute()
            return web.json_response({"status": "success", "module": module_name})
        except Exception as e:
            logger.error(f"Erro ao executar {module_name}: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def start_server(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
        await site.start()
        logger.info(f"Servidor web iniciado na porta {Config.PORT}")

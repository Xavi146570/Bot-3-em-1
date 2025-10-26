import logging
import os
from aiohttp import web
from datetime import datetime

logger = logging.getLogger(__name__)

# Variáveis globais para gestão do servidor
app = web.Application()
server_runner = None
server_site = None
server_started = False

async def health_check(request):
    """Endpoint de health check para o Render"""
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    # Tentar obter stats da API se disponível
    try:
        # Assumindo que o api_client está disponível globalmente ou pode ser importado
        from main import bot_instance
        if hasattr(bot_instance, 'api_client'):
            api_stats = bot_instance.api_client.get_monthly_usage_stats()
            api_info = f"{api_stats['used']}/{api_stats['limit']} ({api_stats['percentage_used']}%)"
        else:
            api_info = "N/A"
    except:
        api_info = "N/A"
    
    response_data = {
        "status": "healthy",
        "timestamp": current_time,
        "service": "Bot Futebol Consolidado",
        "mode": "economia",
        "api_usage": api_info,
        "uptime": "running"
    }
    
    logger.info("✅ Keep-alive: Serviço mantido acordado")
    return web.json_response(response_data)

async def root_handler(request):
    """Handler para rota raiz com dashboard"""
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    # Tentar obter informações do bot
    try:
        from main import bot_instance
        if hasattr(bot_instance, 'api_client'):
            api_stats = bot_instance.api_client.get_monthly_usage_stats()
            modules_info = list(bot_instance.modules.keys()) if hasattr(bot_instance, 'modules') else []
            jobs_count = len(bot_instance.scheduler.get_jobs()) if hasattr(bot_instance, 'scheduler') else 0
        else:
            api_stats = {'used': 0, 'limit': 2000, 'percentage_used': 0, 'remaining': 2000, 'month': 'N/A'}
            modules_info = []
            jobs_count = 0
    except:
        api_stats = {'used': 0, 'limit': 2000, 'percentage_used': 0, 'remaining': 2000, 'month': 'N/A'}
        modules_info = []
        jobs_count = 0
    
    status_color = "#28a745" if api_stats['percentage_used'] < 70 else "#ffc107" if api_stats['percentage_used'] < 90 else "#dc3545"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bot Futebol Consolidado</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f8f9fa; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 800px; margin: 0 auto; }}
            .status {{ color: #28a745; font-weight: bold; font-size: 18px; }}
            .warning {{ color: #ffc107; font-weight: bold; }}
            .info {{ color: #17a2b8; }}
            .api-usage {{ color: {status_color}; font-weight: bold; }}
            .module {{ background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 5px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #6c757d; font-size: 12px; }}
        </style>
        <script>
            setTimeout(function(){{ location.reload(); }}, 300000); // Refresh a cada 5 minutos
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Bot Futebol Consolidado</h1>
            <p class="status">✅ Status: Online e Funcionando</p>
            <p class="warning">⚠️ Modo: Economia de API Ativado</p>
            <p class="info">📅 Última verificação: {current_time}</p>
            
            <h3>📊 API Usage:</h3>
            <p class="api-usage">Usado: {api_stats['used']}/{api_stats['limit']} ({api_stats['percentage_used']}%)</p>
            <p class="info">Restante: {api_stats['remaining']} requests | Mês: {api_stats['month']}</p>
            
            <h3>📦 Módulos Ativos ({len(modules_info)}):</h3>
            <div class="module">🌟 <strong>Elite:</strong> 1x/dia às 08:00 Lisboa (apenas hoje)</div>
            <div class="module">📈 <strong>Regressão:</strong> 1x/dia às 10:00 Lisboa (ligas + watchlist)</div>
            <div class="module">❌ <strong>Campeonatos:</strong> Desativado temporariamente</div>
            
            <h3>⏰ Próximas Execuções:</h3>
            <p>🌟 Elite: Diariamente às 07:00 UTC<br>
               📈 Regressão: Diariamente às 09:00 UTC<br>
               📊 Monitor API: 08:30 e 20:30 UTC</p>
            
            <div class="footer">
                <p>Bot otimizado para economia de API | Jobs agendados: {jobs_count}</p>
                <p>Auto-refresh em 5 minutos</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return web.Response(text=html_content, content_type='text/html')

# Configurar rotas da aplicação
app.router.add_get('/', root_handler)
app.router.add_get('/health', health_check)
app.router.add_head('/', health_check)  # Para health checks do Render
app.router.add_head('/health', health_check)

async def start_server():
    """Inicia o servidor keep-alive"""
    global server_runner, server_site, server_started
    
    if server_started:
        logger.info("✅ Keep-alive: Servidor já está a correr")
        return True
    
    try:
        port = int(os.getenv('PORT', 8080))
        
        server_runner = web.AppRunner(app)
        await server_runner.setup()
        
        server_site = web.TCPSite(server_runner, '0.0.0.0', port)
        await server_site.start()
        
        server_started = True
        logger.info(f"🌐 Servidor keep-alive iniciado na porta {port}")
        logger.info(f"🔗 Dashboard: http://0.0.0.0:{port}")
        logger.info(f"🔗 Health check: http://0.0.0.0:{port}/health")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar servidor keep-alive: {e}")
        return False

async def stop_server():
    """Para o servidor keep-alive graciosamente"""
    global server_runner, server_site, server_started
    
    try:
        if server_site:
            await server_site.stop()
            server_site = None
            logger.info("🛑 Server site parado")
        
        if server_runner:
            await server_runner.cleanup()
            server_runner = None
            logger.info("🛑 Server runner limpo")
        
        server_started = False
        logger.info("🌐 Servidor keep-alive encerrado graciosamente")
        
    except Exception as e:
        logger.error(f"❌ Erro ao parar servidor keep-alive: {e}")

async def keep_alive():
    """
    Função principal de keep-alive que é chamada pelo scheduler.
    Inicia o servidor na primeira chamada e mantém logs nas subsequentes.
    """
    global server_started
    
    if not server_started:
        success = await start_server()
        if success:
            logger.info("💓 Keep-alive: Servidor HTTP iniciado com sucesso")
        else:
            logger.error("❌ Keep-alive: Falha ao iniciar servidor HTTP")
    else:
        # Log periódico para mostrar que está vivo
        logger.info("💓 Keep-alive: Bot ativo e aguardando execuções agendadas")
        
        # Verificar se o servidor ainda está a responder
        try:
            import httpx
            port = int(os.getenv('PORT', 8080))
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"http://localhost:{port}/health")
                if response.status_code == 200:
                    logger.debug("🔍 Keep-alive: Health check local OK")
                else:
                    logger.warning(f"⚠️ Keep-alive: Health check retornou {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Keep-alive: Não foi possível verificar health check local: {e}")

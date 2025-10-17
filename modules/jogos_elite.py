import asyncio
import logging
import unicodedata
import re
from datetime import datetime, timedelta
from config import Config
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from data.elite_teams import ELITE_TEAMS

logger = logging.getLogger(__name__)

class JogosEliteModule:
    """Módulo para monitorar jogos de times de elite com alta média de gols"""
    
    def __init__(self, telegram_client: TelegramClient, api_client: ApiFootballClient):
        self.telegram_client = telegram_client
        self.api_client = api_client
        self.elite_teams = ELITE_TEAMS
        self.elite_teams_normalized = {self.normalize_name(team) for team in self.elite_teams}
        self.notified_fixtures = set()
        
        logger.info(f"🌟 Módulo Elite inicializado com {len(self.elite_teams)} times")
    
    def normalize_name(self, name):
        """Normaliza nomes de times para melhor correspondência"""
        if not name:
            return ""
        # Remove acentos
        name = unicodedata.normalize('NFKD', name)
        name = ''.join(c for c in name if not unicodedata.combining(c))
        # Converte para minúsculas e remove caracteres especiais
        name = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
        # Remove espaços extras
        name = ' '.join(name.split())
        return name
    
    async def execute(self):
    """Executa o monitoramento de jogos de elite - VERSÃO OTIMIZADA"""
    if not Config.ELITE_ENABLED:
        logger.info("Módulo Elite desabilitado")
        return
    
    logger.info("🌟 Executando monitoramento de jogos de elite...")
    
    try:
        # Buscar jogos dos próximos 2 dias
        all_matches = []
        for days_ahead in range(2):
            date_str = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            # CORREÇÃO: Garantir filtro NS (Not Started)
            matches = self.api_client.get_fixtures_by_date(date_str, league_id=None, status="NS")
            all_matches.extend(matches)
            logger.info(f"📅 {date_str}: {len(matches)} jogos encontrados")
        
        if not all_matches:
            message = "ℹ️ Nenhuma partida futura encontrada para análise de times elite."
            await self.telegram_client.send_message(Config.CHAT_ID_ELITE, message)
            return
        
        logger.info(f"📊 Total de jogos para analisar: {len(all_matches)}")
        notifications_sent = 0
        
        for match in all_matches:
            try:
                fixture_id = match['fixture']['id']
                if fixture_id in self.notified_fixtures:
                    continue
                
                home_team = match['teams']['home']['name']
                away_team = match['teams']['away']['name']
                # CORREÇÃO: Usar IDs do fixture (mais confiável)
                home_id = match['teams']['home']['id']
                away_id = match['teams']['away']['id']
                league_name = match['league']['name']
                league_id = match['league']['id']
                season = match['league']['season']  # Usar season da API
                
                qualifying_teams = []
                
                # Verificar time da casa
                if self.normalize_name(home_team) in self.elite_teams_normalized:
                    logger.debug(f"🔍 Verificando {home_team} (ID: {home_id})")
                    avg = self.api_client.get_team_goals_average(home_id, league_id, season)
                    logger.debug(f"📊 {home_team} média: {avg}")
                    if avg is not None and avg >= Config.ELITE_GOALS_THRESHOLD:
                        qualifying_teams.append(f"🏠 {home_team}: {avg:.2f} gols/jogo")
                
                # Verificar time visitante
                if self.normalize_name(away_team) in self.elite_teams_normalized:
                    logger.debug(f"🔍 Verificando {away_team} (ID: {away_id})")
                    avg = self.api_client.get_team_goals_average(away_id, league_id, season)
                    logger.debug(f"📊 {away_team} média: {avg}")
                    if avg is not None and avg >= Config.ELITE_GOALS_THRESHOLD:
                        qualifying_teams.append(f"✈️ {away_team}: {avg:.2f} gols/jogo")
                
                if qualifying_teams:
                    try:
                        dt = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                        formatted_datetime = dt.strftime("%d/%m/%Y às %H:%M UTC")
                    except:
                        formatted_datetime = match['fixture']['date']
                    
                    message = f"""🌟 <b>JOGO DE ELITE DETECTADO!</b> 🌟

🏆 <b>Liga:</b> {league_name}
⚽ <b>Partida:</b> {home_team} vs {away_team}
📅 <b>Data/Hora:</b> {formatted_datetime}

🔥 <b>Times com média ≥ {Config.ELITE_GOALS_THRESHOLD} gols:</b>
""" + "\n".join([f"   • {team}" for team in qualifying_teams]) + f"""

💡 <b>Análise:</b> Time(s) de elite com alta média ofensiva detectado(s)
🎯 <b>Recomendação:</b> Over 2.5 gols, BTTS

📊 <b>Critério:</b> Times da lista elite com ≥ {Config.ELITE_GOALS_THRESHOLD} gols/jogo na temporada atual
📅 <b>Gerado em:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')} UTC"""
                    
                    success = await self.telegram_client.send_message(Config.CHAT_ID_ELITE, message)
                    if success:
                        self.notified_fixtures.add(fixture_id)
                        notifications_sent += 1
                        logger.info(f"✅ Elite: {home_team} vs {away_team}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar partida elite: {e}")
                continue
        
        # Enviar resumo
        summary = f"ℹ️ <b>Monitoramento Elite Concluído</b>\n\n📊 Partidas analisadas: {len(all_matches)}\n🚨 Alertas enviados: {notifications_sent}\n⏰ Próxima verificação em {Config.ELITE_INTERVAL_HOURS}h"
        await self.telegram_client.send_message(Config.CHAT_ID_ELITE, summary)
        
    except Exception as e:
        logger.error(f"❌ Erro no módulo elite: {e}")
        await self.telegram_client.send_admin_message(f"Erro módulo elite: {e}")
    
    logger.info("🌟 Módulo Elite concluído")

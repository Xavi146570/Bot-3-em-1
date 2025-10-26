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
    """Módulo para monitorar jogos de times de elite - OTIMIZADO (apenas hoje)"""
    
    def __init__(self, telegram_client: TelegramClient, api_client: ApiFootballClient):
        self.telegram_client = telegram_client
        self.api_client = api_client
        self.elite_teams = ELITE_TEAMS
        self.elite_teams_normalized = {self.normalize_name(team) for team in self.elite_teams}
        self.notified_fixtures = set()
        
        logger.info(f"🌟 Módulo Elite inicializado com {len(self.elite_teams)} times - MODO ECONOMIA")
    
    def normalize_name(self, name):
        """Normaliza nomes de times para melhor correspondência"""
        if not name:
            return ""
        name = unicodedata.normalize('NFKD', name)
        name = ''.join(c for c in name if not unicodedata.combining(c))
        name = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
        name = ' '.join(name.split())
        return name
    
    async def execute(self):
        """Executa o monitoramento de jogos de elite - APENAS HOJE"""
        if not Config.ELITE_ENABLED:
            logger.info("Módulo Elite desabilitado")
            return
        
        logger.info("🌟 Executando monitoramento de jogos de elite (APENAS HOJE - MODO ECONOMIA)...")
        
        try:
            # Buscar jogos APENAS do dia atual
            today_date = datetime.utcnow()
            date_str = today_date.strftime("%Y-%m-%d")
            
            logger.info(f"🔍 Buscando jogos apenas para HOJE: {date_str}")
            
            # Buscar múltiplos status para hoje
            matches_ns = self.api_client.get_fixtures_by_date(date_str, league_id=None, status="NS") or []
            matches_tbd = self.api_client.get_fixtures_by_date(date_str, league_id=None, status="TBD") or []
            all_matches = matches_ns + matches_tbd
            
            logger.info(f"📅 HOJE {date_str}: NS={len(matches_ns)}, TBD={len(matches_tbd)}, Total={len(all_matches)}")
            
            if not all_matches:
                logger.warning("❌ NENHUM JOGO ENCONTRADO PARA HOJE")
                api_stats = self.api_client.get_monthly_usage_stats()
                message = f"""⚠️ **Elite**: Nenhuma partida encontrada para hoje

🔧 **API Usage:** {api_stats['used']}/{api_stats['limit']} ({api_stats['percentage_used']}%)
📅 {date_str}"""
                await self.telegram_client.send_message(Config.CHAT_ID_ELITE, message)
                return
            
            logger.info(f"📊 Total de jogos para analisar: {len(all_matches)}")
            
            # Verificar times elite nos jogos
            elite_found = []
            for match in all_matches:
                home_team = match['teams']['home']['name']
                away_team = match['teams']['away']['name']
                
                if self.normalize_name(home_team) in self.elite_teams_normalized:
                    elite_found.append(f"🏠 {home_team}")
                if self.normalize_name(away_team) in self.elite_teams_normalized:
                    elite_found.append(f"✈️ {away_team}")
            
            logger.info(f"🌟 Times elite encontrados: {len(elite_found)}")
            
            notifications_sent = 0
            api_requests_for_stats = 0
            
            for match in all_matches:
                try:
                    fixture_id = match['fixture']['id']
                    if fixture_id in self.notified_fixtures:
                        continue
                    
                    home_team = match['teams']['home']['name']
                    away_team = match['teams']['away']['name']
                    home_id = match['teams']['home']['id']
                    away_id = match['teams']['away']['id']
                    league_name = match['league']['name']
                    league_id = match['league']['id']
                    season = match['league']['season']
                    
                    qualifying_teams = []
                    
                    # Verificar time da casa
                    if self.normalize_name(home_team) in self.elite_teams_normalized:
                        avg = self.api_client.get_team_goals_average(home_id, league_id, season)
                        api_requests_for_stats += 1
                        
                        if avg is not None and avg >= Config.ELITE_GOALS_THRESHOLD:
                            qualifying_teams.append(f"🏠 {home_team}: {avg:.2f} gols/jogo")
                            logger.info(f"✅ {home_team} QUALIFICADO!")
                    
                    # Verificar time visitante
                    if self.normalize_name(away_team) in self.elite_teams_normalized:
                        avg = self.api_client.get_team_goals_average(away_id, league_id, season)
                        api_requests_for_stats += 1
                        
                        if avg is not None and avg >= Config.ELITE_GOALS_THRESHOLD:
                            qualifying_teams.append(f"✈️ {away_team}: {avg:.2f} gols/jogo")
                            logger.info(f"✅ {away_team} QUALIFICADO!")
                    
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

📊 <b>Critério:</b> Times da lista elite com ≥ {Config.ELITE_GOALS_THRESHOLD} gols/jogo na temporada {season}
📅 <b>Gerado em:</b> {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC"""
                        
                        success = await self.telegram_client.send_message(Config.CHAT_ID_ELITE, message)
                        if success:
                            self.notified_fixtures.add(fixture_id)
                            notifications_sent += 1
                            logger.info(f"✅ Elite: {home_team} vs {away_team}")
                
                except Exception as e:
                    logger.error(f"❌ Erro ao processar partida elite: {e}", exc_info=True)
                    continue
            
            # Resumo com estatísticas de API
            api_stats = self.api_client.get_monthly_usage_stats()
            
            summary = f"""ℹ️ <b>Monitoramento Elite Concluído</b>

📊 Partidas analisadas: {len(all_matches)}
🌟 Times elite encontrados: {len(elite_found)}
🚨 Alertas enviados: {notifications_sent}

🔧 <b>API Usage:</b> {api_stats['used']}/{api_stats['limit']} ({api_stats['percentage_used']}%)
📈 Requests para stats: {api_requests_for_stats}
⚠️ Restante: {api_stats['remaining']} requests

⏰ Próxima execução: amanhã às 08:00 Lisboa
📅 {date_str}"""
            
            await self.telegram_client.send_message(Config.CHAT_ID_ELITE, summary)
            
        except Exception as e:
            logger.error(f"❌ Erro crítico no módulo Elite: {e}", exc_info=True)
            await self.telegram_client.send_admin_message(f"Erro crítico no módulo Elite: {e}")
        
        logger.info("🌟 Módulo Elite concluído")

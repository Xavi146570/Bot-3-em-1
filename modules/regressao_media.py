import asyncio
import logging
import pytz
from datetime import datetime, timedelta
from config import Config
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from data.leagues_config import REGRESSAO_LEAGUES

logger = logging.getLogger(__name__)

class RegressaoMediaModule:
    """Módulo para detectar oportunidades de regressão à média após jogos com poucos gols"""
    
    def __init__(self, telegram_client: TelegramClient, api_client: ApiFootballClient):
        self.telegram_client = telegram_client
        self.api_client = api_client
        self.allowed_leagues = REGRESSAO_LEAGUES
        self.notified_matches = set()
        
        logger.info(f"📈 Módulo Regressão inicializado com {len(self.allowed_leagues)} ligas")
    
    def is_under_15_result(self, match):
        """Detecta Under 1.5 gols"""
        try:
            goals = match.get('goals', {})
            home = goals.get('home', 0) if goals.get('home') is not None else 0
            away = goals.get('away', 0) if goals.get('away') is not None else 0
            return (home + away) < 2
        except:
            return False
    
    def is_exact_0x0_result(self, match):
        """Detecta especificamente 0x0"""
        try:
            goals = match.get('goals', {})
            home = goals.get('home', 0) if goals.get('home') is not None else 0
            away = goals.get('away', 0) if goals.get('away') is not None else 0
            return home == 0 and away == 0
        except:
            return False
    
    async def check_team_under_15(self, team_id, team_name):
        """Verifica se team vem de Under 1.5/0x0 na rodada anterior"""
        try:
            recent_matches = self.api_client.get_team_recent_matches(team_id, 1)
            if not recent_matches:
                return False, None
            
            last_match = recent_matches[0]
            is_under_15 = self.is_under_15_result(last_match)
            
            if is_under_15:
                is_0x0 = self.is_exact_0x0_result(last_match)
                goals = last_match.get('goals', {})
                score = f"{goals.get('home', 0)}x{goals.get('away', 0)}"
                
                opponent = (last_match['teams']['away']['name'] 
                           if last_match['teams']['home']['id'] == team_id 
                           else last_match['teams']['home']['name'])
                
                match_date = datetime.fromisoformat(last_match['fixture']['date'].replace('Z', '+00:00'))
                days_ago = (datetime.now(pytz.utc) - match_date).days
                
                if days_ago <= Config.MAX_LAST_MATCH_AGE_DAYS:
                    return True, {
                        'opponent': opponent,
                        'score': score,
                        'date': match_date.strftime('%d/%m'),
                        'is_0x0': is_0x0,
                        'days_ago': days_ago,
                        'league_name': last_match.get('league', {}).get('name', 'N/A')
                    }
            
            return False, None
            
        except Exception as e:
            logger.error(f"❌ Erro verificando {team_name}: {e}")
            return False, None
    
    async def execute(self):
        """Executa o monitoramento de regressão à média"""
        if not Config.REGRESSAO_ENABLED:
            return
        
        logger.info("📈 Executando monitoramento de regressão à média...")
        
        try:
            # Verificar horário ativo
            lisbon_tz = pytz.timezone("Europe/Lisbon")
            now_lisbon = datetime.now(lisbon_tz)
            
            if not (Config.REGRESSAO_ACTIVE_HOURS_START <= now_lisbon.hour <= Config.REGRESSAO_ACTIVE_HOURS_END):
                return
            
            today_str = now_lisbon.strftime("%Y-%m-%d")
            current_date = now_lisbon.date()
            
            # Buscar jogos de hoje para todas as ligas permitidas
            all_matches = []
            for league_id in self.allowed_leagues.keys():
                matches = self.api_client.get_fixtures_by_date(today_str, league_id)
                all_matches.extend(matches)
            
            alerts_sent = 0
            
            for match in all_matches:
                try:
                    fixture_id = match['fixture']['id']
                    home_team = match['teams']['home']['name']
                    away_team = match['teams']['away']['name']
                    home_id = match['teams']['home']['id']
                    away_id = match['teams']['away']['id']
                    league_id = match['league']['id']
                    
                    league_info = self.allowed_leagues.get(league_id)
                    if not league_info:
                        continue
                    
                    # Verificar se o jogo é realmente hoje
                    match_datetime = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                    match_date_lisbon = match_datetime.astimezone(lisbon_tz).date()
                    
                    if match_date_lisbon != current_date:
                        continue
                    
                    # Verificar histórico dos times
                    home_under, home_info = await self.check_team_under_15(home_id, home_team)
                    away_under, away_info = await self.check_team_under_15(away_id, away_team)
                    
                    if home_under or away_under:
                        notification_key = f"regressao_{today_str}_{fixture_id}"
                        
                        if notification_key not in self.notified_matches:
                            teams_info = ""
                            priority = "NORMAL"
                            
                            if home_under and home_info:
                                indicator = "🔥 0x0" if home_info['is_0x0'] else f"Under 1.5 ({home_info['score']})"
                                teams_info += f"🏠 <b>{home_team}</b> vem de <b>{indicator}</b> vs {home_info['opponent']} ({home_info['date']} - {home_info['days_ago']}d)\n"
                                if home_info['is_0x0']:
                                    priority = "MÁXIMA"
                            
                            if away_under and away_info:
                                indicator = "🔥 0x0" if away_info['is_0x0'] else f"Under 1.5 ({away_info['score']})"
                                teams_info += f"✈️ <b>{away_team}</b> vem de <b>{indicator}</b> vs {away_info['opponent']} ({away_info['date']} - {away_info['days_ago']}d)\n"
                                if away_info['is_0x0']:
                                    priority = "MÁXIMA"
                            
                            confidence = "ALTÍSSIMA" if (home_under and away_under) else ("ALTA" if priority == "MÁXIMA" else "MÉDIA")
                            
                            tier_indicator = "⭐" * league_info.get('tier', 1)
                            
                            message = f"""🚨 <b>ALERTA REGRESSÃO À MÉDIA - PRIORIDADE {priority}</b>

🏆 <b>{league_info['name']} ({league_info['country']}) {tier_indicator}</b>
⚽ <b>{home_team} vs {away_team}</b>

{teams_info}
📊 <b>Confiança:</b> {confidence}
📈 <b>Over 1.5 histórico da liga:</b> {league_info['over_15_percentage']}%
📉 <b>0x0 histórico da liga:</b> {league_info['0x0_ft_percentage']}%

💡 <b>Teoria:</b> Regressão à média após seca de gols na rodada anterior

🎯 <b>Sugestões:</b> 
• 🟢 Over 1.5 Gols (Principal)
• 🟢 Over 0.5 Gols (Conservador)
• 🟢 BTTS (Ambas marcam)

🕐 <b>HOJE às {match_datetime.astimezone(lisbon_tz).strftime('%H:%M')}</b>
📅 <b>{current_date.strftime('%d/%m/%Y')}</b>"""
                            
                            success = await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, message)
                            if success:
                                self.notified_matches.add(notification_key)
                                alerts_sent += 1
                                logger.info(f"✅ Regressão: {home_team} vs {away_team}")
                
                except Exception as e:
                    logger.error(f"❌ Erro processando jogo regressão: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"❌ Erro no módulo regressão: {e}")
            await self.telegram_client.send_admin_message(f"Erro módulo regressão: {e}")
        
        logger.info("📈 Módulo Regressão concluído")

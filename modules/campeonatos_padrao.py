import logging
from datetime import datetime, timedelta
import pytz
from config import Config
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from data.leagues_config import CAMPEONATOS_LEAGUES

logger = logging.getLogger(__name__)

class CampeonatosPadraoModule:
    """Módulo para análise de campeonatos padrão com estatísticas e tendências"""
    
    def __init__(self, telegram_client: TelegramClient, api_client: ApiFootballClient):
        self.telegram_client = telegram_client
        self.api_client = api_client
        # Normalizar chaves para int
        self.leagues_config = {int(k): v for k, v in CAMPEONATOS_LEAGUES.items()}
        self.notified_today = set()
        
        logger.info(f"🏆 Módulo Campeonatos inicializado com {len(self.leagues_config)} ligas")

    def analyze_team_form(self, team_id, team_name, league_id, season):
        """Analisa forma recente do time (últimos 5 jogos)"""
        try:
            recent_matches = self.api_client.get_team_recent_matches(team_id, 5)
            if not recent_matches:
                return None
            
            stats = {
                'wins': 0, 'draws': 0, 'losses': 0,
                'goals_for': 0, 'goals_against': 0,
                'over_25': 0, 'btts': 0, 'clean_sheets': 0
            }
            
            games_played = 0
            for match in recent_matches:
                if match['fixture']['status']['short'] != 'FT':
                    continue
                
                home_goals = match['goals']['home'] or 0
                away_goals = match['goals']['away'] or 0
                total_goals = home_goals + away_goals
                
                is_home = match['teams']['home']['id'] == team_id
                team_goals = home_goals if is_home else away_goals
                opponent_goals = away_goals if is_home else home_goals
                
                stats['goals_for'] += team_goals
                stats['goals_against'] += opponent_goals
                
                if team_goals > opponent_goals:
                    stats['wins'] += 1
                elif team_goals == opponent_goals:
                    stats['draws'] += 1
                else:
                    stats['losses'] += 1
                
                if total_goals > 2.5:
                    stats['over_25'] += 1
                
                if home_goals > 0 and away_goals > 0:
                    stats['btts'] += 1
                
                if opponent_goals == 0:
                    stats['clean_sheets'] += 1
                
                games_played += 1
            
            if games_played == 0:
                return None
            
            # Calcular percentuais
            stats['form_percentage'] = ((stats['wins'] * 3 + stats['draws']) / (games_played * 3)) * 100
            stats['over_25_percentage'] = (stats['over_25'] / games_played) * 100
            stats['btts_percentage'] = (stats['btts'] / games_played) * 100
            stats['games_played'] = games_played
            stats['avg_goals_for'] = stats['goals_for'] / games_played
            stats['avg_goals_against'] = stats['goals_against'] / games_played
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erro analisando forma de {team_name}: {e}")
            return None

    async def execute(self):
        """Executa a análise de campeonatos padrão"""
        if not Config.CAMPEONATOS_ENABLED:
            logger.info("🏆 Módulo Campeonatos desabilitado na configuração")
            return
        
        logger.info("🏆 Executando análise de campeonatos padrão...")
        
        try:
            lisbon_tz = pytz.timezone("Europe/Lisbon")
            now_lisbon = datetime.now(lisbon_tz)
            current_date = now_lisbon.date()
            
            logger.info(f"📅 Analisando jogos para {current_date.strftime('%d/%m/%Y')}")
            
            # Buscar jogos de hoje
            date_str_utc = datetime.utcnow().strftime("%Y-%m-%d")
            all_matches = []
            leagues_processed = 0
            
            for league_id, league_config in self.leagues_config.items():
                logger.info(f"🔍 Liga: {league_config['name']} (ID: {league_id})")
                
                matches_ns = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="NS") or []
                matches_tbd = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="TBD") or []
                matches = matches_ns + matches_tbd
                
                if matches:
                    all_matches.extend(matches)
                    logger.info(f"📊 {league_config['name']}: {len(matches)} jogos encontrados")
                else:
                    logger.info(f"📊 {league_config['name']}: 0 jogos encontrados")
                
                leagues_processed += 1
            
            logger.info(f"📊 TOTAL: {leagues_processed} ligas, {len(all_matches)} jogos para análise")
            
            if not all_matches:
                message = f"ℹ️ Campeonatos: Nenhum jogo encontrado para {current_date.strftime('%d/%m/%Y')} nas {len(self.leagues_config)} ligas configuradas"
                await self.telegram_client.send_message(Config.CHAT_ID_CAMPEONATOS, message)
                return
            
            # Analisar jogos
            insights_sent = 0
            games_analyzed = 0
            daily_key = current_date.strftime('%Y-%m-%d')
            
            for match in all_matches:
                try:
                    status = match.get('fixture', {}).get('status', {}).get('short')
                    if status not in ("NS", "TBD"):
                        continue
                    
                    fixture_id = match['fixture']['id']
                    home_team = match['teams']['home']['name']
                    away_team = match['teams']['away']['name']
                    home_id = match['teams']['home']['id']
                    away_id = match['teams']['away']['id']
                    league_id = int(match['league']['id'])
                    season = match['league']['season']
                    
                    league_config = self.leagues_config.get(league_id)
                    if not league_config:
                        continue
                    
                    # Verificar se é hoje
                    match_datetime = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                    match_date_lisbon = match_datetime.astimezone(lisbon_tz).date()
                    
                    if match_date_lisbon != current_date:
                        continue
                    
                    games_analyzed += 1
                    logger.debug(f"🔍 Analisando: {home_team} vs {away_team}")
                    
                    # Analisar forma dos times
                    home_form = self.analyze_team_form(home_id, home_team, league_id, season)
                    away_form = self.analyze_team_form(away_id, away_team, league_id, season)
                    
                    if not home_form or not away_form:
                        continue
                    
                    # Critérios para insight
                    insights = []
                    confidence_score = 0
                    
                    # Over 2.5
                    avg_over_25 = (home_form['over_25_percentage'] + away_form['over_25_percentage']) / 2
                    if avg_over_25 >= 70:
                        insights.append("🔥 Over 2.5 Gols")
                        confidence_score += 2
                    elif avg_over_25 >= 60:
                        insights.append("🟡 Over 2.5 Gols")
                        confidence_score += 1
                    
                    # BTTS
                    avg_btts = (home_form['btts_percentage'] + away_form['btts_percentage']) / 2
                    if avg_btts >= 60:
                        insights.append("⚽ BTTS")
                        confidence_score += 1
                    
                    # Forma
                    if home_form['form_percentage'] >= 70 and away_form['form_percentage'] <= 30:
                        insights.append(f"🏠 Vantagem Casa")
                        confidence_score += 1
                    elif away_form['form_percentage'] >= 70 and home_form['form_percentage'] <= 30:
                        insights.append(f"✈️ Vantagem Visitante")
                        confidence_score += 1
                    
                    # Enviar se score >= 2
                    if confidence_score >= 2 and insights:
                        notification_key = f"campeonatos_{daily_key}_{fixture_id}"
                        
                        if notification_key not in self.notified_today:
                            priority = "ALTA" if confidence_score >= 3 else "MÉDIA"
                            priority_emoji = "🔥" if confidence_score >= 3 else "🟡"
                            
                            message = f"""{priority_emoji} <b>ANÁLISE CAMPEONATOS - PRIORIDADE {priority}</b>

🏆 <b>{league_config['name']} ({league_config['country']})</b>
⚽ <b>{home_team} vs {away_team}</b>

📊 <b>Forma Recente (últimos 5 jogos):</b>
🏠 <b>{home_team}:</b> {home_form['wins']}V-{home_form['draws']}E-{home_form['losses']}D
   • Over 2.5: {home_form['over_25_percentage']:.0f}% | BTTS: {home_form['btts_percentage']:.0f}%

✈️ <b>{away_team}:</b> {away_form['wins']}V-{away_form['draws']}E-{away_form['losses']}D
   • Over 2.5: {away_form['over_25_percentage']:.0f}% | BTTS: {away_form['btts_percentage']:.0f}%

🎯 <b>Insights:</b>
""" + "\n".join([f"   • {insight}" for insight in insights]) + f"""

📈 <b>Confiança:</b> {confidence_score}/4
🕐 <b>HOJE às {match_datetime.astimezone(lisbon_tz).strftime('%H:%M')}</b>"""
                            
                            success = await self.telegram_client.send_message(Config.CHAT_ID_CAMPEONATOS, message)
                            if success:
                                self.notified_today.add(notification_key)
                                insights_sent += 1
                                logger.info(f"✅ Campeonatos: {home_team} vs {away_team}")
                
                except Exception as e:
                    logger.error(f"❌ Erro processando jogo: {e}")
                    continue
            
            # Resumo final
            summary = f"""🏆 <b>Análise Campeonatos Concluída</b>

📊 Jogos analisados: {games_analyzed}
🔍 Ligas verificadas: {leagues_processed}
📈 Insights enviados: {insights_sent}
🕐 {now_lisbon.strftime('%H:%M')} Lisboa
📅 {current_date.strftime('%d/%m/%Y')}"""
            
            await self.telegram_client.send_message(Config.CHAT_ID_CAMPEONATOS, summary)
        
        except Exception as e:
            logger.error(f"❌ Erro no módulo Campeonatos: {e}")
            await self.telegram_client.send_admin_message(f"Erro módulo Campeonatos: {e}")
        
        logger.info("🏆 Módulo Campeonatos concluído")

import logging
from datetime import datetime, timedelta
import pytz
from config import Config
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from data.leagues_config import CAMPEONATOS_LEAGUES

# ✅ INTEGRAÇÃO SUPABASE - Importar da main
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from main import botscore
except ImportError:
    botscore = None
    logging.warning("⚠️ BotScoreProIntegration não disponível - integração desabilitada")

logger = logging.getLogger(__name__)

class CampeonatosPadraoModule:
    """Módulo para análise de campeonatos padrão com estatísticas e tendências"""
    
    def __init__(self, telegram_client: TelegramClient, api_client: ApiFootballClient):
        self.telegram_client = telegram_client
        self.api_client = api_client
        self.notified_today = set()
        
        # Processar configuração das ligas de forma robusta
        self.leagues = []
        processed_count = 0
        skipped_count = 0
        
        logger.info(f"🔧 Processando {len(CAMPEONATOS_LEAGUES)} configurações de ligas...")
        
        for key, config in CAMPEONATOS_LEAGUES.items():
            try:
                league_id = None
                
                # Tentar obter league_id de várias formas
                if isinstance(key, int):
                    league_id = key
                elif isinstance(key, str) and key.isdigit():
                    league_id = int(key)
                elif isinstance(config, dict):
                    # Procurar nos campos do config
                    for field in ['league_id', 'id', 'api_id']:
                        if field in config and config[field] is not None:
                            try:
                                league_id = int(config[field])
                                break
                            except (ValueError, TypeError):
                                continue
                
                if league_id is None:
                    logger.warning(f"⚠️ Liga {key} ignorada: sem ID numérico válido")
                    skipped_count += 1
                    continue
                
                # Criar entrada processada
                league_entry = {
                    'league_id': league_id,
                    'name': config.get('name', f'Liga {league_id}'),
                    'country': config.get('country', 'N/A'),
                    'tier': config.get('tier', 1),
                    'original_key': key
                }
                
                self.leagues.append(league_entry)
                processed_count += 1
                
            except Exception as e:
                logger.error(f"❌ Erro processando liga {key}: {e}")
                skipped_count += 1
                continue
        
        logger.info(f"🏆 Módulo Campeonatos inicializado: {processed_count} ligas processadas, {skipped_count} ignoradas")
        
        if processed_count == 0:
            logger.error("❌ NENHUMA LIGA VÁLIDA ENCONTRADA - Verifica configuração CAMPEONATOS_LEAGUES")

    def analyze_team_form(self, team_id, team_name):
        """Analisa forma recente do time (últimos 5 jogos finalizados)"""
        try:
            recent_matches = self.api_client.get_team_recent_matches(team_id, 5)
            if not recent_matches:
                logger.debug(f"🔍 {team_name}: Sem histórico recente")
                return None
            
            stats = {
                'wins': 0, 'draws': 0, 'losses': 0,
                'goals_for': 0, 'goals_against': 0,
                'over_25': 0, 'btts': 0, 'clean_sheets': 0,
                'games_played': 0
            }
            
            for match in recent_matches:
                if match.get('fixture', {}).get('status', {}).get('short') != 'FT':
                    continue
                
                home_goals = match.get('goals', {}).get('home') or 0
                away_goals = match.get('goals', {}).get('away') or 0
                total_goals = home_goals + away_goals
                
                is_home = match.get('teams', {}).get('home', {}).get('id') == team_id
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
                
                stats['games_played'] += 1
            
            if stats['games_played'] == 0:
                return None
            
            # Calcular percentuais
            gp = stats['games_played']
            stats['form_percentage'] = ((stats['wins'] * 3 + stats['draws']) / (gp * 3)) * 100
            stats['over_25_percentage'] = (stats['over_25'] / gp) * 100
            stats['btts_percentage'] = (stats['btts'] / gp) * 100
            stats['avg_goals_for'] = stats['goals_for'] / gp
            stats['avg_goals_against'] = stats['goals_against'] / gp
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erro analisando forma de {team_name}: {e}")
            return None

    async def execute(self):
        """Executa a análise de campeonatos padrão"""
        if not Config.CAMPEONATOS_ENABLED:
            logger.info("🏆 Módulo Campeonatos desabilitado na configuração")
            return
        
        if not self.leagues:
            logger.error("❌ Nenhuma liga configurada - módulo não pode executar")
            await self.telegram_client.send_admin_message("Erro: Módulo Campeonatos sem ligas válidas configuradas")
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
            
            for league in self.leagues:
                league_id = league['league_id']
                league_name = league['name']
                
                logger.info(f"🔍 Liga: {league_name} (ID: {league_id})")
                
                try:
                    matches_ns = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="NS") or []
                    matches_tbd = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="TBD") or []
                    matches = matches_ns + matches_tbd
                    
                    if matches:
                        all_matches.extend(matches)
                        logger.info(f"📊 {league_name}: {len(matches)} jogos encontrados (NS={len(matches_ns)}, TBD={len(matches_tbd)})")
                        
                        # Debug: mostrar primeiros jogos
                        for i, match in enumerate(matches[:2]):
                            home = match['teams']['home']['name']
                            away = match['teams']['away']['name']
                            match_time = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                            logger.info(f"   {i+1}. {home} vs {away} às {match_time.astimezone(lisbon_tz).strftime('%H:%M')}")
                    else:
                        logger.info(f"📊 {league_name}: 0 jogos encontrados")
                    
                    leagues_processed += 1
                    
                except Exception as e:
                    logger.error(f"❌ Erro buscando jogos para {league_name} (ID: {league_id}): {e}")
                    continue
            
            logger.info(f"📊 TOTAL: {leagues_processed} ligas verificadas, {len(all_matches)} jogos para análise")
            
            if not all_matches:
                message = f"ℹ️ **Campeonatos Padrão**\n\n📊 Nenhum jogo encontrado para {current_date.strftime('%d/%m/%Y')}\n🔍 Ligas verificadas: {leagues_processed}"
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
                    
                    # Encontrar configuração da liga
                    league_config = next((l for l in self.leagues if l['league_id'] == league_id), None)
                    if not league_config:
                        logger.debug(f"Liga {league_id} não está na nossa configuração")
                        continue
                    
                    # Verificar se é hoje em Lisboa
                    match_datetime = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                    match_date_lisbon = match_datetime.astimezone(lisbon_tz).date()
                    
                    if match_date_lisbon != current_date:
                        continue
                    
                    games_analyzed += 1
                    logger.debug(f"🔍 Analisando: {home_team} vs {away_team}")
                    
                    # Analisar forma dos times
                    home_form = self.analyze_team_form(home_id, home_team)
                    away_form = self.analyze_team_form(away_id, away_team)
                    
                    if not home_form or not away_form:
                        logger.debug(f"❌ {home_team} vs {away_team}: Dados de forma insuficientes")
                        continue
                    
                    # Critérios para insights
                    insights = []
                    confidence_score = 0
                    market_recommendation = []
                    
                    # Over 2.5 Gols
                    avg_over_25 = (home_form['over_25_percentage'] + away_form['over_25_percentage']) / 2
                    if avg_over_25 >= 70:
                        insights.append("🔥 Over 2.5 Gols")
                        market_recommendation.append("Over 2.5")
                        confidence_score += 2
                    elif avg_over_25 >= 60:
                        insights.append("🟡 Over 2.5 Gols")
                        market_recommendation.append("Over 2.5")
                        confidence_score += 1
                    
                    # BTTS (Both Teams To Score)
                    avg_btts = (home_form['btts_percentage'] + away_form['btts_percentage']) / 2
                    if avg_btts >= 60:
                        insights.append("⚽ BTTS")
                        market_recommendation.append("BTTS")
                        confidence_score += 1
                    
                    # Vantagem de Forma
                    form_advantage = None
                    if home_form['form_percentage'] >= 70 and away_form['form_percentage'] <= 30:
                        insights.append("🏠 Vantagem Casa")
                        form_advantage = "home"
                        confidence_score += 1
                    elif away_form['form_percentage'] >= 70 and home_form['form_percentage'] <= 30:
                        insights.append("✈️ Vantagem Visitante")
                        form_advantage = "away"
                        confidence_score += 1
                    
                    # Enviar insight se confiança >= 2
                    if confidence_score >= 2 and insights:
                        notification_key = f"campeonatos_{daily_key}_{fixture_id}"
                        
                        if notification_key not in self.notified_today:
                            priority = "ALTA" if confidence_score >= 3 else "MÉDIA"
                            priority_emoji = "🔥" if confidence_score >= 3 else "🟡"
                            
                            # Calcular confiança numérica para Supabase
                            confidence_numeric = min(95, 60 + (confidence_score * 10))
                            
                            message = f"""{priority_emoji} <b>ANÁLISE CAMPEONATOS - PRIORIDADE {priority}</b>

🏆 <b>{league_config['name']} ({league_config['country']})</b>
⚽ <b>{home_team} vs {away_team}</b>

📊 <b>Forma Recente (últimos 5 jogos FT):</b>
🏠 <b>{home_team}:</b> {home_form['wins']}V-{home_form['draws']}E-{home_form['losses']}D ({home_form['games_played']} jogos)
   • Over 2.5: {home_form['over_25_percentage']:.0f}% | BTTS: {home_form['btts_percentage']:.0f}%
   • Forma: {home_form['form_percentage']:.0f}%

✈️ <b>{away_team}:</b> {away_form['wins']}V-{away_form['draws']}E-{away_form['losses']}D ({away_form['games_played']} jogos)
   • Over 2.5: {away_form['over_25_percentage']:.0f}% | BTTS: {away_form['btts_percentage']:.0f}%
   • Forma: {away_form['form_percentage']:.0f}%

🎯 <b>Insights Identificados:</b>
""" + "\n".join([f"   • {insight}" for insight in insights]) + f"""

📈 <b>Confiança:</b> {confidence_score}/4
🕐 <b>HOJE às {match_datetime.astimezone(lisbon_tz).strftime('%H:%M')}</b>
📅 <b>{current_date.strftime('%d/%m/%Y')}</b>"""
                            
                            success = await self.telegram_client.send_message(Config.CHAT_ID_CAMPEONATOS, message)
                            if success:
                                self.notified_today.add(notification_key)
                                insights_sent += 1
                                logger.info(f"✅ Campeonatos: {home_team} vs {away_team} (confiança: {confidence_score})")
                                
                                # ✅ INTEGRAÇÃO SUPABASE - LINHA 3
                                if botscore:
                                    try:
                                        # Determinar mercado principal
                                        if "Over 2.5" in market_recommendation:
                                            main_market = "Over 2.5 Goals"
                                            estimated_odd = 1.75
                                        elif "BTTS" in market_recommendation:
                                            main_market = "BTTS"
                                            estimated_odd = 1.80
                                        else:
                                            main_market = " / ".join(market_recommendation) if market_recommendation else "Análise Estatística"
                                            estimated_odd = 1.70
                                        
                                        opportunity_data = {
                                            'bot_name': 'Bot Campeonatos 3em1',
                                            'match_info': f"{home_team} vs {away_team}",
                                            'league': league_config['name'],
                                            'market': main_market,
                                            'odd': estimated_odd,
                                            'confidence': confidence_numeric,
                                            'status': 'pre-match',
                                            'match_date': match_datetime.isoformat(),
                                            'analysis': f"Forma: Casa {home_form['form_percentage']:.0f}% vs Fora {away_form['form_percentage']:.0f}%. {', '.join(insights)}"
                                        }
                                        
                                        resultado = botscore.send_opportunity(opportunity_data)
                                        if resultado:
                                            logger.info(f"📤 Oportunidade enviada para ScorePro: {home_team} vs {away_team}")
                                        else:
                                            logger.warning(f"⚠️ Falha ao enviar para ScorePro: {home_team} vs {away_team}")
                                    except Exception as e:
                                        logger.error(f"❌ Erro ao enviar para Supabase: {e}")
                
                except Exception as e:
                    logger.error(f"❌ Erro processando jogo: {e}")
                    continue
            
            # Resumo final sempre enviado
            summary = f"""🏆 <b>Análise Campeonatos Concluída</b>

📊 Jogos analisados: {games_analyzed}
🔍 Ligas verificadas: {leagues_processed}
📈 Insights enviados: {insights_sent}
🕐 Horário: {now_lisbon.strftime('%H:%M')} Lisboa
📅 {current_date.strftime('%d/%m/%Y')}

🔧 Configuração: {len(self.leagues)} ligas ativas"""
            
            await self.telegram_client.send_message(Config.CHAT_ID_CAMPEONATOS, summary)
        
        except Exception as e:
            logger.error(f"❌ Erro crítico no módulo Campeonatos: {e}", exc_info=True)
            await self.telegram_client.send_admin_message(f"Erro crítico no módulo Campeonatos: {e}")
        
        logger.info("🏆 Módulo Campeonatos concluído")

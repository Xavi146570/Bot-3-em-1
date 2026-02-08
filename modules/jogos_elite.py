import asyncio
import logging
import unicodedata
import re
from datetime import datetime, timedelta, timezone
from config import Config
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from data.elite_teams import ELITE_TEAMS

logger = logging.getLogger(__name__)

class JogosEliteModule:
    """Módulo para monitorar jogos de times de elite - OTIMIZADO"""
    
    def __init__(self, telegram_client: TelegramClient, api_client: ApiFootballClient, botscore=None):
        self.telegram_client = telegram_client
        self.api_client = api_client
        self.botscore = botscore  # ✅ INTEGRAÇÃO SUPABASE
        self.elite_teams = ELITE_TEAMS
        self.elite_teams_normalized = {self.normalize_name(team) for team in self.elite_teams}
        self.notified_fixtures = set()
        
        logger.info(f"🌟 Módulo Elite inicializado com {len(self.elite_teams)} times - MODO OTIMIZADO")
    
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
        
        logger.info("🌟 Executando monitoramento de jogos de elite (APENAS HOJE - MODO OTIMIZADO)...")
        
        try:
            # Buscar jogos APENAS do dia atual
            today_date = datetime.now(timezone.utc)
            date_str = today_date.strftime("%Y-%m-%d")
            
            logger.info(f"🔍 Buscando jogos apenas para HOJE: {date_str}")
            
            # Buscar múltiplos status para hoje
            matches_ns = self.api_client.get_fixtures_by_date(date_str, league_id=None, status="NS") or []
            matches_tbd = self.api_client.get_fixtures_by_date(date_str, league_id=None, status="TBD") or []
            all_matches = matches_ns + matches_tbd
            
            logger.info(f"📅 HOJE {date_str}: NS={len(matches_ns)}, TBD={len(matches_tbd)}, Total={len(all_matches)}")
            
            if not all_matches:
                logger.warning("❌ NENHUM JOGO ENCONTRADO PARA HOJE")
                try:
                    api_stats = self.api_client.get_daily_usage_stats()
                    api_info = f"{api_stats['bot_used']}/{api_stats['bot_limit']} ({api_stats['bot_percentage']}%)"
                except:
                    api_info = "N/A"
                
                message = f"""⚠️ **Elite**: Nenhuma partida encontrada para hoje

🔧 **API Usage:** {api_info}
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
                    team_averages = {}
                    
                    # Verificar time da casa
                    if self.normalize_name(home_team) in self.elite_teams_normalized:
                        logger.debug(f"🔍 Verificando {home_team} (ID: {home_id}, Liga: {league_id}, Season: {season})")
                        avg = self.api_client.get_team_goals_average(home_id, league_id, season)
                        api_requests_for_stats += 1
                        logger.info(f"📊 {home_team} média: {avg} (threshold: {Config.ELITE_GOALS_THRESHOLD})")
                        
                        if avg is not None and avg >= Config.ELITE_GOALS_THRESHOLD:
                            qualifying_teams.append(f"🏠 {home_team}: {avg:.2f} gols/jogo")
                            team_averages['home'] = avg
                            logger.info(f"✅ {home_team} QUALIFICADO!")
                        else:
                            logger.info(f"❌ {home_team} não qualificado (avg={avg})")
                    
                    # Verificar time visitante
                    if self.normalize_name(away_team) in self.elite_teams_normalized:
                        logger.debug(f"🔍 Verificando {away_team} (ID: {away_id}, Liga: {league_id}, Season: {season})")
                        avg = self.api_client.get_team_goals_average(away_id, league_id, season)
                        api_requests_for_stats += 1
                        logger.info(f"📊 {away_team} média: {avg} (threshold: {Config.ELITE_GOALS_THRESHOLD})")
                        
                        if avg is not None and avg >= Config.ELITE_GOALS_THRESHOLD:
                            qualifying_teams.append(f"✈️ {away_team}: {avg:.2f} gols/jogo")
                            team_averages['away'] = avg
                            logger.info(f"✅ {away_team} QUALIFICADO!")
                        else:
                            logger.info(f"❌ {away_team} não qualificado (avg={avg})")
                    
                    if qualifying_teams:
                        try:
                            dt = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                            formatted_datetime = dt.strftime("%d/%m/%Y às %H:%M UTC")
                            match_date_iso = dt.isoformat()
                        except:
                            formatted_datetime = match['fixture']['date']
                            match_date_iso = match['fixture']['date']
                        
                        message = f"""🌟 <b>JOGO DE ELITE DETECTADO!</b> 🌟

🏆 <b>Liga:</b> {league_name}
⚽ <b>Partida:</b> {home_team} vs {away_team}
📅 <b>Data/Hora:</b> {formatted_datetime}

🔥 <b>Times com média ≥ {Config.ELITE_GOALS_THRESHOLD} gols:</b>
""" + "\n".join([f"   • {team}" for team in qualifying_teams]) + f"""

💡 <b>Análise:</b> Time(s) de elite com alta média ofensiva detectado(s)
🎯 <b>Recomendação:</b> Over 2.5 gols, BTTS

📊 <b>Critério:</b> Times da lista elite com ≥ {Config.ELITE_GOALS_THRESHOLD} gols/jogo na temporada {season}
📅 <b>Gerado em:</b> {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC"""
                        
                        success = await self.telegram_client.send_message(Config.CHAT_ID_ELITE, message)
                        if success:
                            self.notified_fixtures.add(fixture_id)
                            notifications_sent += 1
                            logger.info(f"✅ Elite: {home_team} vs {away_team}")
                            
                            # ✅ ENVIAR PARA SUPABASE
                            if self.botscore:
                                try:
                                    # Calcular confiança baseada nas médias
                                    avg_goals = sum(team_averages.values()) / len(team_averages) if team_averages else Config.ELITE_GOALS_THRESHOLD
                                    confidence = min(95, int(60 + (avg_goals - Config.ELITE_GOALS_THRESHOLD) * 10))
                                    
                                    # Montar análise detalhada
                                    analysis_parts = [
                                        f"Time(s) de elite com alta média ofensiva detectado(s).",
                                        *qualifying_teams,
                                        f"Critério: Times com ≥ {Config.ELITE_GOALS_THRESHOLD} gols/jogo na temporada {season}"
                                    ]
                                    
                                    opportunity = {
                                        "bot_name": "elite",
                                        "match_info": f"{home_team} vs {away_team}",
                                        "league": league_name,
                                        "market": "Over 2.5 gols, BTTS",
                                        "odd": 1.80,
                                        "confidence": confidence,
                                        "status": "pre-match",
                                        "match_date": match_date_iso,
                                        "analysis": " ".join(analysis_parts)
                                    }
                                    
                                    supabase_ok = self.botscore.send_opportunity(opportunity)
                                    if supabase_ok:
                                        logger.info(f"✅ Oportunidade ELITE enviada ao Supabase: {home_team} vs {away_team}")
                                    else:
                                        logger.error(f"❌ Falha ao enviar ELITE ao Supabase: {home_team} vs {away_team}")
                                except Exception as e:
                                    logger.error(f"❌ Erro ao enviar ELITE ao Supabase: {e}")
                
                except Exception as e:
                    logger.error(f"❌ Erro ao processar partida elite: {e}", exc_info=True)
                    continue
            
            # Resumo com estatísticas CORRIGIDAS
            try:
                api_stats = self.api_client.get_daily_usage_stats()
                api_info = f"{api_stats['bot_used']}/{api_stats['bot_limit']} ({api_stats['bot_percentage']}%)"
                remaining_info = f"⚠️ Restante: {api_stats['bot_remaining']} requests"
            except Exception as e:
                logger.warning(f"Erro ao obter stats da API: {e}")
                api_info = "N/A"
                remaining_info = ""
            
            summary = f"""ℹ️ <b>Monitoramento Elite Concluído</b>

📊 Partidas analisadas: {len(all_matches)}
🌟 Times elite encontrados: {len(elite_found)}
🚨 Alertas enviados: {notifications_sent}

🔧 <b>API Usage:</b> {api_info}
📈 Requests para stats: {api_requests_for_stats}
{remaining_info}

⏰ Próxima execução: conforme agendamento
📅 {date_str}"""
            
            await self.telegram_client.send_message(Config.CHAT_ID_ELITE, summary)
            
        except Exception as e:
            logger.error(f"❌ Erro crítico no módulo Elite: {e}", exc_info=True)
            await self.telegram_client.send_admin_message(f"Erro crítico no módulo Elite: {e}")
        
        logger.info("🌟 Módulo Elite concluído")

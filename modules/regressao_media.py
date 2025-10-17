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
        # Normalizar chaves para int para evitar problemas de tipo
        self.allowed_leagues = {int(k): v for k, v in REGRESSAO_LEAGUES.items()}
        self.notified_matches = set()
        
        logger.info(f"📈 Módulo Regressão inicializado com {len(self.allowed_leagues)} ligas")
        logger.info(f"🔧 Tipos de chaves: {set(type(k) for k in self.allowed_leagues.keys())}")
    
    def is_under_15_result(self, match):
        """Detecta Under 1.5 gols"""
        try:
            goals = match.get('goals', {})
            home = goals.get('home', 0) if goals.get('home') is not None else 0
            away = goals.get('away', 0) if goals.get('away') is not None else 0
            return (home + away) < 2
        except Exception as e:
            logger.error(f"Erro ao verificar Under 1.5: {e}")
            return False
    
    def is_exact_0x0_result(self, match):
        """Detecta especificamente 0x0"""
        try:
            goals = match.get('goals', {})
            home = goals.get('home', 0) if goals.get('home') is not None else 0
            away = goals.get('away', 0) if goals.get('away') is not None else 0
            return home == 0 and away == 0
        except Exception as e:
            logger.error(f"Erro ao verificar 0x0: {e}")
            return False
    
    async def check_team_under_15(self, team_id, team_name):
        """Verifica se team vem de Under 1.5/0x0 na rodada anterior"""
        try:
            recent_matches = self.api_client.get_team_recent_matches(team_id, 1)
            if not recent_matches:
                logger.debug(f"🔍 {team_name}: Nenhuma partida recente encontrada")
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
                
                logger.debug(f"🔍 {team_name}: Última partida {score} vs {opponent} ({days_ago}d atrás)")
                
                if days_ago <= Config.MAX_LAST_MATCH_AGE_DAYS:
                    logger.debug(f"✅ {team_name}: Qualifica para regressão (Under 1.5, {days_ago}d)")
                    return True, {
                        'opponent': opponent,
                        'score': score,
                        'date': match_date.strftime('%d/%m'),
                        'is_0x0': is_0x0,
                        'days_ago': days_ago,
                        'league_name': last_match.get('league', {}).get('name', 'N/A')
                    }
                else:
                    logger.debug(f"❌ {team_name}: Partida muito antiga ({days_ago}d > {Config.MAX_LAST_MATCH_AGE_DAYS}d)")
            else:
                logger.debug(f"❌ {team_name}: Última partida não foi Under 1.5")
            
            return False, None
            
        except Exception as e:
            logger.error(f"❌ Erro verificando {team_name}: {e}")
            return False, None
    
    async def execute(self):
        """Executa o monitoramento de regressão à média"""
        if not Config.REGRESSAO_ENABLED:
            logger.info("📈 Módulo Regressão desabilitado na configuração")
            return
        
        logger.info("📈 Executando monitoramento de regressão à média...")
        
        try:
            # Verificar horário ativo COM DEBUG DETALHADO
            lisbon_tz = pytz.timezone("Europe/Lisbon")
            now_lisbon = datetime.now(lisbon_tz)
            current_hour = now_lisbon.hour
            
            logger.info(f"🕐 Hora atual Lisboa: {now_lisbon.strftime('%H:%M')} (hora {current_hour})")
            logger.info(f"🕐 Horário ativo: {Config.REGRESSAO_ACTIVE_HOURS_START}h às {Config.REGRESSAO_ACTIVE_HOURS_END}h")
            
            if not (Config.REGRESSAO_ACTIVE_HOURS_START <= current_hour <= Config.REGRESSAO_ACTIVE_HOURS_END):
                logger.info(f"⏰ MÓDULO INATIVO neste horário ({current_hour}h)")
                # Mensagem de diagnóstico temporária
                message = f"⏰ Regressão INATIVO às {current_hour}h Lisboa (ativo: {Config.REGRESSAO_ACTIVE_HOURS_START}-{Config.REGRESSAO_ACTIVE_HOURS_END}h)"
                await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, message)
                return
            
            logger.info("✅ Módulo Regressão ATIVO - prosseguindo...")
            
            # Usar estratégia similar ao Elite: UTC + múltiplos status
            date_str_utc = datetime.utcnow().strftime("%Y-%m-%d")
            today_str_lisbon = now_lisbon.strftime("%Y-%m-%d")
            current_date = now_lisbon.date()
            
            logger.info(f"📅 Buscando jogos para {today_str_lisbon} (Lisboa) / {date_str_utc} (UTC)")
            
            all_matches = []
            leagues_checked = 0
            
            for league_id, league_info in self.allowed_leagues.items():
                logger.info(f"🔍 Liga: {league_info['name']} (ID: {league_id})")
                
                # Buscar com múltiplos status como no Elite
                matches_ns = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="NS") or []
                matches_tbd = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="TBD") or []
                matches = matches_ns + matches_tbd
                
                if matches:
                    all_matches.extend(matches)
                    logger.info(f"📊 {league_info['name']}: NS={len(matches_ns)}, TBD={len(matches_tbd)}, Total={len(matches)}")
                    # Debug: mostrar primeiros jogos
                    for i, match in enumerate(matches[:2]):
                        home = match['teams']['home']['name']
                        away = match['teams']['away']['name']
                        match_time = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                        logger.info(f"   {i+1}. {home} vs {away} às {match_time.astimezone(lisbon_tz).strftime('%H:%M')}")
                else:
                    logger.info(f"📊 {league_info['name']}: 0 jogos encontrados")
                
                leagues_checked += 1
            
            logger.info(f"📊 RESUMO BUSCA: {leagues_checked} ligas, {len(all_matches)} jogos totais")
            
            if not all_matches:
                logger.warning("❌ NENHUM JOGO ENCONTRADO")
                message = f"⚠️ Regressão: 0 jogos encontrados para {today_str_lisbon} nas {len(self.allowed_leagues)} ligas"
                await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, message)
                return
            
            alerts_sent = 0
            games_analyzed = 0
            
            for match in all_matches:
                try:
                    # Verificar status do jogo
                    status = match.get('fixture', {}).get('status', {}).get('short')
                    if status not in ("NS", "TBD"):
                        logger.debug(f"Jogo ignorado - status: {status}")
                        continue
                    
                    fixture_id = match['fixture']['id']
                    home_team = match['teams']['home']['name']
                    away_team = match['teams']['away']['name']
                    home_id = match['teams']['home']['id']
                    away_id = match['teams']['away']['id']
                    league_id = int(match['league']['id'])  # Garantir int
                    
                    league_info = self.allowed_leagues.get(league_id)
                    if not league_info:
                        logger.debug(f"Liga {league_id} não permitida")
                        continue
                    
                    # Verificar se o jogo é realmente hoje em Lisboa
                    match_datetime = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                    match_date_lisbon = match_datetime.astimezone(lisbon_tz).date()
                    
                    if match_date_lisbon != current_date:
                        logger.debug(f"Jogo {home_team} vs {away_team} não é hoje em Lisboa")
                        continue
                    
                    games_analyzed += 1
                    logger.debug(f"🔍 Analisando: {home_team} vs {away_team}")
                    
                    # Verificar histórico dos times
                    home_under, home_info = await self.check_team_under_15(home_id, home_team)
                    away_under, away_info = await self.check_team_under_15(away_id, away_team)
                    
                    logger.debug(f"   {home_team} under 1.5? {home_under}")
                    logger.debug(f"   {away_team} under 1.5? {away_under}")
                    
                    if home_under or away_under:
                        notification_key = f"regressao_{today_str_lisbon}_{fixture_id}"
                        
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
📈 <b>Over 1.5 histórico da liga:</b> {league_info.get('over_15_percentage', 'N/A')}%
📉 <b>0x0 histórico da liga:</b> {league_info.get('0x0_ft_percentage', 'N/A')}%

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
                        else:
                            logger.debug(f"🔄 {home_team} vs {away_team} já notificado hoje")
                    else:
                        logger.debug(f"❌ {home_team} vs {away_team} não atende critérios")
                
                except Exception as e:
                    logger.error(f"❌ Erro processando jogo regressão: {e}")
                    continue
            
            # Resumo final SEMPRE enviado
            interval_minutes = getattr(Config, 'REGRESSAO_INTERVAL_MINUTES', 30)  # Fallback para 30 min
            summary = f"""📈 <b>Monitoramento Regressão Concluído</b>

📊 Jogos analisados: {games_analyzed}
🔍 Ligas verificadas: {leagues_checked}
🚨 Alertas enviados: {alerts_sent}
🕐 Horário: {now_lisbon.strftime('%H:%M')} Lisboa
⏰ Próxima verificação: {interval_minutes} min

🔧 Configuração:
• Idade máxima último jogo: {Config.MAX_LAST_MATCH_AGE_DAYS} dias
• Horário ativo: {Config.REGRESSAO_ACTIVE_HOURS_START}-{Config.REGRESSAO_ACTIVE_HOURS_END}h
📅 {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC"""
            
            await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, summary)
        
        except Exception as e:
            logger.error(f"❌ Erro no módulo regressão: {e}")
            await self.telegram_client.send_admin_message(f"Erro módulo regressão: {e}")
        
        logger.info("📈 Módulo Regressão concluído")

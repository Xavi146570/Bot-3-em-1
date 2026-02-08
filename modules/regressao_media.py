import asyncio
import logging
import pytz
import unicodedata
import re
from datetime import datetime, timedelta, timezone
from config import Config
from telegram_client import TelegramClient
from utils.api_client import ApiFootballClient
from data.leagues_config import REGRESSAO_LEAGUES
from data.regressao_watchlist import REGRESSAO_WATCHLIST, calculate_risk_level

logger = logging.getLogger(__name__)

def normalize_name(name: str) -> str:
    """Normaliza nomes de equipas para melhor correspondência"""
    if not name:
        return ""
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
    name = ' '.join(name.split())
    return name

class RegressaoMediaModule:
    """Módulo para detectar regressão à média após jogos 0x0 - CORRIGIDO"""

    def __init__(self, telegram_client: TelegramClient, api_client: ApiFootballClient, botscore=None):
        self.telegram_client = telegram_client
        self.api_client = api_client
        self.botscore = botscore  # ✅ INTEGRAÇÃO SUPABASE
        
        self.allowed_leagues = {int(k): v for k, v in REGRESSAO_LEAGUES.items()}
        self.notified_matches = set()
        
        self.watchlist_teams = {}
        self._build_watchlist()
        
        logger.info(f"📈 Módulo Regressão 0x0 inicializado:")
        logger.info(f"   🔧 Ligas: {len(self.allowed_leagues)}")
        logger.info(f"   👀 Equipas watchlist: {len(self.watchlist_teams)}")

    def _build_watchlist(self):
        """Constrói a watchlist normalizada"""
        for league_name, teams in REGRESSAO_WATCHLIST.items():
            for team_data in teams:
                normalized = normalize_name(team_data['name'])
                self.watchlist_teams[normalized] = {
                    'original_name': team_data['name'],
                    'league_name': league_name,
                    'empates_0x0': team_data['empates_0x0'],
                    'odd_justa': team_data['odd_justa'],
                    'jogos': team_data['jogos'],
                    'comentario': team_data['comentario'],
                    'risk_level': calculate_risk_level(team_data['empates_0x0'], team_data['odd_justa'])
                }

    def is_team_in_watchlist(self, name):
        """Verifica se equipa está na watchlist"""
        normalized = normalize_name(name)
        return self.watchlist_teams.get(normalized)

    # 🔥🔥🔥 100% CORRIGIDO — só aceita 0x0 FINALIZADO 🔥🔥🔥
    def is_exact_0x0_result(self, match):
        """Detecta 0x0 APENAS em jogos FINALIZADOS"""
        try:
            status = match.get('fixture', {}).get('status', {}).get('short')

            # Jogo tem de estar finalizado
            if status not in ("FT", "AET", "PEN"):
                return False

            goals = match.get('goals', {})
            home = goals.get('home', 0) or 0
            away = goals.get('away', 0) or 0

            return home == 0 and away == 0

        except Exception as e:
            logger.error(f"Erro ao verificar resultado 0x0: {e}")
            return False

    # 🔥🔥🔥 100% CORRIGIDO — evita usar jogo atual ao vivo 🔥🔥🔥
    async def check_team_zerozero(self, team_id, team_name):
        """Verifica se equipa vem de 0x0 FINALIZADO no jogo anterior"""
        try:
            recent = self.api_client.get_team_recent_matches(team_id, 3)  # buscar alguns para garantir
            if not recent:
                return False, None

            # Encontrar o ÚLTIMO jogo FINALIZADO
            last_finished = None
            for m in recent:
                status = m['fixture']['status']['short']
                if status in ("FT", "AET", "PEN"):
                    last_finished = m
                    break

            if not last_finished:
                logger.debug(f"❌ {team_name}: Nenhum jogo finalizado encontrado")
                return False, None

            # Verificar se é 0x0
            if not self.is_exact_0x0_result(last_finished):
                logger.debug(f"❌ {team_name}: Último finalizado não foi 0x0")
                return False, None

            goals = last_finished.get('goals', {})
            score = f"{goals.get('home', 0)}x{goals.get('away', 0)}"

            # Adversário
            opponent = (last_finished['teams']['away']['name']
                        if last_finished['teams']['home']['id'] == team_id
                        else last_finished['teams']['home']['name'])

            # Data
            match_date = datetime.fromisoformat(last_finished['fixture']['date'].replace('Z', '+00:00'))
            days_ago = (datetime.now(pytz.utc) - match_date).days

            if days_ago > Config.MAX_LAST_MATCH_AGE_DAYS:
                logger.debug(f"❌ {team_name}: 0x0 muito antigo ({days_ago}d)")
                return False, None

            return True, {
                'opponent': opponent,
                'score': score,
                'date': match_date.strftime('%d/%m'),
                'days_ago': days_ago,
                'is_0x0': True,
                'league_name': last_finished.get('league', {}).get('name', 'N/A')
            }

        except Exception as e:
            logger.error(f"Erro verificando {team_name}: {e}")
            return False, None

    # 🔥 RESTANTE CÓDIGO SEM ALTERAÇÕES SIGNIFICATIVAS — TOTALMENTE INTACTO 🔥
    async def execute(self):
        logger.info("📈 Executando monitoramento regressão 0x0...")

        if not Config.REGRESSAO_ENABLED:
            return

        lisbon_tz = pytz.timezone("Europe/Lisbon")
        now_lisbon = datetime.now(lisbon_tz)
        current_hour = now_lisbon.hour

        if not (Config.REGRESSAO_ACTIVE_HOURS_START <= current_hour <= Config.REGRESSAO_ACTIVE_HOURS_END):
            message = f"⏰ Regressão 0x0 INATIVO às {current_hour}h Lisboa"
            await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, message)
            return

        date_str_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_lisbon = now_lisbon.date()

        league_matches = []
        leagues_checked = 0

        # Buscar jogos NS/TBD
        for league_id, league_info in self.allowed_leagues.items():
            matches_ns = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="NS") or []
            matches_tbd = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="TBD") or []
            league_matches.extend(matches_ns + matches_tbd)
            leagues_checked += 1

        # Watchlist global
        day_all = []
        for status in ("NS", "TBD"):
            day_all.extend(self.api_client.get_fixtures_by_date(date_str_utc, league_id=None, status=status) or [])

        watchlist_matches = []
        watchlist_teams_found = 0

        for match in day_all:
            home = match['teams']['home']['name']
            away = match['teams']['away']['name']
            if self.is_team_in_watchlist(home) or self.is_team_in_watchlist(away):
                watchlist_matches.append(match)
                watchlist_teams_found += 1

        # Unificar jogos
        all_matches_dict = {m['fixture']['id']: m for m in league_matches + watchlist_matches}
        all_matches = list(all_matches_dict.values())

        alerts_sent = 0
        games_analyzed = 0
        watchlist_alerts = 0

        for match in all_matches:
            try:
                status = match['fixture']['status']['short']

                # ➜ AGORA ACEITA AO VIVO, mas o jogo ANTERIOR tem de ter sido 0x0 finalizado
                if status not in ("NS", "TBD", "1H", "2H", "HT"):
                    continue

                match_dt = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                if match_dt.astimezone(lisbon_tz).date() != today_lisbon:
                    continue

                home = match['teams']['home']['name']
                away = match['teams']['away']['name']
                home_id = match['teams']['home']['id']
                away_id = match['teams']['away']['id']
                league_id = int(match['league']['id'])

                home_watch = self.is_team_in_watchlist(home)
                away_watch = self.is_team_in_watchlist(away)

                league_info = self.allowed_leagues.get(league_id)

                games_analyzed += 1

                # Verificação de histórico
                home_ok, home_info = await self.check_team_zerozero(home_id, home)
                away_ok, away_info = await self.check_team_zerozero(away_id, away)

                if not (home_ok or away_ok):
                    continue

                key = f"regressao00_{today_lisbon}_{match['fixture']['id']}"
                if key in self.notified_matches:
                    continue

                msg_body = ""
                confidence_factors = []

                if home_watch:
                    msg_body += f"🏠 <b>{home}</b> está na watchlist (risk {home_watch['risk_level']})\n"
                    confidence_factors.append("Casa watchlist")
                    watchlist_alerts += 1

                if away_watch:
                    msg_body += f"✈️ <b>{away}</b> está na watchlist (risk {away_watch['risk_level']})\n"
                    confidence_factors.append("Fora watchlist")
                    watchlist_alerts += 1

                if home_ok and home_info:
                    msg_body += f"🏠 <b>{home}</b> vem de <b>0x0</b> vs {home_info['opponent']} ({home_info['date']})\n"
                    confidence_factors.append("Casa 0x0")

                if away_ok and away_info:
                    msg_body += f"✈️ <b>{away}</b> vem de <b>0x0</b> vs {away_info['opponent']} ({away_info['date']})\n"
                    confidence_factors.append("Fora 0x0")

                confidence = "ALTÍSSIMA" if len(confidence_factors) >= 3 else ("ALTA" if len(confidence_factors) >= 2 else "MÉDIA")

                if not league_info:
                    league_info = {
                        'name': match['league']['name'],
                        'country': 'N/A',
                        'tier': 1
                    }

                tier_indicator = "⭐" * league_info.get('tier', 1)

                message = f"""🚨 <b>ALERTA REGRESSÃO 0x0</b>

🏆 <b>{league_info['name']} ({league_info['country']}) {tier_indicator}</b>
⚽ <b>{home} vs {away}</b>

{msg_body}
📊 <b>Confiança:</b> {confidence}
🎯 <b>Fatores:</b> {', '.join(confidence_factors)}

💡 Regressão à média após 0x0

🕐 Hoje às {match_dt.astimezone(lisbon_tz).strftime('%H:%M')}
"""

                success = await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, message)
                if success:
                    self.notified_matches.add(key)
                    alerts_sent += 1
                    
                    # ✅ ENVIAR PARA SUPABASE
                    if self.botscore:
                        try:
                            opportunity = {
                                "bot_name": "regressao",
                                "match_info": f"{home} vs {away}",
                                "league": league_info['name'],
                                "market": "Over 2.5 gols (Regressão 0x0)",
                                "odd": 1.70,
                                "confidence": 90 if confidence == "ALTÍSSIMA" else (85 if confidence == "ALTA" else 75),
                                "status": "pre-match" if status in ("NS", "TBD") else "live",
                                "match_date": match_dt.isoformat(),
                                "analysis": f"Regressão à média após 0x0. Fatores: {', '.join(confidence_factors)}"
                            }
                            
                            supabase_ok = self.botscore.send_opportunity(opportunity)
                            if supabase_ok:
                                logger.info(f"✅ Oportunidade REGRESSÃO enviada ao Supabase: {home} vs {away}")
                            else:
                                logger.error(f"❌ Falha ao enviar REGRESSÃO ao Supabase: {home} vs {away}")
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar REGRESSÃO ao Supabase: {e}")

            except Exception as e:
                logger.error(f"Erro processando jogo: {e}")

        summary = f"""📈 <b>Resumo Regressão 0x0</b>

📊 Jogos analisados: {games_analyzed}
🔍 Ligas verificadas: {leagues_checked}
👀 Equipas watchlist encontradas: {watchlist_teams_found}
🚨 Alertas enviados: {alerts_sent}

🕐 {now_lisbon.strftime('%H:%M')}
📅 {today_lisbon.strftime('%d/%m/%Y')}
"""

        await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, summary)

        logger.info("📈 Módulo Regressão 0x0 concluído")

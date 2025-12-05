import asyncio
import logging
import pytz
import unicodedata
import re
from datetime import datetime, timedelta
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
    """Módulo para detectar regressão após jogos 0x0"""
    
    def __init__(self, telegram_client: TelegramClient, api_client: ApiFootballClient):
        self.telegram_client = telegram_client
        self.api_client = api_client

        self.allowed_leagues = {int(k): v for k, v in REGRESSAO_LEAGUES.items()}
        self.notified_matches = set()

        self.watchlist_teams = {}
        self._build_watchlist()

        logger.info(f"Módulo Regressão 0x0 inicializado")

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
        normalized = normalize_name(name)
        return self.watchlist_teams.get(normalized)

    def is_exact_0x0_result(self, match):
        """Detecta especificamente 0x0"""
        try:
            goals = match.get('goals', {})
            h = goals.get('home', 0)
            a = goals.get('away', 0)
            return h == 0 and a == 0
        except:
            return False

    async def check_team_zerozero(self, team_id, team_name):
        """Verifica se equipa vem de 0x0 na última partida"""
        try:
            recent = self.api_client.get_team_recent_matches(team_id, 1)
            if not recent:
                return False, None

            last = recent[0]
            is_0x0 = self.is_exact_0x0_result(last)
            if not is_0x0:
                return False, None

            goals = last.get('goals', {})
            score = f"{goals.get('home', 0)}x{goals.get('away', 0)}"

            opponent = (last['teams']['away']['name']
                        if last['teams']['home']['id'] == team_id
                        else last['teams']['home']['name'])

            date = datetime.fromisoformat(last['fixture']['date'].replace('Z', '+00:00'))
            diff = (datetime.now(pytz.utc) - date).days

            if diff <= Config.MAX_LAST_MATCH_AGE_DAYS:
                return True, {
                    'opponent': opponent,
                    'score': score,
                    'date': date.strftime('%d/%m'),
                    'days_ago': diff,
                    'is_0x0': True,
                    'league_name': last.get('league', {}).get('name', 'N/A')
                }

            return False, None

        except Exception as e:
            logger.error(f"Erro verificando último 0x0 de {team_name}: {e}")
            return False, None

    async def execute(self):
        logger.info("Execução módulo regressão 0x0")

        if not Config.REGRESSAO_ENABLED:
            return

        lis_tz = pytz.timezone("Europe/Lisbon")
        now = datetime.now(lis_tz)
        hour = now.hour

        if not (Config.REGRESSAO_ACTIVE_HOURS_START <= hour <= Config.REGRESSAO_ACTIVE_HOURS_END):
            await self.telegram_client.send_message(
                Config.CHAT_ID_REGRESSAO,
                f"⏰ Regressão 0x0 Inativo às {hour}h Lisboa"
            )
            return

        date_str_utc = datetime.utcnow().strftime("%Y-%m-%d")
        today_lisbon = now.date()

        league_matches = []
        leagues_checked = 0

        # Buscar jogos das ligas configuradas
        for league_id, info in self.allowed_leagues.items():
            ns = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="NS") or []
            tbd = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="TBD") or []
            # Adicionar status aos jogos simulados
            for match in ns:
                match['fixture']['status'] = {'short': 'NS'}
            for match in tbd:
                match['fixture']['status'] = {'short': 'TBD'}

            league_matches += ns + tbd
            leagues_checked += 1

        # Buscar todos os jogos do dia e filtrar watchlist
        day_all = []
        for st in ("NS", "TBD"):
            d = self.api_client.get_fixtures_by_date(date_str_utc, league_id=None, status=st) or []
            # Adicionar status aos jogos simulados
            for match in d:
                match['fixture']['status'] = {'short': st}
            day_all += d

        watchlist_matches = []
        for match in day_all:
            home = match['teams']['home']['name']
            away = match['teams']['away']['name']

            if self.is_team_in_watchlist(home) or self.is_team_in_watchlist(away):
                watchlist_matches.append(match)

        # Remover duplicados
        all_matches = {m["fixture"]["id"]: m for m in league_matches + watchlist_matches}
        all_matches = list(all_matches.values())

        if not all_matches:
            await self.telegram_client.send_message(
                Config.CHAT_ID_REGRESSAO,
                f"⚠️ Regressão 0x0: Nenhum jogo encontrado hoje."
            )
            return

        alerts_sent = 0
        analyzed = 0
        watchlist_alerts = 0

        for match in all_matches:
            try:
                status = match['fixture']['status']['short']
                if status not in ("NS", "TBD"):
                    continue

                match_dt = datetime.fromisoformat(match['fixture']['date'].replace("Z", "+00:00"))
                if match_dt.astimezone(lis_tz).date() != today_lisbon:
                    continue

                home = match['teams']['home']['name']
                away = match['teams']['away']['name']
                home_id = match['teams']['home']['id']
                away_id = match['teams']['away']['id']

                home_watch = self.is_team_in_watchlist(home)
                away_watch = self.is_team_in_watchlist(away)

                league_id = match['league']['id']
                league_info = self.allowed_leagues.get(league_id)

                # A contagem de jogos analisados deve ser feita para todos os jogos do dia
                analyzed += 1
                
                # O filtro para análise deve ser mantido
                if not (league_info or home_watch or away_watch):
                    continue

                home_ok, home_info = await self.check_team_zerozero(home_id, home)
                away_ok, away_info = await self.check_team_zerozero(away_id, away)

                if not (home_ok or away_ok):
                    continue
                
                # A contagem de alertas da watchlist é feita aqui, uma vez por jogo
                if home_watch or away_watch:
                    watchlist_alerts += 1

                key = f"regressao00_{today_lisbon}_{match['fixture']['id']}"
                if key in self.notified_matches:
                    continue

                msg_body = ""
                confidence_factors = []

                if home_watch:
                    msg_body += f"🏠 <b>{home}</b> está na watchlist (risk {home_watch['risk_level']})\n"

                if away_watch:
                    msg_body += f"✈️ <b>{away}</b> está na watchlist (risk {away_watch['risk_level']})\n"

                if home_ok:
                    msg_body += f"🏠 <b>{home}</b> vem de <b>0x0</b> vs {home_info['opponent']} ({home_info['date']})\n"
                    confidence_factors.append("Casa vem de 0x0")

                if away_ok:
                    msg_body += f"✈️ <b>{away}</b> vem de <b>0x0</b> vs {away_info['opponent']} ({away_info['date']})\n"
                    confidence_factors.append("Fora vem de 0x0")

                if len(confidence_factors) >= 2:
                    confidence = "ALTA"
                    conf_score = 90
                else:
                    confidence = "MÉDIA"
                    conf_score = 70

                if not league_info:
                    league_info = {
                        'name': match['league']['name'],
                        'country': 'N/A',
                        'tier': 1
                    }

                tier_ind = "⭐" * league_info['tier']

                message = f"""
🚨 <b>ALERTA REGRESSÃO 0x0</b>

🏆 <b>{league_info['name']} ({league_info['country']}) {tier_ind}</b>
⚽ <b>{home} vs {away}</b>

{msg_body}

📊 Confiança: <b>{confidence}</b>
🎯 Fatores: {", ".join(confidence_factors)}

💡 Teoria: regressão após 0x0 (tendência de gol hoje)

🕐 Hoje às {match_dt.astimezone(lis_tz).strftime('%H:%M')}
📅 {today_lisbon.strftime('%d/%m/%Y')}
"""

                await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, message)

                self.notified_matches.add(key)
                alerts_sent += 1

            except Exception as e:
                logger.error(f"Erro processando jogo: {e}")

        summary = f"""
📈 <b>Resumo Regressão 0x0</b>

📊 Jogos analisados: {analyzed}
👀 Watchlist alertas: {watchlist_alerts}
🚨 Alertas enviados: {alerts_sent}
🕐 Hora: {now.strftime('%H:%M')}
"""
        await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, summary)

        logger.info("Execução regressão 0x0 concluída")

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
    """Módulo para detectar regressão à média após jogos 0x0 - OTIMIZADO"""
    
    def __init__(self, telegram_client: TelegramClient, api_client: ApiFootballClient):
        self.telegram_client = telegram_client
        self.api_client = api_client
        
        # Normalizar ligas permitidas
        self.allowed_leagues = {int(k): v for k, v in REGRESSAO_LEAGUES.items()}
        self.notified_matches = set()
        
        # Construir watchlist normalizada
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

    def is_exact_0x0_result(self, match):
        """Detecta especificamente resultado 0x0"""
        try:
            goals = match.get('goals', {})
            home = goals.get('home', 0) if goals.get('home') is not None else 0
            away = goals.get('away', 0) if goals.get('away') is not None else 0
            return home == 0 and away == 0
        except Exception as e:
            logger.error(f"Erro ao verificar 0x0: {e}")
            return False

    async def check_team_zerozero(self, team_id, team_name):
        """Verifica se equipa vem de 0x0 na última partida"""
        try:
            recent = self.api_client.get_team_recent_matches(team_id, 1)
            if not recent:
                logger.debug(f"🔍 {team_name}: Sem histórico recente")
                return False, None

            last_match = recent[0]
            
            # Verificar se é 0x0
            is_0x0 = self.is_exact_0x0_result(last_match)
            if not is_0x0:
                logger.debug(f"❌ {team_name}: Última partida não foi 0x0")
                return False, None

            goals = last_match.get('goals', {})
            score = f"{goals.get('home', 0)}x{goals.get('away', 0)}"

            # Identificar adversário
            opponent = (last_match['teams']['away']['name']
                       if last_match['teams']['home']['id'] == team_id
                       else last_match['teams']['home']['name'])

            # Calcular dias desde o jogo
            match_date = datetime.fromisoformat(last_match['fixture']['date'].replace('Z', '+00:00'))
            days_ago = (datetime.now(pytz.utc) - match_date).days

            logger.debug(f"🔍 {team_name}: Último jogo {score} vs {opponent} ({days_ago}d atrás)")

            # Verificar idade máxima
            if days_ago <= Config.MAX_LAST_MATCH_AGE_DAYS:
                logger.debug(f"✅ {team_name}: Qualifica (0x0 há {days_ago}d)")
                return True, {
                    'opponent': opponent,
                    'score': score,
                    'date': match_date.strftime('%d/%m'),
                    'days_ago': days_ago,
                    'is_0x0': True,
                    'league_name': last_match.get('league', {}).get('name', 'N/A')
                }
            else:
                logger.debug(f"❌ {team_name}: 0x0 muito antigo ({days_ago}d > {Config.MAX_LAST_MATCH_AGE_DAYS}d)")

            return False, None

        except Exception as e:
            logger.error(f"❌ Erro verificando {team_name}: {e}")
            return False, None

    async def execute(self):
        """Executa monitoramento de regressão após 0x0"""
        logger.info("📈 Executando monitoramento regressão 0x0...")

        if not Config.REGRESSAO_ENABLED:
            logger.info("📈 Módulo Regressão desabilitado")
            return

        # Verificar horário ativo
        lisbon_tz = pytz.timezone("Europe/Lisbon")
        now_lisbon = datetime.now(lisbon_tz)
        current_hour = now_lisbon.hour

        logger.info(f"🕐 Hora atual Lisboa: {now_lisbon.strftime('%H:%M')} (hora {current_hour})")
        logger.info(f"🕐 Horário ativo: {Config.REGRESSAO_ACTIVE_HOURS_START}h-{Config.REGRESSAO_ACTIVE_HOURS_END}h")

        if not (Config.REGRESSAO_ACTIVE_HOURS_START <= current_hour <= Config.REGRESSAO_ACTIVE_HOURS_END):
            logger.info(f"⏰ MÓDULO INATIVO neste horário ({current_hour}h)")
            message = f"⏰ Regressão 0x0 INATIVO às {current_hour}h Lisboa (ativo: {Config.REGRESSAO_ACTIVE_HOURS_START}-{Config.REGRESSAO_ACTIVE_HOURS_END}h)"
            await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, message)
            return

        logger.info("✅ Módulo Regressão ATIVO - prosseguindo...")

        # Datas
        date_str_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_lisbon = now_lisbon.date()

        logger.info(f"📅 Buscando jogos para {today_lisbon.strftime('%d/%m/%Y')} (UTC: {date_str_utc})")

        # Buscar jogos das ligas configuradas
        league_matches = []
        leagues_checked = 0

        for league_id, league_info in self.allowed_leagues.items():
            logger.info(f"🔍 Liga: {league_info['name']} (ID: {league_id})")
            
            # Buscar sem adicionar status fake
            matches_ns = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="NS") or []
            matches_tbd = self.api_client.get_fixtures_by_date(date_str_utc, league_id=league_id, status="TBD") or []
            matches = matches_ns + matches_tbd

            if matches:
                league_matches.extend(matches)
                logger.info(f"📊 {league_info['name']}: NS={len(matches_ns)}, TBD={len(matches_tbd)}, Total={len(matches)}")
            else:
                logger.info(f"📊 {league_info['name']}: 0 jogos")

            leagues_checked += 1

        # Buscar jogos globais para watchlist
        logger.info("🔍 Buscando jogos globais para watchlist...")
        day_all = []
        for status in ("NS", "TBD"):
            day_matches = self.api_client.get_fixtures_by_date(date_str_utc, league_id=None, status=status) or []
            day_all.extend(day_matches)

        # Filtrar watchlist
        watchlist_matches = []
        watchlist_teams_found = 0

        for match in day_all:
            home = match['teams']['home']['name']
            away = match['teams']['away']['name']

            home_in = self.is_team_in_watchlist(home)
            away_in = self.is_team_in_watchlist(away)

            if home_in or away_in:
                watchlist_matches.append(match)
                if home_in:
                    watchlist_teams_found += 1
                    logger.debug(f"👀 {home} encontrado na watchlist")
                if away_in:
                    watchlist_teams_found += 1
                    logger.debug(f"👀 {away} encontrado na watchlist")

        # Remover duplicados por fixture_id
        all_matches_dict = {}
        for match in league_matches + watchlist_matches:
            all_matches_dict[match['fixture']['id']] = match

        all_matches = list(all_matches_dict.values())

        logger.info(f"📊 RESUMO BUSCA:")
        logger.info(f"   📋 Ligas configuradas: {len(league_matches)} jogos")
        logger.info(f"   👀 Watchlist: {len(watchlist_matches)} jogos, {watchlist_teams_found} equipas")
        logger.info(f"   🎯 Total único: {len(all_matches)} jogos")

        if not all_matches:
            logger.warning("❌ NENHUM JOGO ENCONTRADO")
            message = f"⚠️ Regressão 0x0: Nenhum jogo encontrado para {today_lisbon.strftime('%d/%m/%Y')}"
            await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, message)
            return

        # Analisar jogos
        alerts_sent = 0
        games_analyzed = 0
        watchlist_alerts = 0

        for match in all_matches:
            try:
                # Verificar status (usar o real da API)
                status = match.get('fixture', {}).get('status', {}).get('short')
                if status not in ("NS", "TBD"):
                    logger.debug(f"Jogo ignorado - status: {status}")
                    continue

                # Verificar se é hoje em Lisboa
                match_dt = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
                match_date_lisbon = match_dt.astimezone(lisbon_tz).date()

                if match_date_lisbon != today_lisbon:
                    logger.debug(f"Jogo não é hoje em Lisboa")
                    continue

                # Dados do jogo
                home = match['teams']['home']['name']
                away = match['teams']['away']['name']
                home_id = match['teams']['home']['id']
                away_id = match['teams']['away']['id']
                league_id = int(match['league']['id'])

                # Verificar watchlist
                home_watch = self.is_team_in_watchlist(home)
                away_watch = self.is_team_in_watchlist(away)

                # Verificar se é liga permitida
                league_info = self.allowed_leagues.get(league_id)

                # IMPORTANTE: Contar ANTES do filtro
                games_analyzed += 1

                # Filtrar apenas para análise detalhada
                if not (league_info or home_watch or away_watch):
                    logger.debug(f"Jogo ignorado - não está em liga permitida nem tem watchlist")
                    continue

                logger.debug(f"🔍 Analisando: {home} vs {away}")

                # Verificar histórico 0x0
                home_ok, home_info = await self.check_team_zerozero(home_id, home)
                away_ok, away_info = await self.check_team_zerozero(away_id, away)

                logger.debug(f"   {home} vem de 0x0? {home_ok}")
                logger.debug(f"   {away} vem de 0x0? {away_ok}")

                if not (home_ok or away_ok):
                    logger.debug(f"❌ {home} vs {away} não atende critérios")
                    continue

                # Construir alerta
                key = f"regressao00_{today_lisbon}_{match['fixture']['id']}"
                if key in self.notified_matches:
                    logger.debug(f"🔄 {home} vs {away} já notificado hoje")
                    continue

                msg_body = ""
                confidence_factors = []

                # Informações da watchlist
                if home_watch:
                    msg_body += f"🏠 <b>{home}</b> está na watchlist (risk {home_watch['risk_level']})\n"
                    confidence_factors.append("Casa na watchlist")
                    watchlist_alerts += 1

                if away_watch:
                    msg_body += f"✈️ <b>{away}</b> está na watchlist (risk {away_watch['risk_level']})\n"
                    confidence_factors.append("Fora na watchlist")
                    watchlist_alerts += 1

                # Informações do 0x0
                if home_ok and home_info:
                    msg_body += f"🏠 <b>{home}</b> vem de <b>0x0</b> vs {home_info['opponent']} ({home_info['date']} - {home_info['days_ago']}d)\n"
                    confidence_factors.append("Casa vem de 0x0")

                if away_ok and away_info:
                    msg_body += f"✈️ <b>{away}</b> vem de <b>0x0</b> vs {away_info['opponent']} ({away_info['date']} - {away_info['days_ago']}d)\n"
                    confidence_factors.append("Fora vem de 0x0")

                # Calcular confiança
                if len(confidence_factors) >= 3:
                    confidence = "ALTÍSSIMA"
                elif len(confidence_factors) >= 2:
                    confidence = "ALTA"
                else:
                    confidence = "MÉDIA"

                # Informações da liga
                if not league_info:
                    league_info = {
                        'name': match['league']['name'],
                        'country': 'N/A',
                        'tier': 1
                    }

                tier_indicator = "⭐" * league_info.get('tier', 1)

                # Mensagem final
                message = f"""🚨 <b>ALERTA REGRESSÃO 0x0</b>

🏆 <b>{league_info['name']} ({league_info['country']}) {tier_indicator}</b>
⚽ <b>{home} vs {away}</b>

{msg_body}
📊 <b>Confiança:</b> {confidence}
🎯 <b>Fatores:</b> {', '.join(confidence_factors)}

💡 <b>Teoria:</b> Regressão à média após 0x0 (tendência de gols hoje)

🎯 <b>Sugestões:</b>
• 🟢 Over 0.5 Gols (Principal)
• 🟢 Over 1.5 Gols
• 🟢 BTTS (se ambos de 0x0)

🕐 <b>HOJE às {match_dt.astimezone(lisbon_tz).strftime('%H:%M')}</b>
📅 <b>{today_lisbon.strftime('%d/%m/%Y')}</b>"""

                success = await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, message)
                if success:
                    self.notified_matches.add(key)
                    alerts_sent += 1
                    logger.info(f"✅ Regressão 0x0: {home} vs {away}")

            except Exception as e:
                logger.error(f"❌ Erro processando jogo: {e}")
                continue

        # Resumo final
        try:
            api_stats = self.api_client.get_daily_usage_stats()
            api_info = f"{api_stats['bot_used']}/{api_stats['bot_limit']} ({api_stats['bot_percentage']}%)"
            remaining_info = f"⚠️ Restante: {api_stats['bot_remaining']} requests"
        except Exception as e:
            logger.warning(f"Erro ao obter stats da API: {e}")
            api_info = "N/A"
            remaining_info = ""

        summary = f"""📈 <b>Resumo Regressão 0x0</b>

📊 Jogos analisados: {games_analyzed}
🔍 Ligas verificadas: {leagues_checked}
👀 Equipas watchlist encontradas: {watchlist_teams_found}
🚨 Alertas enviados: {alerts_sent}
🕐 Horário: {now_lisbon.strftime('%H:%M')} Lisboa
📅 {today_lisbon.strftime('%d/%m/%Y')}

🔧 <b>API Usage:</b> {api_info}
{remaining_info}

🔧 Configuração: {len(self.allowed_leagues)} ligas + {len(self.watchlist_teams)} equipas watchlist"""

        await self.telegram_client.send_message(Config.CHAT_ID_REGRESSAO, summary)

        logger.info("📈 Módulo Regressão 0x0 concluído")

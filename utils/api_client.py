import httpx
import logging
from datetime import datetime, date
from config import Config

logger = logging.getLogger(__name__)

class ApiFootballClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "v3.football.api-sports.io"
        }
        
        # Controlo mensal de requisições
        self.monthly_count = 0
        self.limit_per_month = 2000  # Plano gratuito
        self.current_month = datetime.utcnow().month
        self.current_year = datetime.utcnow().year
        
        logger.info(f"🔧 ApiFootballClient inicializado - Limite mensal: {self.limit_per_month}")

    def _check_monthly_reset(self):
        """Verifica se mudou o mês e reseta contador"""
        now = datetime.utcnow()
        if now.month != self.current_month or now.year != self.current_year:
            old_count = self.monthly_count
            self.monthly_count = 0
            self.current_month = now.month
            self.current_year = now.year
            logger.info(f"🔄 Reset contador API: {old_count} → 0 (novo mês: {now.month}/{now.year})")
            return True
        return False

    def _can_make_request(self) -> bool:
        """Verifica se ainda pode fazer requisições"""
        self._check_monthly_reset()
        
        if self.monthly_count >= self.limit_per_month:
            logger.warning(f"🚨 Limite mensal atingido: {self.monthly_count}/{self.limit_per_month}")
            return False
        return True

    def _increment_counter(self):
        """Incrementa contador e loga progresso"""
        self.monthly_count += 1
        remaining = self.limit_per_month - self.monthly_count
        percentage = (self.monthly_count / self.limit_per_month) * 100
        
        # Log a cada 25 requests ou quando crítico
        if self.monthly_count % 25 == 0 or remaining < 50:
            logger.info(f"📊 API: {self.monthly_count}/{self.limit_per_month} ({percentage:.1f}% - {remaining} restantes)")
        
        # Alertas críticos
        if remaining == 100:
            logger.warning(f"⚠️ ATENÇÃO: Restam apenas {remaining} requisições este mês!")
        elif remaining == 25:
            logger.error(f"🚨 CRÍTICO: Restam apenas {remaining} requisições este mês!")

    def get_fixtures_by_date(self, date_str: str, league_id=None, status="NS"):
        """Busca jogos por data com controlo de quota"""
        if not self._can_make_request():
            logger.warning(f"🚫 get_fixtures_by_date bloqueado - limite mensal atingido")
            return []

        try:
            with httpx.Client(headers=self.headers, timeout=30.0) as client:
                params = {"date": date_str, "status": status}
                if league_id:
                    params["league"] = league_id

                url = f"{self.base_url}/fixtures"
                logger.debug(f"🌐 Request: fixtures {date_str}, league={league_id}, status={status}")
                
                response = client.get(url, params=params)
                self._increment_counter()
                
                if response.status_code == 200:
                    data = response.json()
                    fixtures = data.get('response', [])
                    logger.debug(f"📊 Fixtures: {len(fixtures)} encontrados")
                    return fixtures
                else:
                    logger.error(f"❌ API Error {response.status_code} para fixtures")
                    return []
                    
        except Exception as e:
            logger.error(f"❌ Erro em get_fixtures_by_date: {e}")
            return []

    def get_team_recent_matches(self, team_id: int, count: int = 1):
        """Busca jogos recentes com controlo de quota"""
        if not self._can_make_request():
            logger.warning(f"🚫 get_team_recent_matches bloqueado para team {team_id}")
            return []

        try:
            with httpx.Client(headers=self.headers, timeout=30.0) as client:
                params = {"team": team_id, "last": count}
                url = f"{self.base_url}/fixtures"
                
                response = client.get(url, params=params)
                self._increment_counter()
                
                if response.status_code == 200:
                    data = response.json()
                    matches = data.get('response', [])
                    logger.debug(f"📊 Recent matches: {len(matches)} para team {team_id}")
                    return matches
                else:
                    logger.error(f"❌ API Error {response.status_code} para team {team_id}")
                    return []
                    
        except Exception as e:
            logger.error(f"❌ Erro em get_team_recent_matches: {e}")
            return []

    def get_team_goals_average(self, team_id: int, league_id: int, season: int):
        """Busca média de gols com controlo de quota"""
        if not self._can_make_request():
            logger.warning(f"🚫 get_team_goals_average bloqueado para team {team_id}")
            return None

        try:
            with httpx.Client(headers=self.headers, timeout=30.0) as client:
                params = {"team": team_id, "league": league_id, "season": season}
                url = f"{self.base_url}/teams/statistics"
                
                response = client.get(url, params=params)
                self._increment_counter()
                
                if response.status_code == 200:
                    data = response.json()
                    stats = data.get('response', {})
                    
                    if stats and 'goals' in stats:
                        goals_for = stats['goals']['for']['total']['total'] or 0
                        games_played = stats['fixtures']['played']['total'] or 1
                        average = goals_for / games_played if games_played > 0 else 0.0
                        logger.debug(f"📊 Team {team_id} average: {average:.2f} gols/jogo")
                        return average
                    return None
                else:
                    logger.error(f"❌ API Error {response.status_code} para stats team {team_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Erro em get_team_goals_average: {e}")
            return None

    def get_monthly_usage_stats(self) -> dict:
        """Retorna estatísticas mensais de uso"""
        self._check_monthly_reset()
        remaining = self.limit_per_month - self.monthly_count
        percentage = (self.monthly_count / self.limit_per_month) * 100
        
        return {
            'used': self.monthly_count,
            'limit': self.limit_per_month,
            'remaining': remaining,
            'percentage_used': round(percentage, 1),
            'month': f"{self.current_month}/{self.current_year}"
        }

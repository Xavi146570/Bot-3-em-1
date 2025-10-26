import httpx
import logging
from datetime import datetime, date, timezone
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

class ApiFootballClient:
    def __init__(self, api_key: str, daily_limit: int = 2000):
        if not api_key:
            raise ValueError("API key é obrigatória")
            
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "v3.football.api-sports.io"
        }
        
        # Controlo diário de requisições
        self.daily_count = 0
        self.daily_limit = daily_limit
        self.current_date = datetime.now(timezone.utc).date()
        
        # Thresholds configuráveis
        self.warn_threshold = 0.75  # 75% para aviso
        self.block_threshold = 0.95  # 95% para bloqueio preventivo
        
        # Informações da conta (dos headers da API)
        self.account_remaining = None
        self.account_limit = None
        
        logger.info(f"🔧 ApiFootballClient inicializado - Limite diário: {self.daily_limit}")

    def _check_daily_reset(self):
        """Verifica se mudou o dia e reseta contador"""
        today = datetime.now(timezone.utc).date()
        if today != self.current_date:
            old_count = self.daily_count
            self.daily_count = 0
            self.current_date = today
            logger.info(f"🔄 Reset contador diário: {old_count} → 0 (novo dia: {today})")
            return True
        return False

    def _update_from_headers(self, response: httpx.Response):
        """Atualiza informações da conta a partir dos headers da API"""
        try:
            # API-Football pode retornar diferentes headers dependendo do plano
            remaining = response.headers.get("x-ratelimit-requests-remaining") or \
                       response.headers.get("X-RateLimit-Remaining")
            limit = response.headers.get("x-ratelimit-requests-limit") or \
                   response.headers.get("X-RateLimit-Limit")
            
            if remaining is not None:
                self.account_remaining = int(remaining)
            if limit is not None:
                self.account_limit = int(limit)
                
            if self.account_remaining is not None and self.account_limit is not None:
                logger.debug(f"🔧 Conta API: {self.account_remaining}/{self.account_limit} restantes")
                
        except Exception as e:
            logger.debug(f"Não foi possível ler headers da API: {e}")

    def _can_make_request(self) -> bool:
        """Verifica se pode fazer requisição (bot + conta)"""
        self._check_daily_reset()
        
        # Verificar limite do bot
        usage_pct = self.daily_count / self.daily_limit if self.daily_limit > 0 else 0
        if usage_pct >= self.block_threshold:
            logger.warning(f"🚫 Limite preventivo do bot atingido: {self.daily_count}/{self.daily_limit} ({usage_pct:.1%})")
            return False
        
        # Verificar limite da conta (se conhecido)
        if self.account_remaining is not None and self.account_remaining <= 10:
            logger.error(f"🚨 Conta quase sem requests: {self.account_remaining} restantes")
            return False
        
        return True

    def _increment_counter(self, response: Optional[httpx.Response] = None):
        """Incrementa contador e atualiza estatísticas"""
        self.daily_count += 1
        
        # Atualizar info da conta se temos resposta
        if response is not None:
            self._update_from_headers(response)
        
        # Logs e alertas
        remaining = self.daily_limit - self.daily_count
        usage_pct = self.daily_count / self.daily_limit
        
        # Log periódico
        if self.daily_count % 100 == 0 or remaining < 200:
            logger.info(f"📊 API Bot: {self.daily_count}/{self.daily_limit} ({usage_pct:.1%} - {remaining} restantes)")
        
        # Alertas
        if usage_pct >= self.warn_threshold and usage_pct < self.block_threshold:
            logger.warning(f"⚠️ Bot aproximando-se do limite: {usage_pct:.1%} usado")
        elif remaining == 100:
            logger.warning(f"🟡 Restam apenas {remaining} requests hoje!")
        elif remaining == 25:
            logger.error(f"🔴 CRÍTICO: Apenas {remaining} requests restantes!")

    def get_fixtures_by_date(self, date_str: str, league_id=None, status="NS"):
        """Busca jogos por data com controlo de quota"""
        if not self._can_make_request():
            logger.warning("🚫 get_fixtures_by_date bloqueado - limite atingido")
            return []

        try:
            with httpx.Client(headers=self.headers, timeout=30.0) as client:
                params = {"date": date_str, "status": status}
                if league_id:
                    params["league"] = league_id

                url = f"{self.base_url}/fixtures"
                response = client.get(url, params=params)
                self._increment_counter(response)
                
                if response.status_code == 200:
                    data = response.json()
                    fixtures = data.get('response', [])
                    logger.debug(f"📊 Fixtures: {len(fixtures)} encontrados")
                    return fixtures
                elif response.status_code == 429:
                    logger.error("🚨 Rate limit atingido pela API")
                    return []
                else:
                    logger.error(f"❌ API Error {response.status_code}")
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
                self._increment_counter(response)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get('response', [])
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
                self._increment_counter(response)
                
                if response.status_code == 200:
                    data = response.json()
                    stats = data.get('response', {})
                    
                    if stats and 'goals' in stats:
                        goals_for = stats['goals']['for']['total']['total'] or 0
                        games_played = stats['fixtures']['played']['total'] or 1
                        average = goals_for / games_played if games_played > 0 else 0.0
                        return average
                    return None
                else:
                    logger.error(f"❌ API Error {response.status_code} para stats team {team_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Erro em get_team_goals_average: {e}")
            return None

    def get_daily_usage_stats(self) -> dict:
        """Retorna estatísticas diárias de uso"""
        self._check_daily_reset()
        remaining = self.daily_limit - self.daily_count
        percentage = (self.daily_count / self.daily_limit) * 100
        
        return {
            'bot_used': self.daily_count,
            'bot_limit': self.daily_limit,
            'bot_remaining': remaining,
            'bot_percentage': round(percentage, 1),
            'account_remaining': self.account_remaining,
            'account_limit': self.account_limit,
            'date': self.current_date.strftime('%d/%m/%Y'),
            'reset_time': '00:00 UTC (próximo dia)'
        }

    def should_throttle(self, min_remaining: int = 100) -> bool:
        """Indica se devemos reduzir atividade para preservar quota"""
        self._check_daily_reset()
        
        # Verificar limite do bot
        if (self.daily_limit - self.daily_count) <= min_remaining:
            return True
            
        # Verificar limite da conta
        if self.account_remaining is not None and self.account_remaining <= min_remaining:
            return True
            
        return False

import time
import requests
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from config import Config
import logging

logger = logging.getLogger(__name__)

class ApiFootballClient:
    """Cliente unificado para a API Football com cache e controle de taxa"""
    
    def __init__(self):
        self.football_key = Config.API_FOOTBALL_KEY
        self.livescore_key = Config.LIVESCORE_API_KEY or Config.API_FOOTBALL_KEY
        self.base_url = "https://v3.football.api-sports.io"
        
        # Contador de requisições
        self.request_count = 0
        
        # Cache para armazenar respostas
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.cache_durations = {
            "fixtures": 300,        # 5 minutos
            "team_stats": 3600,     # 1 hora
            "league_stats": 7200,   # 2 horas
            "team_info": 86400      # 24 horas
        }
        
        logger.info("ApiFootballClient inicializado")

    def _is_cache_valid(self, timestamp: float, cache_type: str) -> bool:
        """Verifica se um item no cache ainda é válido"""
        duration = self.cache_durations.get(cache_type, 300)
        return (time.time() - timestamp) < duration

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None, 
                      cache_key: Optional[str] = None, cache_type: Optional[str] = None,
                      use_livescore_key: bool = False) -> List[Dict[str, Any]]:
        """Faz requisição HTTP GET com cache e retries"""
        
        # Verificar cache primeiro
        if cache_key and cache_type:
            cached_data = self.cache.get(cache_key)
            if cached_data and self._is_cache_valid(cached_data[1], cache_type):
                logger.debug(f"Cache hit para {cache_key}")
                return cached_data[0]
        
        # Verificar limite de requisições
        if self.request_count >= Config.MAX_API_REQUESTS:
            logger.warning(f"Limite de {Config.MAX_API_REQUESTS} requisições atingido")
            return []
        
        # Escolher chave da API
        current_api_key = self.livescore_key if use_livescore_key else self.football_key
        headers = {"x-apisports-key": current_api_key}
        
        # Fazer requisição com retries
        for attempt in range(3):
            if self.request_count > 0:
                time.sleep(Config.API_REQUEST_DELAY)
            
            try:
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    params=params or {},
                    timeout=30
                )
                
                self.request_count += 1
                
                if response.status_code == 429:
                    wait_time = (attempt + 1) * 10
                    logger.warning(f"Rate limit API: aguardando {wait_time}s")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json().get("response", [])
                
                # Armazenar no cache
                if cache_key and cache_type:
                    self.cache[cache_key] = (data, time.time())
                
                return data
                
            except Exception as e:
                logger.error(f"Erro API (tentativa {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep((attempt + 1) * 2)
        
        return []

    def get_current_season(self, league_id: int) -> int:
        """Determina a temporada atual para uma liga"""
        now = datetime.now()
        european_leagues = [39, 140, 135, 78, 61, 94, 144, 203]
        
        if league_id in european_leagues:
            return now.year if now.month >= 8 else now.year - 1
        else:
            return now.year

    def get_team_id(self, team_name: str) -> Optional[int]:
        """Busca ID do time pelo nome"""
        cache_key = f"team_id:{team_name}"
        data = self._make_request("/teams", {"search": team_name}, cache_key, "team_info")
        
        if data and data[0].get("team", {}).get("id"):
            return data[0]["team"]["id"]
        return None

    def get_fixtures_by_date(self, date_str: str, league_id: Optional[int] = None, 
                           status: str = "NS") -> List[Dict[str, Any]]:
        """Obtém jogos para uma data específica"""
        params = {"date": date_str, "status": status}
        if league_id:
            params["league"] = league_id
            params["season"] = self.get_current_season(league_id)
            
        cache_key = f"fixtures:{date_str}:{league_id or 'all'}:{status}"
        return self._make_request("/fixtures", params, cache_key, "fixtures")

    def get_team_recent_matches(self, team_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Obtém as últimas N partidas de um time"""
        cache_key = f"recent_matches:{team_id}:{limit}"
        params = {"team": team_id, "last": limit, "status": "FT"}
        return self._make_request("/fixtures", params, cache_key, "team_stats")

    def get_team_goals_average(self, team_id: int, league_id: int, season: int) -> Optional[float]:
        """Obtém média de gols de um time em uma liga/temporada"""
        cache_key = f"team_avg:{team_id}:{league_id}:{season}"
        data = self._make_request("/teams/statistics", {
            "team": team_id,
            "league": league_id,
            "season": season
        }, cache_key, "team_stats")
        
        if data:
            try:
                stats = data[0]
                avg_str = stats["goals"]["for"]["average"]["total"]
                if avg_str and avg_str.strip():
                    return float(avg_str)
                else:
                    total_goals = stats["goals"]["for"]["total"]["total"]
                    total_games = stats["fixtures"]["played"]["total"]
                    return total_goals / total_games if total_games > 0 else 0.0
            except Exception as e:
                logger.warning(f"Erro ao processar média de gols: {e}")
                return None
        return None

    def get_teams_stats_batch(self, team_ids: List[int], last_n: int = 4) -> Dict[int, Tuple[Optional[float], int]]:
        """Obtém estatísticas de gols para múltiplos times"""
        results: Dict[int, Tuple[Optional[float], int]] = {}
        unique_teams = list(dict.fromkeys(team_ids))
        
        for team_id in unique_teams:
            if self.request_count >= Config.MAX_API_REQUESTS:
                results[team_id] = (None, 0)
                continue
            
            try:
                fixtures = self.get_team_recent_matches(team_id, last_n)
                
                if not fixtures:
                    results[team_id] = (None, 0)
                    continue
                
                goals_scored = []
                for fixture in fixtures:
                    home_id = fixture["teams"]["home"]["id"]
                    away_id = fixture["teams"]["away"]["id"]
                    home_goals = fixture["goals"]["home"] or 0
                    away_goals = fixture["goals"]["away"] or 0
                    
                    if team_id == home_id:
                        goals_scored.append(home_goals)
                    elif team_id == away_id:
                        goals_scored.append(away_goals)
                
                if goals_scored:
                    avg = round(sum(goals_scored) / len(goals_scored), 2)
                    results[team_id] = (avg, len(goals_scored))
                else:
                    results[team_id] = (None, 0)
                
            except Exception as e:
                logger.error(f"Erro ao buscar stats do time {team_id}: {e}")
                results[team_id] = (None, 0)
        
        return results

    async def get_fixtures_async(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Versão assíncrona para buscar fixtures"""
        headers = {"x-apisports-key": self.livescore_key}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/fixtures",
                    headers=headers,
                    params=params,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", [])
        except Exception as e:
            logger.error(f"Erro async na API: {e}")
        
        return []


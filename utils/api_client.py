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
        # Ligas europeias começam em agosto/setembro
        european_leagues = [39, 140, 135, 78, 61, 94, 144, 203]
        
        if league_id in european_leagues:
            return now.year if now.month >= 8 else now.year - 1
        else:
            return now.year

    def get_team_id(self, team_name: str) -> Optional[int]:
        """Busca ID do time pelo nome - VERSÃO CORRIGIDA"""
        cache_key = f"team_id:{team_name}"
        data = self._make_request("/teams", {"search": team_name}, cache_key, "team_info")
        
        # CORREÇÃO: Verificação robusta da resposta
        if data and isinstance(data, list) and len(data) > 0:
            team_info = data[0]
            if isinstance(team_info, dict) and team_info.get("team", {}).get("id"):
                return team_info["team"]["id"]
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
        """Obtém média de gols de um time em uma liga/temporada - VERSÃO CORRIGIDA CRÍTICA"""
        cache_key = f"team_avg:{team_id}:{league_id}:{season}"
        
        logger.debug(f"🔍 Buscando stats: team={team_id}, league={league_id}, season={season}")
        
        data = self._make_request("/teams/statistics", {
            "team": team_id,
            "league": league_id,
            "season": season
        }, cache_key, "team_stats")
        
        if not data:
            logger.debug(f"❌ Nenhum dado retornado para team {team_id}")
            return None

        try:
            # CORREÇÃO CRÍTICA: API pode retornar objeto diretamente ou lista com um objeto
            if isinstance(data, list):
                if len(data) == 0:
                    logger.debug(f"❌ Lista vazia para team {team_id}")
                    return None
                stats = data[0]  # Primeiro item da lista
            else:
                stats = data  # Objeto direto
            
            if not stats or not isinstance(stats, dict):
                logger.debug(f"❌ Stats inválidas para team {team_id}: {type(stats)}")
                return None

            logger.debug(f"📊 Stats structure for team {team_id}: {type(stats)}")

            # MÉTODO 1: Tentar pegar média pré-calculada da API
            try:
                goals_section = stats.get("goals", {})
                for_section = goals_section.get("for", {}) if goals_section else {}
                average_section = for_section.get("average", {}) if for_section else {}
                avg_str = average_section.get("total") if average_section else None
                
                if avg_str is not None and str(avg_str).strip() and str(avg_str).strip() != "":
                    avg_value = float(avg_str)
                    logger.debug(f"✅ Team {team_id}: média API = {avg_value}")
                    return round(avg_value, 2)
                else:
                    logger.debug(f"⚠️ Team {team_id}: média API vazia ou nula ({avg_str})")
            except Exception as e:
                logger.debug(f"⚠️ Erro ao acessar média pré-calculada team {team_id}: {e}")
            
            # MÉTODO 2: FALLBACK - Calcular média manualmente
            try:
                goals_section = stats.get("goals", {})
                for_section = goals_section.get("for", {}) if goals_section else {}
                total_section = for_section.get("total", {}) if for_section else {}
                total_goals = total_section.get("total", 0) if total_section else 0
                
                fixtures_section = stats.get("fixtures", {})
                played_section = fixtures_section.get("played", {}) if fixtures_section else {}
                total_games = played_section.get("total", 0) if played_section else 0
                
                logger.debug(f"📊 Team {team_id}: {total_goals} gols em {total_games} jogos")
                
                if total_games > 0:
                    calculated_avg = total_goals / total_games
                    logger.debug(f"✅ Team {team_id}: média calculada = {calculated_avg}")
                    return round(calculated_avg, 2)
                else:
                    logger.debug(f"⚠️ Team {team_id}: nenhum jogo jogado")
                    return 0.0
                    
            except Exception as e:
                logger.debug(f"❌ Erro no cálculo manual team {team_id}: {e}")
                
            # MÉTODO 3: ÚLTIMO RECURSO - Tentar estrutura alternativa
            try:
                # Algumas vezes a API retorna estrutura diferente
                if "goals" in stats and "for" in stats["goals"]:
                    total_goals = stats["goals"]["for"].get("total", {}).get("total", 0)
                    total_games = stats["fixtures"]["played"].get("total", 0)
                    
                    if total_games > 0:
                        fallback_avg = total_goals / total_games
                        logger.debug(f"🔧 Team {team_id}: fallback média = {fallback_avg}")
                        return round(fallback_avg, 2)
            except:
                pass
            
            logger.warning(f"❌ Team {team_id}: não foi possível calcular média com nenhum método")
            return None
                
        except Exception as e:
            logger.error(f"❌ Erro geral ao processar stats do team {team_id}: {e}")
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

    def get_teams_ht_stats_batch(self, team_ids: List[int], last_n: int = 4) -> Dict[int, Tuple[Optional[float], int]]:
        """Obtém estatísticas HT para múltiplos times"""
        results: Dict[int, Tuple[Optional[float], int]] = {}
        unique_teams = list(dict.fromkeys(team_ids))
        
        for team_id in unique_teams:
            try:
                cache_key = f"{team_id}:{last_n}"
                cached = self.cache.get(f"team_ht_stats:{cache_key}")
                
                if cached and self._is_cache_valid(cached[1], "team_stats"):
                    results[team_id] = cached[0]
                    continue
                
                if self.request_count >= Config.MAX_API_REQUESTS:
                    results[team_id] = (None, 0)
                    continue
                
                params = {"team": team_id, "last": last_n, "status": "FT"}
                fixtures = self._make_request("/fixtures", params, f"team_ht_stats:{cache_key}", "team_stats")
                
                if not fixtures:
                    results[team_id] = (None, 0)
                    continue
                
                ht_totals = []
                for fixture in fixtures:
                    score = fixture.get("score", {})
                    halftime = score.get("halftime", {})
                    ht_home = halftime.get("home")
                    ht_away = halftime.get("away")
                    
                    if ht_home is not None and ht_away is not None:
                        ht_totals.append(ht_home + ht_away)
                
                if ht_totals:
                    avg = round(sum(ht_totals) / len(ht_totals), 2)
                    results[team_id] = (avg, len(ht_totals))
                else:
                    results[team_id] = (None, 0)
                
            except Exception as e:
                logger.error(f"Erro HT stats team {team_id}: {e}")
                results[team_id] = (None, 0)
        
        return results

    def get_league_real_stats(self, league_id: int, season: int) -> Optional[Dict[str, Any]]:
        """Obtém estatísticas reais da liga"""
        if not Config.ENABLE_REAL_LEAGUE_STATS:
            return None
        
        cache_key = f"league_stats:{league_id}:{season}"
        cached = self.cache.get(cache_key)
        
        if cached and self._is_cache_valid(cached[1], "league_stats"):
            return cached[0]
        
        if self.request_count >= Config.MAX_API_REQUESTS - 10:
            return None
        
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=120)
            
            params = {
                "league": league_id, 
                "season": season,
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date.strftime("%Y-%m-%d"),
                "status": "FT"
            }
            
            fixtures = self._make_request("/fixtures", params, cache_key, "league_stats")
            
            if not fixtures or len(fixtures) < 30:
                return None
            
            total_games = len(fixtures)
            total_goals = 0
            total_goals_ht = 0
            btts_count = 0
            over15_ht_count = 0
            over25_count = 0
            over35_count = 0
            
            for fixture in fixtures:
                home_goals = fixture["goals"]["home"] or 0
                away_goals = fixture["goals"]["away"] or 0
                match_goals = home_goals + away_goals
                total_goals += match_goals
                
                score = fixture.get("score", {})
                halftime = score.get("halftime", {})
                home_ht = halftime.get("home") if halftime.get("home") is not None else 0
                away_ht = halftime.get("away") if halftime.get("away") is not None else 0
                match_goals_ht = home_ht + away_ht
                total_goals_ht += match_goals_ht
                
                if home_goals > 0 and away_goals > 0:
                    btts_count += 1
                if match_goals_ht > 1.5:
                    over15_ht_count += 1
                if match_goals > 2.5:
                    over25_count += 1
                if match_goals > 3.5:
                    over35_count += 1
            
            return {
                "total_games": total_games,
                "avg_goals_per_match": round(total_goals / total_games, 2),
                "avg_goals_ht": round(total_goals_ht / total_games, 2),
                "btts_rate": round((btts_count / total_games) * 100),
                "over15_ht_rate": round((over15_ht_count / total_games) * 100),
                "over25_rate": round((over25_count / total_games) * 100),
                "over35_rate": round((over35_count / total_games) * 100),
                "second_half_share": round(((total_goals - total_goals_ht) / total_goals) * 100) if total_goals > 0 else 50,
                "days_analyzed": 120,
                "is_real": True
            }
            
        except Exception as e:
            logger.warning(f"Erro ao calcular stats da liga {league_id}: {e}")
            return None

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

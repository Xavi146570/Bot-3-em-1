# Configurações para o módulo de Regressão à Média
REGRESSAO_LEAGUES = {
    39: {"name": "Premier League", "country": "Inglaterra", "0x0_ft_percentage": 26, "over_15_percentage": 89, "tier": 1},
    140: {"name": "La Liga", "country": "Espanha", "0x0_ft_percentage": 23, "over_15_percentage": 78, "tier": 1},
    78: {"name": "Bundesliga", "country": "Alemanha", "0x0_ft_percentage": 19, "over_15_percentage": 85, "tier": 1},
    135: {"name": "Serie A", "country": "Itália", "0x0_ft_percentage": 25, "over_15_percentage": 81, "tier": 1},
    61: {"name": "Ligue 1", "country": "França", "0x0_ft_percentage": 21, "over_15_percentage": 76, "tier": 1},
    # ... (adicione todas as ligas do seu código original)
}

# Configurações para o módulo de 10 Campeonatos
CAMPEONATOS_LEAGUES = {
    "ENG1": {
        "api_id": 39, "name": "Premier League", "timezone": "Europe/London",
        "criteria": {"min_team_avg_goals": 2.30, "min_team_avg_goals_ht": 1.20, "min_sample_games": 4},
        "historical_minimums": {"avg_goals_per_match": 2.75, "btts_rate": 58, "over25_rate": 60, "over35_rate": 30, "second_half_share": 52, "over15_ht_rate": 28},
        "peak_minutes": {"60": 16, "75": 17, "85": 22}, "peak_window": {"start": 61, "end": 75, "prob_min": 17}
    },
    # ... (adicione todas as configurações do seu código original)
}


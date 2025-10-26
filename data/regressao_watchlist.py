def calculate_risk_level(empates_0x0_str, odd_justa):
    """Calcula nível de risco baseado nas estatísticas"""
    try:
        empates_pct = float(str(empates_0x0_str).replace('%', '').replace(',', '.'))
        odd_justa = float(str(odd_justa).replace(',', '.'))
        
        if empates_pct <= 5.0 and odd_justa <= 1.0:
            return "BAIXO"
        elif empates_pct <= 7.0 and odd_justa <= 3.0:
            return "MODERADO"
        else:
            return "ALTO"
    except (ValueError, TypeError):
        return "DESCONHECIDO"

REGRESSAO_WATCHLIST = {
    "Alemanha 2. Bundesliga": [
        {"name": "1860 Munchen", "empates_0x0": "2.63%", "odd_justa": 0.67, "jogos": 152, "comentario": "Confiável, baixa variância"},
        {"name": "Dusseldorf", "empates_0x0": "3.68%", "odd_justa": 0.25, "jogos": 136, "comentario": "Extremamente estável"},
        {"name": "Hamburger SV", "empates_0x0": "1.47%", "odd_justa": 0.33, "jogos": 136, "comentario": "Confiável na divisão inferior"},
        {"name": "Mannheim", "empates_0x0": "4.61%", "odd_justa": 2.92, "jogos": 152, "comentario": "Baixo 0-0, variância moderada"},
        {"name": "Verl", "empates_0x0": "4.61%", "odd_justa": 4.25, "jogos": 152, "comentario": "Baixo 0-0, variância tolerável"},
        {"name": "Viktoria Koln", "empates_0x0": "2.63%", "odd_justa": 0.67, "jogos": 152, "comentario": "Estável, baixo 0-0"},
        {"name": "Dortmund B", "empates_0x0": "5.92%", "odd_justa": 0.92, "jogos": 152, "comentario": "Consistente, mas 5%+"},
        {"name": "FC Nurnberg", "empates_0x0": "6.62%", "odd_justa": 2.92, "jogos": 136, "comentario": "Variância moderada, acima de 6%"},
        {"name": "Hannover 96", "empates_0x0": "7.35%", "odd_justa": 1.67, "jogos": 136, "comentario": "Razoavelmente estável, mas 7%+"},
        {"name": "Karlsruher SC", "empates_0x0": "5.15%", "odd_justa": 0.92, "jogos": 136, "comentario": "Consistente, mas acima de 5%"},
        {"name": "Paderborn", "empates_0x0": "7.35%", "odd_justa": 1.00, "jogos": 136, "comentario": "Consistente, mas 7%+"}
    ],
    "Inglaterra Premier League": [
        {"name": "Arsenal", "empates_0x0": "3.95%", "odd_justa": 0.33, "jogos": 152, "comentario": "Muito estável, baixo 0-0"},
        {"name": "Aston Villa", "empates_0x0": "2.63%", "odd_justa": 0.00, "jogos": 152, "comentario": "Consistência perfeita"},
        {"name": "Chelsea", "empates_0x0": "4.61%", "odd_justa": 2.25, "jogos": 152, "comentario": "Baixo 0-0, variância moderada"},
        {"name": "Liverpool", "empates_0x0": "3.29%", "odd_justa": 3.58, "jogos": 152, "comentario": "Baixo 0-0, variância gerenciável"},
        {"name": "Manchester City", "empates_0x0": "1.97%", "odd_justa": 0.92, "jogos": 152, "comentario": "Gols tardios comuns"},
        {"name": "Manchester United", "empates_0x0": "3.95%", "odd_justa": 0.33, "jogos": 152, "comentario": "Muito estável, baixo 0-0"},
        {"name": "Tottenham", "empates_0x0": "1.32%", "odd_justa": 1.00, "jogos": 152, "comentario": "Baixo 0-0, estilo ofensivo"},
        {"name": "West Ham United", "empates_0x0": "2.63%", "odd_justa": 0.67, "jogos": 152, "comentario": "Estável, muitos gols"},
        {"name": "Wolverhampton", "empates_0x0": "3.95%", "odd_justa": 1.67, "jogos": 152, "comentario": "Baixo 0-0, consistência razoável"},
        {"name": "Brentford", "empates_0x0": "6.58%", "odd_justa": 0.33, "jogos": 152, "comentario": "Muito estável, mas 6%+"},
        {"name": "Brighton", "empates_0x0": "7.24%", "odd_justa": 0.92, "jogos": 152, "comentario": "Consistente, mas 7%+"},
        {"name": "Crystal Palace", "empates_0x0": "8.55%", "odd_justa": 2.25, "jogos": 152, "comentario": "Variância moderada, acima de 8%"},
        {"name": "Everton", "empates_0x0": "7.89%", "odd_justa": 2.00, "jogos": 152, "comentario": "Variância moderada, acima de 7%"},
        {"name": "Newcastle United", "empates_0x0": "5.26%", "odd_justa": 11.33, "jogos": 152, "comentario": "Variância muito alta, arriscado"}
    ],
    "Holanda Eredivisie": [
        {"name": "Ajax Amsterdam", "empates_0x0": "4.41%", "odd_justa": 1.67, "jogos": 136, "comentario": "Razoavelmente estável, ofensivo"},
        {"name": "AZ Alkmaar", "empates_0x0": "4.41%", "odd_justa": 0.33, "jogos": 136, "comentario": "Muito estável, baixo 0-0"},
        {"name": "FC Twente", "empates_0x0": "2.94%", "odd_justa": 0.67, "jogos": 136, "comentario": "Altamente estável"},
        {"name": "Feyenoord", "empates_0x0": "4.41%", "odd_justa": 1.00, "jogos": 136, "comentario": "Consistente, baixo 0-0"},
        {"name": "PSV Eindhoven", "empates_0x0": "0.74%", "odd_justa": 0.25, "jogos": 136, "comentario": "Dominante, gols tardios prováveis"},
        {"name": "FC Utrecht", "empates_0x0": "5.88%", "odd_justa": 0.67, "jogos": 136, "comentario": "Estável, mas acima de 5%"},
        {"name": "Go Ahead Eagles", "empates_0x0": "5.15%", "odd_justa": 1.58, "jogos": 136, "comentario": "Razoavelmente estável, mas acima de 5%"}
    ],
    "Alemanha Bundesliga": [
        {"name": "Bayern Munich", "empates_0x0": "0.74%", "odd_justa": 0.25, "jogos": 136, "comentario": "Time de elite, 0-0 extremamente raro"},
        {"name": "Bochum", "empates_0x0": "2.94%", "odd_justa": 1.33, "jogos": 136, "comentario": "Baixo 0-0, consistência razoável"},
        {"name": "Dortmund", "empates_0x0": "1.47%", "odd_justa": 0.33, "jogos": 136, "comentario": "Conhecido por gols tardios"},
        {"name": "Eintracht Frankfurt", "empates_0x0": "3.68%", "odd_justa": 2.25, "jogos": 136, "comentario": "Baixo 0-0, consistência razoável"},
        {"name": "Hoffenheim", "empates_0x0": "2.94%", "odd_justa": 0.67, "jogos": 136, "comentario": "Estável, boa pontuação"},
        {"name": "Stuttgart", "empates_0x0": "3.68%", "odd_justa": 1.58, "jogos": 136, "comentario": "Estável, baixo 0-0"}
    ]
    # Adiciona todas as outras ligas que forneceste, mantendo o mesmo formato
}

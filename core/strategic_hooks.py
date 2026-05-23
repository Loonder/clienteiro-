# Strategic Hooks Library (Zero-AI / Zero-Cost)

HOOK_TEMPLATES = {
    'Dentista': [
        "Vi que sua clínica em {city} tem um score de {score}% em automação. Podemos dobrar seu agendamento hoje?",
        "Otimizamos a captação de pacientes para consultórios em {city}. Você é a bola da vez.",
        "A {company} está perdendo pacientes para clínicas mais 'rápidas' em {city}. Vamos automatizar?"
    ],
    'Advogado': [
        "Sua presença digital em {city} pode escalar. Analisamos seu score ({score}%) e temos o plano certo.",
        "Como advogados em {city} estão fechando contratos via WhatsApp? Temos a resposta.",
        "Identificamos que a {company} tem um 'vácuo' digital em {city}. Queremos preenchê-lo com leads."
    ],
    'Academia': [
        "O score da {company} está em {score}%. Vamos transformar visitantes em matriculados agora?",
        "Academia cheia em {city}? Nossa automação de leads é o segredo.",
        "Sua recepção em {city} não dá conta? Nossa IA de triagem resolve o gargalo."
    ],
    'Imobiliaria': [
        "Corretores em {city} estão implorando por esses leads. A {company} vai ficar de fora?",
        "Seu score de {score}% mostra que você tem imóveis, mas falta velocidade no WA.",
        "Domine o mercado imobiliário de {city} com nossa extração de leads qualificados."
    ],
    'Oficina Mecanica': [
        "Pátio vazio em {city}? Analisamos o score da {company} e sabemos como atrair novos clientes.",
        "Seu concorrente em {city} já usa automação. Recupere o tempo perdido com {score}% de melhoria."
    ],
    'default': [
        "O score da {company} foi analisado ({score}%). Temos 3 pontos de melhoria para {city} agora.",
        "Vi seu perfil em {city} e identifiquei uma oportunidade de escala imediata. Vamos falar?",
        "Urgente: Detectamos 5 falhas no funil da {company} em {city}. Veja como corrigir."
    ]
}

def get_best_hook(lead_data):
    """
    Selects the most aggressive/persuasive hook based on local templates.
    """
    nicho = lead_data.get('nicho', 'default')
    city = lead_data.get('city', 'sua cidade')
    company = lead_data.get('company_name', 'sua empresa')
    score = lead_data.get('clienteiro_score', 0)
    
    import random
    options = HOOK_TEMPLATES.get(nicho, HOOK_TEMPLATES['default'])
    hook = random.choice(options)
    
    return hook.format(city=city, company=company, score=score)

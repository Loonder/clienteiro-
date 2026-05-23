import unicodedata

from core.scorer import B2BScorer, B2PScorer, CollegeScorer, get_scorer


def test_scorer_factory():
    assert isinstance(get_scorer({'type_focus': 'B2B'}), B2BScorer)
    assert isinstance(get_scorer({'type_focus': 'B2P'}), B2PScorer)
    assert isinstance(get_scorer({'type_focus': 'COLLEGE'}), CollegeScorer)
    assert isinstance(get_scorer({'type_focus': 'UNKNOWN'}), B2BScorer)
    assert isinstance(get_scorer(None), B2BScorer)


def test_b2b_scoring():
    scorer = B2BScorer()
    lead = {
        'has_website': True,
        'company_name': 'Acme',
        'city': 'Sao Paulo',
        'nicho': 'Escritorio',
    }
    score = scorer.score(lead)
    assert score > 0
    normalized_label = unicodedata.normalize(
        'NFKD', scorer.get_label(score)
    ).encode('ascii', 'ignore').decode()
    assert normalized_label in [
        'Analogia / Risco de Esquecimento',
        'Digital Inicial / Presenca Basica',
        'Em Transicao / Potencial de Escala',
        'Digital High-Performance',
        'Dominador de Mercado / Elite',
    ]


def test_b2p_scoring():
    scorer = B2PScorer()
    lead = {'has_instagram': True, 'company_name': 'Loja A'}
    score = scorer.score(lead)
    assert score > 0


def test_college_scoring():
    scorer = CollegeScorer()
    lead = {'dept': 'Ciencia da Computacao', 'company_name': 'Faculdade X'}
    score = scorer.score(lead)
    assert score > 0

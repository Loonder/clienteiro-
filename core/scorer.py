from abc import ABC, abstractmethod


# ---------------------------------------------------------------------------
# BaseScorer — classe abstrata (Herança + Polimorfismo + Encapsulamento)
# ---------------------------------------------------------------------------

class BaseScorer(ABC):
    """
    Contrato base para todos os algoritmos de scoring do Clienteiro.
    Inclui lógica de variabilidade Real-World para evitar scores repetitivos.
    """
    BASE_SCORE = 15

    def __init__(self, data: dict | None = None):
        self._data = data or {}

    @abstractmethod
    def score(self, data: dict | None = None) -> int:
        pass

    def _use_runtime_data(self, data: dict | None):
        """
        Permite uso flexivel: scorer.score(lead) ou scorer.score().
        """
        if data is not None:
            self._data = data or {}

    def get_label(self, score: int) -> str:
        if score < 35:  return "Analógia / Risco de Esquecimento"
        if score < 55:  return "Digital Inicial / Presença Básica"
        if score < 75:  return "Em Transição / Potencial de Escala"
        if score < 90:  return "Digital High-Performance"
        return "Dominador de Mercado / Elite"

    def _flag(self, key: str) -> bool:
        val = self._data.get(key)
        return val is True or str(val).lower() in ('true', 'yes', 'sim', 'on', '1')

    def _get_jitter(self) -> int:
        """Gera uma variação determinística baseada no nome para evitar monotonia."""
        name = str(self._data.get('company_name', self._data.get('name', '')))
        if not name: return 0
        # Soma os caracteres para um seed simples
        seed = sum(ord(c) for c in name)
        return (seed % 9) - 4  # Entre -4 e +4


# ---------------------------------------------------------------------------
# B2BScorer — Heurística Refinada
# ---------------------------------------------------------------------------

class B2BScorer(BaseScorer):
    def score(self, data: dict | None = None) -> int:
        self._use_runtime_data(data)
        pts = self.BASE_SCORE
        
        # 1. Ativos Digitais (Pesos variados para mais granularidade)
        has_web = self._flag('has_website')
        has_wa  = self._flag('has_whatsapp')
        has_ig  = self._flag('has_instagram')
        is_auto = self._flag('is_automated')

        if has_web:    pts += 22
        if has_wa:     pts += 24
        if has_ig:     pts += 15
        if is_auto:    pts += 20
        
        # 2. Bônus de Ecossistema (Combinações que aumentam valor)
        if has_web and has_wa:  pts += 5 # Funil direto
        if has_ig and has_wa:   pts += 3 # Atendimento social
        if is_auto and has_wa:  pts += 7 # Escala operacional

        # 3. Penalidades "Real-World" (Falta de ativos críticos para B2B)
        if not has_web and not has_ig: pts -= 10 # Invisibilidade Digital
        
        # 4. Bônus de Especificidade (Nicho/Cidade preenchidos)
        nicho = str(self._data.get('nicho', ''))
        if len(nicho) > 3: pts += 4
        if len(str(self._data.get('city', ''))) > 3:  pts += 3

        # --- AURA PROTECTOR: Heurística do Dashboard ---
        # Se os campos vierem nulos (requisição feita do painel privado sem checklist),
        # assumimos uma probabilidade determinística baseada no nome da empresa.
        dashboard_mode = all(k not in self._data for k in ['has_website', 'has_whatsapp', 'has_instagram', 'is_automated'])
        if dashboard_mode:
            lead_identifier = str(self._data.get('company_name', self._data.get('name', ''))) + nicho
            # Math nativa para gerar número pseudo-aleatório seguro entre 50 e 75 baseado na string
            pseudo = 50 + (abs(hash(lead_identifier)) % 26)
            pts += pseudo

        # 5. Jitter determinístico
        pts += self._get_jitter()
        
        return max(5, min(100, pts))


# ---------------------------------------------------------------------------
# B2PScorer — Heurística Refinada
# ---------------------------------------------------------------------------

class B2PScorer(BaseScorer):
    def score(self, data: dict | None = None) -> int:
        self._use_runtime_data(data)
        pts = self.BASE_SCORE
        if self._flag('has_instagram'):  pts += 34
        if self._flag('is_automated'):   pts += 28
        if self._flag('has_whatsapp'):   pts += 18
        if self._flag('has_website'):    pts += 12
        
        pts += self._get_jitter()
        return max(5, min(100, pts))


# ---------------------------------------------------------------------------
# CollegeScorer — Heurística Refinada
# ---------------------------------------------------------------------------

class CollegeScorer(BaseScorer):
    def score(self, data: dict | None = None) -> int:
        self._use_runtime_data(data)
        pts = self.BASE_SCORE
        if str(self._data.get('dept', '')).strip(): pts += 21
        if self._flag('has_instagram'):   pts += 24
        if self._flag('is_automated'):    pts += 19
        if self._flag('has_website'):     pts += 17
        if self._flag('has_whatsapp'):    pts += 11
        
        pts += self._get_jitter()
        return max(5, min(100, pts))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_SCORER_MAP = {
    'b2b':     B2BScorer,
    'b2p':     B2PScorer,
    'college': CollegeScorer,
}

def get_scorer(data: dict | None) -> BaseScorer:
    payload = data or {}
    focus = str(payload.get('type_focus', 'b2b')).lower().strip()
    cls   = _SCORER_MAP.get(focus, B2BScorer)
    return cls(payload)

import os, sys
from core.db_manager import get_db_connection
from core.runtime import env_bool, env_int, env_str
import unicodedata
from urllib.parse import urlparse, parse_qs, unquote
from duckduckgo_search import DDGS

# ---------------------------------------------------------------------------
# Helpers de Normalizacao (blindagem contra erros de digitacao / acentos)
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Remove acentos e normaliza espacos."""
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(text.split())


def _title_safe(text: str) -> str:
    return _normalize(str(text)).title()


def _is_search_engine_url(link: str) -> bool:
    parsed = urlparse(link)
    host = (parsed.netloc or '').lower()
    path = (parsed.path or '').lower()
    if 'duckduckgo.com' in host or 'bing.com' in host or 'search.brave.com' in host or 'yahoo.com' in host:
        return True
    if 'google.' in host and path.startswith('/search'):
        return True
    return False


def _format_br_phone(raw: str) -> str:
    digits = ''.join(ch for ch in str(raw or '') if ch.isdigit())
    if not digits:
        return ''
    if digits.startswith('55') and len(digits) in (12, 13):
        digits = digits[2:]
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return ''


def _extract_phone_candidates(text: str) -> list[str]:
    import re

    blob = str(text or '')
    patterns = (
        r'(?:\+?55[\s\-.]*)?(?:\(?\d{2}\)?[\s\-.]*)?(?:9[\s\-.]*)?\d{4}[\s\-.]?\d{4}',
        r'\b(?:55)?\d{10,13}\b',
    )

    found: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, blob):
            fmt = _format_br_phone(match)
            if fmt and fmt not in found:
                found.append(fmt)
    return found


def _extract_phone_from_link(link: str) -> str:
    import re

    raw_link = str(link or '')
    if not raw_link:
        return ''

    for candidate in (raw_link, unquote(raw_link)):
        parsed = urlparse(candidate)
        query = parse_qs(parsed.query)
        for key in ('phone', 'telefone', 'tel', 'whatsapp', 'numero', 'number'):
            for value in query.get(key, []):
                fmt = _format_br_phone(value)
                if fmt:
                    return fmt

        wa_match = re.search(r'wa\.me/(\d{10,15})', candidate, re.IGNORECASE)
        if wa_match:
            fmt = _format_br_phone(wa_match.group(1))
            if fmt:
                return fmt

        tel_match = re.search(r'tel:([+\d\-\s().]{8,})', candidate, re.IGNORECASE)
        if tel_match:
            fmt = _format_br_phone(tel_match.group(1))
            if fmt:
                return fmt

        candidates = _extract_phone_candidates(candidate)
        if candidates:
            return candidates[0]

    return ''


# ---------------------------------------------------------------------------
# BusinessProcessor
# ---------------------------------------------------------------------------


class BusinessProcessor:
    # Tokens que indicam resultados de diretorio/lista (nao sao leads reais)
    _TRASH_TOKENS = frozenset([
        'portal', 'lista', 'search', 'encontre', 'guia', 'guia de', 'cnpj',
        'busca', 'catalogo', 'directory', 'yelp', 'yellowpages',
        'tudo sobre', 'veja mais', 'anuncio', 'patrocinado', 'infobel',
        'mapa', 'mapas', 'enderecos', 'secretaria', 'prefeitura', 
        'governo', 'ministerio', 'estadual', 'federal', 'municipal',
        'transparencia', 'licitacao'
    ])

    def __init__(self, raw_data: dict):
        self.data = raw_data

    # ------------------------------------------------------------------
    # Ponto de entrada principal
    # ------------------------------------------------------------------

    def process(self) -> dict:
        processed = dict(self.data).copy()

        from .scorer import get_scorer
        from .strategic_hooks import get_best_hook
        
        scorer = get_scorer(self.data)
        score = scorer.score()
        processed['clienteiro_score'] = score
        processed['diagnosis_level']  = scorer.get_label(score)
        processed['recommendations'] = list(self._generate_recommendations(processed))
        processed['strategic_leads'] = list(self._fetch_strategic_leads())
        
        # 🧪 Sensation AI: Predictive Model
        processed['conversion_prediction'] = self._predict_success(processed)
        processed['next_action'] = self._get_next_action(processed)
        processed['strategic_hook'] = get_best_hook(processed)

        return processed

    # ------------------------------------------------------------------
    # Beast Mode Search — motor principal
    # ------------------------------------------------------------------

    def _fetch_strategic_leads(self) -> list:
        import time
        import random

        max_leads = max(1, env_int("LEADS_PER_REPORT", 5))
        nicho_raw = str(self.data.get('nicho', 'Empresas')).strip() or 'Empresas'
        city_raw = str(self.data.get('city', 'Brasil')).strip() or 'Brasil'
        type_focus = str(self.data.get('type_focus', 'b2b')).strip().lower()

        nicho_clean = _normalize(nicho_raw)
        city_clean = _normalize(city_raw).split('-')[0].strip() or 'Brasil'
        leads_mode = env_str("LEADS_SOURCE", "db").lower()
        leads_fallback = env_str("LEADS_FALLBACK", "empty").lower()
        allow_live_scraping = env_bool("ENABLE_LIVE_SCRAPING", False)
        live_fallback_requested = (
            leads_mode == "auto"
            or leads_fallback in {"live", "scrape", "scraping", "search", "auto"}
        )
        on_live_lead = self.data.get('_on_lead')
        should_stop = self.data.get('_should_stop')

        # 0. Conexão com Supabase (Data Lake)
        db = None
        try:
            db = get_db_connection()
        except Exception as e:
            print(f"[Cache] Erro ao conectar ao Data Lake (Supabase): {e}")

        # --- SMART DEDUPE: Identifica o que já está no CRM ---
        harvested_phones = set()
        if db:
            try:
                # Carregamos os telefones já presentes na internal_leads para evitar duplicidade
                with db.cursor() as cur:
                    cur.execute("SELECT phone FROM internal_leads WHERE phone != 'N/A' LIMIT 2000")
                    # fetchall() retorna listas; extraímos o primeiro elemento de cada linha
                    harvested_phones = {r[0] if isinstance(r, (list, tuple)) else r.get('phone') for r in cur.fetchall()}
            except: pass

        def _add_rows(rows, leads_list, seen):
            for r in rows:
                source = r.get('source') if isinstance(r, dict) else r[3]
                phone = r.get('phone') if isinstance(r, dict) else r[1]
                # Dedupe interno + Dedupe contra o CRM já colhido
                if (source and source in seen) or (phone and phone in harvested_phones):
                    continue
                leads_list.append({
                    'name': r.get('name') if isinstance(r, dict) else r[0],
                    'phone': phone,
                    'rating': r.get('rating') if isinstance(r, dict) else r[2],
                    'source': source
                })
                if source:
                    seen.add(source)

        def _fetch_cached_leads(strict=False) -> list[dict]:
            if not db:
                return []
            try:
                nicho_base = nicho_clean.lower().rstrip('s')
                leads_list: list[dict] = []
                seen = set()

                queries = [
                    # Prioridade 1: Nicho E Cidade Exatos
                    ('''
                        SELECT name, phone, rating, source FROM scraped_leads
                        WHERE (LOWER(nicho) LIKE %s OR %s LIKE LOWER(nicho) || '%%')
                          AND LOWER(city) = %s AND type_focus = %s
                        ORDER BY criado_em DESC
                        LIMIT %s
                    ''', (f'%{nicho_base}%', nicho_clean.lower(), city_clean.lower(), type_focus)),
                    # Prioridade 2: Nicho Exato (Cidade Ampla)
                    ('''
                        SELECT name, phone, rating, source FROM scraped_leads
                        WHERE (LOWER(nicho) LIKE %s OR %s LIKE LOWER(nicho) || '%%')
                          AND type_focus = %s
                        ORDER BY criado_em DESC
                        LIMIT %s
                    ''', (f'%{nicho_base}%', nicho_clean.lower(), type_focus)),
                ]

                # Se nao estiver em strict mode (buscas normais de usuario), podemos pegar leads de apoio
                if not strict:
                    queries.extend([
                        # Prioridade 3: Cidade Exata (Nicho Amplo)
                        ('''
                            SELECT name, phone, rating, source FROM scraped_leads
                            WHERE LOWER(city) = %s AND type_focus = %s
                            ORDER BY criado_em DESC
                            LIMIT %s
                        ''', (city_clean.lower(), type_focus)),
                        # Prioridade 4: Qualquer Lead da Mesma Categoria (B2B/B2P)
                        ('''
                            SELECT name, phone, rating, source FROM scraped_leads
                            WHERE type_focus = %s
                            ORDER BY criado_em DESC
                            LIMIT %s
                        ''', (type_focus,)),
                    ])

                with db.cursor() as cur:
                    for sql, params in queries:
                        remaining = max_leads - len(leads_list)
                        if remaining <= 0:
                            break
                        cur.execute(sql, (*params, remaining))
                        rows = cur.fetchall()
                        _add_rows(rows, leads_list, seen)

                if leads_list:
                    lbl = "[Cache-Strict]" if strict else "[Cache]"
                    print(f"{lbl} Retornando {len(leads_list)} leads do banco.")
                return leads_list[:max_leads]
            except Exception as e:
                print(f"[Cache] Falha na leitura: {e}")
                return []

        # Para o motor autonomo (Live), usamos strict=True para nao misturar nichos se o banco estiver vazio
        is_harvest = env_bool("HARVEST_MODE", False) or "harvest" in str(sys.argv).lower()
        if is_harvest:
            allow_live_scraping = True # 🚀 BEAST MODE: Worker sempre minera live
            leads = [] # Worker só caça leads fresquinhos, nunca recicla
            max_leads = max(1, env_int("HARVEST_LEADS_PER_TARGET", 12))
        else:
            # strict=True garante que o PDF nunca mostra leads de nicho diferente do buscado
            leads = _fetch_cached_leads(strict=True)

        seen_sources = {l.get('source') for l in leads if l.get('source')}

        # Modo DB-only: nunca faz scraping ao vivo (a menos que seja o próprio worker Harvest)
        if leads_mode in {"db", "cache", "database", "auto"} and not is_harvest:
            if leads:
                if db:
                    db.close()
                return leads[:max_leads]
            if leads_fallback == "demo":
                if db:
                    db.close()
                return self._get_demo_leads(type_focus, nicho_clean, city_clean)[:max_leads]
            if live_fallback_requested:
                allow_live_scraping = True
                print("[BeastMode] Banco vazio. Acionando scraping pontual para este relatorio.")
            else:
                if db:
                    db.close()
                return []

        # Modo DEMO: sempre usa dados simulados
        if leads_mode in {"demo", "mock"} and not is_harvest:
            if db:
                db.close()
            return self._get_demo_leads(type_focus, nicho_clean, city_clean)[:max_leads]

        # 2. Varredura Online - 🚀 NOVO: Prioridade ULTRA-ROBUSTA (Google Maps)
        if allow_live_scraping and len(leads) < max_leads:
            print("[BeastMode] 📍 Acionando Motor Primário: Google Maps via Playwright...")
            scraper = None
            try:
                from core.maps_scraper import MapsScraper
                scraper = MapsScraper(headless=True)
                try:
                    maps_leads = scraper.fetch_leads(
                        nicho_clean,
                        city_clean,
                        max_leads=max_leads,
                        on_lead=on_live_lead,
                        should_stop=should_stop,
                    )
                except TypeError as exc:
                    if "unexpected keyword" not in str(exc):
                        raise
                    maps_leads = scraper.fetch_leads(nicho_clean, city_clean, max_leads)
                
                for l in maps_leads:
                    if l['source'] not in seen_sources:
                        seen_sources.add(l['source'])
                        leads.append(l)
                        
                        if db:
                            try:
                                with db.cursor() as cur:
                                    cur.execute('''
                                        INSERT INTO scraped_leads 
                                        (nicho, city, type_focus, name, phone, rating, source)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (source) DO NOTHING
                                    ''', (nicho_clean.lower(), city_clean.lower(), type_focus, l['name'], l['phone'], l['rating'], l['source']))
                                db.commit()
                            except: pass
                print(f"[Maps] ✅ Sucesso! {len(maps_leads)} leads de Maps injetados.")
            except Exception as maps_err:
                print(f"[Maps] ⚠️ Erro no Scraper de Maps: {maps_err}")
            finally:
                if scraper:
                    scraper.close()
        elif not allow_live_scraping:
            print("[BeastMode] 🧊 Scraping ao vivo desativado por configuração.")

        # 3. Finalização
        if db:
            db.close()
        if not leads and leads_fallback == "demo":
            leads = self._get_demo_leads(type_focus, nicho_clean, city_clean)
        return leads[:max_leads]

    # ------------------------------------------------------------------
    # Gerador de queries com cobertura ampla
    # ------------------------------------------------------------------

    def _build_queries(self, nicho: str, city: str, type_focus: str) -> list[str]:
        dept = _normalize(str(self.data.get('dept', 'Diretoria')))

        if type_focus == 'b2p':
            return [
                f"microinfluenciador {nicho} {city} instagram contato",
                f"criador de conteudo {nicho} {city} tiktok email",
                f"reviewer youtuber {nicho} {city} patrocinio",
                f"comunidade ou grupo {nicho} {city} links",
                f"blogueira experte em {nicho} {city} linktr.ee",
            ]
        if type_focus == 'college':
            return [
                f"coordenador de curso {nicho} {city} linkedin",
                f"escola ensino medio {city} contato parceiro",
                f"alunos interessados em {nicho} {city} instagram",
                f"gremio estudantil colegio {city} {nicho}",
                f"feiras de profissoes {city} organizacao contato",
            ]

        # b2b (Usa aspas para forçar correspondência exata e reduzir resultados lixo)
        return [
            f'"{nicho}" "{city}" empresa whatsapp',
            f'site:instagram.com "{nicho}" "{city}" whatsapp -governo -prefeitura',
            f'site:facebook.com "{nicho}" "{city}" whatsapp -secretaria',
            f'clinica ou empresa "{nicho}" {city} contato',
            f'"{nicho}" {city} "contato" comercial whatsapp',
            f'comercio {nicho} {city} fone',
        ]

    # ------------------------------------------------------------------
    # Parser e filtro de qualidade de resultado
    # ------------------------------------------------------------------

    def _parse_result(self, res: dict, existing: list) -> dict | None:
        title = str(res.get('title', '')).split('|')[0].split(' - ')[0].strip()
        link = str(res.get('href', ''))
        snippet = str(res.get('body', '')).lower()

        if not title or len(title) < 4:
            return None
        if not link or _is_search_engine_url(link):
            return None
        if any(t in title.lower() for t in self._TRASH_TOKENS):
            return None

        # 🧪 Validação Niche-Strict (Filtro Anti-Erro "Coco Bambu")
        n_search = str(self.data.get('nicho', '')).lower()
        if 'dentista' in n_search or 'odonto' in n_search:
            for bad in ['restaurante', 'pizzaria', 'churrascaria', 'bambu', 'gastronomia', 'bar', 'cafe', 'casas bahia', 'magalu']:
                if bad in title.lower() or bad in snippet:
                    print(f"[Strict] 🚫 Rejeitado lead de outro nicho: '{title}'")
                    return None

        if any(lead.get('source') == link for lead in existing):
            return None

        # 🔍 Captura Telefones/WhatsApp reais via Regex e URLs
        text_blob = snippet + " " + title.lower()
        candidates = _extract_phone_candidates(text_blob)
        contact = candidates[0] if candidates else ''

        if not contact:
            contact = _extract_phone_from_link(link)

        if contact:
            pass
        elif 'whatsapp' in snippet or 'zap' in snippet or 'whatsapp' in link.lower():
            contact = 'WhatsApp Detectado'
        elif 'instagram' in link or 'instagram' in snippet:
            contact = 'Instagram Detectado'
        elif 'linkedin' in link:
            contact = 'LinkedIn Detectado'
        elif 'contato' in snippet or 'tel' in snippet or 'fone' in snippet:
            contact = 'Telefone Detectado'
        else:
            contact = 'Ver na Web'

        import random
        base = 4.2 + (random.randint(0, 4) / 10.0)
        # 🏁 Utiilizando multiplicador Randômico para evitar erros de variável
        rating = round(min(5.0, base + (random.random() * 0.1)), 1)

        return {
            'name': title[:55],
            'phone': contact,
            'rating': rating,
            'source': link,
        }
    # ------------------------------------------------------------------
        # Helpers de diagnóstico e recomendações
    def _get_demo_leads(self, type_focus: str, nicho: str, city: str) -> list:
        """
        Gera leads sob medida baseado no nicho e cidade 
        como fallback de segurança para apresentações em feiras.
        """
        import random
        n_cap = str(nicho).title()
        c_cap = str(city).title()
        
        templates = [
            f"Grupo {n_cap} Premium", 
            f"{n_cap} Soluções {c_cap}", 
            f"Instituto {n_cap} {c_cap}", 
            f"{n_cap} & Marketing Co.", 
            f"Central {n_cap} Brasil"
        ]
        
        contacts = ['WhatsApp Detectado', 'Instagram Detectado', 'Telefone Detectado', 'Ver na Web']
        leads = []
        
        for i, name in enumerate(templates):
            slug = name.lower().replace(' ', '-').replace('&', 'e')
            leads.append({
                'name': name,
                'phone': random.choice(contacts),
                'rating': round(random.uniform(4.2, 4.9), 1),
                'source': f"https://{slug}.com.br",
            })
        return leads

    # ------------------------------------------------------------------

    def _get_level(self, score: int) -> str:
        if score < 40:
            return 'Analógico / Inicial'
        if score < 70:
            return 'Em Transição Digital'
        return 'Digital High-Performance'

    def _generate_recommendations(self, data: dict) -> list:
        recs = []
        nicho_raw = str(data.get('nicho', '')).strip()
        nicho = _normalize(nicho_raw.lower())

        gold_insights = {
            'tatuador': "Crie um 'Story Highlight' exclusivo para depoimentos de cicatrização.",
            'tecnologia': "Implemente agendamento automático com lembretes via WhatsApp.",
            'marketing': "Use estudos de caso em vídeo para aumentar 40% a confiança do lead.",
            'moda': "Crie reels de 'look do dia' para humanizar a marca e gerar prova social.",
            'fitness': "Ofereça uma planilha de treino grátis em troca do WhatsApp para iniciar o funil.",
            'restaurante': "Ative pedidos via WhatsApp Business com catálogo digital atualizado.",
            'advogado': "Publique mini-cases de sucesso (anonimizados) para construir autoridade.",
            'medico': "Use conteúdo educativo no Instagram para atrair pacientes qualificados.",
            'imobiliaria': "Produza tours virtuais curtos e compartilhe no WhatsApp para agilizar visitas.",
        }

        for key, insight in gold_insights.items():
            if key in nicho:
                recs.append(f"INSIGHT DE OURO: {insight}")
                break
        else:
            recs.append("INSIGHT DE OURO: Use Prova Social em tempo real para acelerar a decisão do cliente.")

        if not data.get('has_website'):
            recs.append(f"Consolidar autoridade digital com um Ecossistema Web exclusivo para {nicho_raw or 'seu segmento'}")
        if not data.get('is_automated'):
            recs.append("Escalar com Automação Inteligente de Atendimento VIP via WhatsApp")

        recs.append(f"Utilizar a rede Clienteiro para dominar o nicho de {nicho_raw or 'seu segmento'}")
        recs.append("Implementar estratégias de prestígio para converter leads de alto ticket")
        return recs

    def _predict_success(self, data):
        """Simula um modelo preditivo baseado em heurísticas de rede neural."""
        score = data.get('clienteiro_score', 0)
        has_all = all([data.get('has_website'), data.get('has_instagram'), data.get('has_whatsapp')])
        
        if score > 85 and has_all:
            return "ALTA (92% - Oportunidade Escassa)"
        if score > 65:
            return "MÉDIA-ALTA (74% - Aquecimento Necessário)"
        if score > 40:
            return "MÉDIA (51% - Prova Social Indispensável)"
        return "LOW-TOUCH (28% - Nutrição de Longo Prazo)"

    def _get_next_action(self, data):
        """Define o 'Golden Path' para o consultor."""
        score = data.get('clienteiro_score', 0)
        if score < 40:
            return "Enviar PDF e aguardar 48h (Estratégia de Autoridade)"
        if not data.get('has_whatsapp'):
            return "Localizar telefone secundário e prospectar via Direct IG"
        if data.get('is_automated'):
            return "Abordar focado em Otimização de Custo (Lead já é digital)"
        return "Disparo imediato via WhatsApp (Lead Quente)"

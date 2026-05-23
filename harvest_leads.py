import sys
import asyncio

if sys.platform == 'win32':
    try:
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
    except:
        pass

import time
import random
import os
import signal
from core.processor import BusinessProcessor
from core.runtime import env_bool, env_int

# ——— Graceful Shutdown: Sinal de Parada Cirúrgico ———————————————————————
# Quando o Dashboard para o worker, ele recebe SIGTERM.
# Essa flag garante que o loop principal termina de forma limpa,
# sem deixar nenhum Chrome "zumbi" aberto.
_SHUTDOWN = False

def _handle_signal(signum, frame):
    global _SHUTDOWN
    print(f"\n[Harvest] 🛑 Sinal {signum} recebido. Encerrando com segurança...", flush=True)
    _SHUTDOWN = True
    try:
        from core.maps_scraper import MapsScraper
        MapsScraper.close_active_drivers()
    except Exception:
        pass

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)
# ——————————————————————————————————————————————————————————————————————————


# 📍 CIDADES PADRÃO (Caso não haja hunter_config.json)
CIDADES_DEFAULT = [
    'Sao Paulo', 'Guarulhos', 'Campinas', 'Sao Bernardo do Campo', 'Santo Andre', 
    'Osasco', 'Sao Jose dos Campos', 'Ribeirao Preto', 'Sorocaba', 'Santos'
]

# 🎯 NICHOS PADRÃO (Caso não haja hunter_config.json)
NICHOS_DEFAULT = [
    'Dentista', 'Advogado', 'Academia de Ginastica', 'Restaurante', 'Pizzaria', 
    'Pet Shop', 'Oficina Mecanica', 'Imobiliaria', 'Clinica Estetica'
]

def load_hunter_config():
    import json
    path = os.path.join(os.path.dirname(__file__), 'hunter_config.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                return cfg.get('nichos', NICHOS_DEFAULT), cfg.get('cidades', CIDADES_DEFAULT)
        except: pass
    return NICHOS_DEFAULT, CIDADES_DEFAULT

NICHOS, CIDADES = load_hunter_config()
ALLOWED_TYPE_FOCUS = {'b2b', 'b2c', 'misto'}

def resolve_type_focus():
    requested = str(os.getenv('HARVEST_TYPE_FOCUS', 'b2b')).strip().lower()
    return requested if requested in ALLOWED_TYPE_FOCUS else 'b2b'

def run_harvest():
    if not env_bool("ENABLE_HARVEST", False):
        print("[Harvest] 🚫 Colheita desativada por configuração (ENABLE_HARVEST=false).")
        return

    # 🕵️‍♂️ Divisão de Trabalho (Para 5 pessoas rodarem sem colisão)
    worker_id = 1
    if len(sys.argv) > 1:
        try:
            worker_id = int(sys.argv[1])
        except: pass


    print("[+] INICIANDO MOTOR DE COLHEITA CONTÍNUA (worker {})".format(worker_id))
    print("----------------------------------------------------------------")
    print("- Modo: Anti-Bloqueio\n")

    loop_count = 0
    max_cycles = env_int("HARVEST_MAX_CYCLES", 0)
    max_runtime_min = env_int("HARVEST_MAX_RUNTIME_MIN", 0)
    started_at = time.time()
    while not _SHUTDOWN:
        # 🛑 Verifica o sinal antes de cada ciclo
        # 🔄 RECARGA DE CONFIGURAÇÃO (Sincronia com o Dashboard)
        NEW_NICHOS, NEW_CIDADES = load_hunter_config()
        # Se os alvos mudaram, atualizamos a lista de trabalho do worker
        NICHOS, CIDADES = NEW_NICHOS, NEW_CIDADES
        use_all_nichos = env_bool("HARVEST_SINGLE_WORKER_ALL", True) and worker_id == 1
        if use_all_nichos:
            meus_nichos = list(NICHOS)
        else:
            step = max(1, env_int("HARVEST_NICHO_CHUNK", 6))
            start_idx = (worker_id - 1) * step
            meus_nichos = NICHOS[start_idx : start_idx + step] if start_idx < len(NICHOS) else NICHOS[:step]

        loop_count += 1
        print(f"\n=== CICLO #{loop_count} (Worker {worker_id}) ===\n")

        if max_cycles and loop_count > max_cycles:
            print(f"[Harvest-{worker_id}] ✅ Limite de ciclos atingido ({max_cycles}). Encerrando.")
            break
        if max_runtime_min and (time.time() - started_at) > (max_runtime_min * 60):
            print(f"[Harvest-{worker_id}] ✅ Tempo máximo atingido ({max_runtime_min} min). Encerrando.")
            break
        
        random.shuffle(meus_nichos)
        random.shuffle(CIDADES)

        for nicho in meus_nichos:
            if _SHUTDOWN: break
            for cidade in CIDADES:
                if _SHUTDOWN:
                    print(f"[Harvest-{worker_id}] 🛑 Encerrando loop interno...")
                    break
                
                print(f"\n[Harvest-{worker_id}] 🔍 Buscando: {nicho} em {cidade}...")
                
                try:
                    current_type_focus = resolve_type_focus()
                    import json
                    from core.db_manager import get_db_connection

                    # ── Callback ao vivo: dispara assim que o scraper captura cada lead ──
                    def _on_lead_live(l, _nicho=nicho, _cidade=cidade, _type_focus=current_type_focus):
                        if not isinstance(l, dict):
                            return
                        l['city'] = _cidade
                        l['nicho'] = _nicho
                        # Imprime imediatamente para o painel ao vivo
                        print(f"__LEAD_DATA__{json.dumps(l)}", flush=True)
                        # Salva no banco em tempo real
                        try:
                            c_name  = l.get('name') or l.get('company_name') or 'Empresa Geral'
                            c_phone = l.get('phone', 'N/A')
                            if c_phone == 'Ver na Web':
                                c_phone = 'N/A'
                            c_rating = l.get('rating') or l.get('clienteiro_score') or 0
                            c_score  = int(c_rating * 20) if 0 < c_rating <= 5 else int(c_rating)
                            conn_rt = get_db_connection()
                            with conn_rt.cursor() as cur:
                                cur.execute('''
                                    SELECT id FROM internal_leads
                                    WHERE phone = %s AND nicho = %s AND city = %s AND company_name = %s
                                    LIMIT 1
                                ''', (c_phone, _nicho, _cidade, c_name))
                                if not cur.fetchone():
                                    cur.execute('''
                                        INSERT INTO internal_leads
                                        (user_name, company_name, nicho, city, phone, type_focus, consent, clienteiro_score, printed, gestor_id)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    ''', ('Motor Autônomo', c_name, _nicho, _cidade, c_phone, _type_focus, 1, c_score, 0, 1))
                            conn_rt.commit()
                            conn_rt.close()
                        except Exception as dbe:
                            print(f"[Harvest-{worker_id}] ⚠️ Erro ao salvar lead ao vivo: {dbe}", flush=True)

                    proc = BusinessProcessor({
                        'nicho': nicho,
                        'city': cidade,
                        'type_focus': current_type_focus,
                        '_on_lead': _on_lead_live,
                        '_should_stop': lambda: _SHUTDOWN,
                    })
                    leads = proc._fetch_strategic_leads()

                    # Leads que não vieram pelo callback (fallback do banco/cache) — salva os que faltam
                    try:
                        conn_leads = get_db_connection()
                        with conn_leads.cursor() as cur:
                            for l in leads:
                                if isinstance(l, dict):
                                    l['city'] = cidade
                                    l['nicho'] = nicho
                                    c_name  = l.get('name') or l.get('company_name') or 'Empresa Geral'
                                    c_phone = l.get('phone', 'N/A')
                                    if c_phone == 'Ver na Web':
                                        c_phone = 'N/A'
                                    c_rating = l.get('rating') or l.get('clienteiro_score') or 0
                                    c_score  = int(c_rating * 20) if 0 < c_rating <= 5 else int(c_rating)
                                    cur.execute('''
                                        SELECT id FROM internal_leads
                                        WHERE phone = %s AND nicho = %s AND city = %s AND company_name = %s
                                        LIMIT 1
                                    ''', (c_phone, nicho, cidade, c_name))
                                    if not cur.fetchone():
                                        cur.execute('''
                                            INSERT INTO internal_leads
                                            (user_name, company_name, nicho, city, phone, type_focus, consent, clienteiro_score, printed, gestor_id)
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        ''', ('Motor Autônomo', c_name, nicho, cidade, c_phone, current_type_focus, 1, c_score, 0, 1))
                        conn_leads.commit()
                        conn_leads.close()
                    except Exception as dbe:
                        print(f"[Harvest-{worker_id}] ⚠️ Erro ao salvar fallback no CRM: {dbe}")
                    print(f"[Harvest-{worker_id}] ✅ Sucesso! {len(leads)} leads processados/armazenados.")
                except Exception as e:
                    print(f"[Harvest-{worker_id}] ⚠️ Erro isolado: {e}")

                next_pause = random.randint(3, 6) # Abaixado para ~5s conforme solicitação
                print(f"[Harvest-{worker_id}] ⏳ Resfriando IP por {next_pause}s...")
                time.sleep(next_pause)

if __name__ == "__main__":
    try:
        run_harvest()
    except KeyboardInterrupt:
        print("\n🛑 Colheita interrompida pelo usuário.")

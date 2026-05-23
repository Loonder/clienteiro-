import sqlite3
from collections import Counter
from datetime import datetime, timedelta

def get_dashboard_kpis(conn):
    """
    Calcula KPIs, métricas e distribuições para o Dashboard de Produção.
    Retorna um dicionário com estatísticas agregadas.
    """
    stats = {
        'total_leads': 0,
        'taxa_conversao': 0,
        'leads_por_nicho': {},
        'leads_por_cidade': {},
        'score_medio': 0,
        'leads_hoje': 0,
        'leads_grafico': { 'labels': [], 'values': [] }
    }

    try:
        with conn.cursor() as cur:
            # 1. Totais básicos
            cur.execute('SELECT COUNT(*) FROM internal_leads')
            total = cur.fetchone()['count']
            cur.execute('SELECT COUNT(*) FROM internal_leads WHERE printed = 1')
            printed = cur.fetchone()['count']
            
            stats['total_leads'] = total
            stats['leads_aguardando'] = total - printed
            stats['taxa_conversao'] = round((printed / total * 100), 1) if total > 0 else 0

            # 2. Score Médio
            cur.execute('SELECT AVG(clienteiro_score) FROM internal_leads')
            score_avg = cur.fetchone()['avg']
            stats['score_medio'] = round(float(score_avg or 0), 1)

            # 3. Leads de Hoje
            hoje_iso = datetime.now().strftime('%Y-%m-%d')
            cur.execute(
                "SELECT COUNT(*) FROM internal_leads WHERE timestamp::text LIKE %s", (f'{hoje_iso}%',)
            )
            leads_hoje = cur.fetchone()['count']
            stats['leads_hoje'] = leads_hoje

            # 4. Agrupamento por Nicho (Top 5)
            cur.execute(
                'SELECT nicho, COUNT(*) as qtd FROM internal_leads GROUP BY nicho ORDER BY qtd DESC LIMIT 5'
            )
            nicho_rows = cur.fetchall()
            stats['leads_por_nicho'] = { row['nicho']: row['qtd'] for row in nicho_rows }

            # 5. Agrupamento por Cidade (Top 5)
            cur.execute(
                'SELECT city, COUNT(*) as qtd FROM internal_leads GROUP BY city ORDER BY qtd DESC LIMIT 5'
            )
            cidade_rows = cur.fetchall()
            stats['leads_por_cidade'] = { row['city']: row['qtd'] for row in cidade_rows }
            stats['leads_por_cidade_labels'] = list(stats['leads_por_cidade'].keys())
            stats['leads_por_cidade_values'] = list(stats['leads_por_cidade'].values())

            # 6. Histórico de 7 dias (Para Gráfico de Linha)
            leads_grafico = { 'labels': [], 'values': [] }
            for i in range(6, -1, -1):
                dia = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                cur.execute(
                    "SELECT COUNT(*) FROM internal_leads WHERE timestamp::text LIKE %s", (f'{dia}%',)
                )
                qtd = cur.fetchone()['count']
                # Formata label para exibição: ex "16/03"
                label = (datetime.now() - timedelta(days=i)).strftime('%d/%m')
                leads_grafico['labels'].append(label)
                leads_grafico['values'].append(qtd)

            stats['leads_grafico'] = leads_grafico

    except Exception as e:
        print(f"[Analytics] Erro ao gerar estatísticas: {e}")
        stats['error'] = str(e)

    return stats

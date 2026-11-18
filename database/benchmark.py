"""Reproducible, isolated PostgreSQL query experiment."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import time
import psycopg
from portable import DATA


def run(rows=100000, repeats=7):
    params = dict(host='127.0.0.1', port=os.environ['PK_DB_PORT'], user=os.environ['PK_DB_USER'],
                  password=os.environ['PK_DB_PASSWORD'], dbname=os.environ['PK_DB_NAME'])
    out = DATA / 'benchmarks' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True, exist_ok=True)
    # TEMP tables belong to this connection and cannot modify the admissions dataset.
    with psycopg.connect(**params, autocommit=True) as conn:
        conn.execute('CREATE TEMP TABLE bench_application(id bigint, offer_id bigint, status text, submitted_at timestamptz, score numeric(8,2), payload jsonb)')
        conn.execute('''INSERT INTO bench_application
          SELECT n,1+(n%%200),CASE WHEN n%%7=0 THEN 'verified' ELSE 'draft' END,
                 timestamptz '2027-06-01 00:00:00+00' + n * interval '1 second',
                 (n%%100001)::numeric/100,jsonb_build_object('diploma',CASE WHEN n%%53=0 THEN 'engineer' ELSE 'other' END)
          FROM generate_series(1,%s) n''', [rows])
        conn.execute('ANALYZE bench_application')
        sql_query = "SELECT id,submitted_at,score FROM bench_application WHERE offer_id=42 AND status='verified' ORDER BY submitted_at,id LIMIT 50"
        evidence = {'date_utc': datetime.now(timezone.utc).isoformat(), 'rows': rows, 'repeats': repeats,
                    'os': platform.platform(), 'python': platform.python_version(), 'cpu': platform.processor(),
                    'postgres': conn.execute('SELECT version()').fetchone()[0], 'query': sql_query,
                    'dataset': 'Deterministic synthetic temporary relation; no candidate data. Warm cache, one connection, no competing workload.',
                    'settings': dict(conn.execute("SELECT name,setting FROM pg_settings WHERE name IN ('shared_buffers','work_mem','effective_cache_size','random_page_cost','max_parallel_workers_per_gather')").fetchall())}
        checksums = []
        for phase in ['before', 'after']:
            if phase == 'after':
                begin = time.perf_counter()
                conn.execute("CREATE INDEX bench_verified_cover ON bench_application(offer_id,submitted_at,id) INCLUDE(score) WHERE status='verified'")
                evidence['index_build_ms'] = (time.perf_counter() - begin) * 1000
                conn.execute('VACUUM ANALYZE bench_application')
                evidence['index_bytes'] = conn.execute("SELECT pg_relation_size('bench_verified_cover')").fetchone()[0]
            result = conn.execute(sql_query).fetchall()
            checksums.append(hashlib.sha256(repr(result).encode()).hexdigest())
            plans = [conn.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + sql_query).fetchone()[0][0] for _ in range(repeats)]
            times = [p['Execution Time'] for p in plans]
            evidence[phase] = {'median_ms': statistics.median(times), 'min_ms': min(times), 'max_ms': max(times),
                               'execution_ms': times, 'planning_ms': [p['Planning Time'] for p in plans],
                               'plan': plans[len(plans)//2], 'result_rows': len(result), 'result_sha256': checksums[-1]}
            (out / f'{phase}-plans.json').write_text(json.dumps(plans, indent=2), encoding='utf-8')
        if checksums[0] != checksums[1]:
            raise AssertionError('Optimization changed query results.')
        evidence['speedup_median'] = evidence['before']['median_ms'] / max(evidence['after']['median_ms'], .0001)
        # Measure the write cost on equivalent fresh TEMP relations, with / without the index.
        write_cost = {}
        for indexed in [False, True]:
            table = 'bench_write_indexed' if indexed else 'bench_write_plain'
            conn.execute(f'CREATE TEMP TABLE {table} (LIKE bench_application)')
            if indexed:
                conn.execute(f"CREATE INDEX ON {table}(offer_id,submitted_at,id) INCLUDE(score) WHERE status='verified'")
            timings = []
            for _ in range(repeats):
                conn.execute(f'TRUNCATE {table}')
                plan = conn.execute(f'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) INSERT INTO {table} SELECT * FROM bench_application LIMIT 10000').fetchone()[0][0]
                timings.append(plan['Execution Time'])
            write_cost['indexed' if indexed else 'plain'] = {'median_ms': statistics.median(timings), 'runs_ms': timings}
        evidence['insert_10000'] = write_cost
    (out / 'summary.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding='utf-8')
    summary = (f"# Pomiar PostgreSQL — {evidence['date_utc']}\n\n"
        f"Relacja tymczasowa: {rows:,} deterministycznych rekordów, {repeats} powtórzeń, rozgrzana pamięć podręczna.\n\n"
        f"| Wariant | Mediana wykonania |\n|---|---:|\n"
        f"| Bez indeksu | {evidence['before']['median_ms']:.3f} ms |\n"
        f"| Indeks częściowy z INCLUDE | {evidence['after']['median_ms']:.3f} ms |\n\n"
        f"Względna zmiana mediany: {evidence['speedup_median']:.2f}×. Zgodność wyniku: identyczne SHA-256. "
        f"Rozmiar indeksu: {evidence['index_bytes']} B; budowa: {evidence['index_build_ms']:.3f} ms.\n\n"
        f"Wstawienie 10 000 rekordów: bez indeksu {write_cost['plain']['median_ms']:.3f} ms, "
        f"z indeksem {write_cost['indexed']['median_ms']:.3f} ms.\n\n"
        "To pomiar silnika SQL na izolowanej relacji reprezentującej kolejkę zgłoszeń. Nie jest pomiarem całego API, "
        "sieci, interfejsu ani obciążenia 50 użytkowników. Nie wyłączano wymuszaniem skanowania sekwencyjnego. "
        "Pełne plany, bufory, czasy planowania i konfiguracja są w plikach JSON.\n")
    (out / 'wynik.md').write_text(summary, encoding='utf-8')
    return str(out)

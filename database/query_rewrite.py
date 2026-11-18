"""SQL-only optimization on a scaled copy of this project's actual relations."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import os
import platform
import statistics
import psycopg
from psycopg import sql
from portable import DATA

BEFORE="""SELECT o.id, o.program_id,
 (SELECT count(*) FROM bench_application a WHERE a.offer_id=o.id AND a.status='verified') AS verified,
 (SELECT count(*) FROM bench_application a WHERE a.offer_id=o.id AND a.status='confirmed') AS confirmed
FROM bench_offer o ORDER BY o.id"""
AFTER="""SELECT o.id, o.program_id, COALESCE(a.verified,0) AS verified, COALESCE(a.confirmed,0) AS confirmed
FROM bench_offer o
LEFT JOIN (
 SELECT offer_id, count(*) FILTER (WHERE status='verified') AS verified,
                  count(*) FILTER (WHERE status='confirmed') AS confirmed
 FROM bench_application GROUP BY offer_id
) a ON a.offer_id=o.id ORDER BY o.id"""


def run(rows=100000,repeats=7):
    out=DATA/'benchmarks'/('sql-rewrite-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
    out.mkdir(parents=True,exist_ok=True)
    with psycopg.connect(host='127.0.0.1',port=os.environ['PK_DB_PORT'],user=os.environ['PK_DB_USER'],password=os.environ['PK_DB_PASSWORD'],dbname=os.environ['PK_DB_NAME'],autocommit=True) as conn:
        # Actual project column definitions; data amplification is isolated from the application.
        conn.execute('CREATE TEMP TABLE bench_application (LIKE admissions_application)')
        conn.execute('CREATE TEMP TABLE bench_offer AS SELECT * FROM admissions_offer WHERE campaign_id=(SELECT id FROM admissions_campaign ORDER BY start,id LIMIT 1)')
        columns=[r[0] for r in conn.execute("SELECT attname FROM pg_attribute WHERE attrelid='admissions_application'::regclass AND attnum>0 AND NOT attisdropped ORDER BY attnum")]
        expressions={'id':sql.SQL('g.n'),'offer_id':sql.SQL('o.id'),
            'status':sql.SQL("CASE WHEN g.n%%3=0 THEN 'verified' WHEN g.n%%7=0 THEN 'confirmed' ELSE 'draft' END")}
        select=sql.SQL(',').join(expressions.get(name,sql.Identifier('a',name)) for name in columns)
        conn.execute(sql.SQL('''INSERT INTO bench_application SELECT {} FROM generate_series(1,%s) g(n)
          JOIN (SELECT id,row_number() OVER (ORDER BY id) AS rn FROM bench_offer) o
          ON o.rn=1+(g.n-1)%%(SELECT count(*) FROM bench_offer)
          CROSS JOIN (SELECT * FROM admissions_application ORDER BY id LIMIT 1) a''').format(select),[rows])
        conn.execute('ANALYZE bench_application'); conn.execute('ANALYZE bench_offer')
        evidence={'rows':rows,'repeats':repeats,'os':platform.platform(),'cpu':platform.processor(),
            'postgres':conn.execute('SELECT version()').fetchone()[0],
            'scope':'Temporary copies of admissions_application and admissions_offer; no indexes changed; only SELECT rewritten; warm cache, one connection.'}
        for phase,query in [('before',BEFORE),('after',AFTER)]:
            data=conn.execute(query).fetchall()
            conn.execute(query).fetchall() # warmup excluded
            plans=[conn.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+query).fetchone()[0][0] for _ in range(repeats)]
            evidence[phase]={'query':query,'result_sha256':hashlib.sha256(repr(data).encode()).hexdigest(),'result_rows':len(data),
                'execution_ms':[p['Execution Time'] for p in plans],'median_ms':statistics.median(p['Execution Time'] for p in plans),
                'total_cost':plans[0]['Plan']['Total Cost'],'plans':plans}
            (out/(phase+'.sql')).write_text(query+';\n','utf-8')
            (out/(phase+'-explain.txt')).write_text('\n'.join(r[0] for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) '+query)),'utf-8')
        assert evidence['before']['result_sha256']==evidence['after']['result_sha256']
    before,after=evidence['before'],evidence['after']
    evidence['time_reduction_percent']=100*(1-after['median_ms']/before['median_ms'])
    evidence['cost_reduction_percent']=100*(1-after['total_cost']/before['total_cost'])
    (out/'summary.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False),'utf-8')
    (out/'wynik.md').write_text(f"# Zmiana wyłącznie zapytania SQL\n\n100 000 rekordów syntetycznych w kopii relacji projektu. Te same tabele, dane i indeksy w obu wariantach.\n\n| Wariant | Mediana wykonania | Koszt planu |\n|---|---:|---:|\n| Podzapytania skorelowane | {before['median_ms']:.3f} ms | {before['total_cost']} |\n| Agregacja i LEFT JOIN | {after['median_ms']:.3f} ms | {after['total_cost']} |\n\nCzas mniejszy o {evidence['time_reduction_percent']:.2f}%, koszt szacowany mniejszy o {evidence['cost_reduction_percent']:.2f}%. Koszt planera nie jest czasem w milisekundach.\n\nWyniki są identyczne (SHA-256); zachowano także oferty bez zgłoszeń dzięki LEFT JOIN i COALESCE. Siedem pomiarów po rozgrzewce, jeden klient, bez zmian struktury programu. Relacje tymczasowe nie zawierają nowego obciążenia w działającej aplikacji. Nie jest to dowód spełnienia N07 ani porównanie wszystkich możliwych rozkładów danych.\n",'utf-8')
    return str(out)


if __name__=='__main__':
    from portable import environment
    environment(owner=True)
    print(run())

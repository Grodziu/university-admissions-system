"""Private PostgreSQL cluster; no installer, system service or administrator rights."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
HOME = Path(sys.executable).parent if getattr(sys, 'frozen', False) else ROOT
DATA = Path(os.environ.get('PK_DATA_DIR', HOME / 'runtime')).resolve()
# Keep PostgreSQL's native libraries outside PyInstaller's DLL directory.
# Its ICU libraries have the same names as Windows ICU used by Qt, but a different ABI.
PG = HOME / 'vendor' / 'pgsql' / 'bin'
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def command(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, capture_output=True,
                          encoding='utf-8', errors='replace', creationflags=HIDDEN, timeout=90, **kwargs)


def free_port(preferred, bind='127.0.0.1'):
    with socket.socket() as s:
        try:
            s.bind((bind, preferred))
        except OSError:
            s.bind((bind, 0))
        return s.getsockname()[1]


def report_bound_port(path, port):
    if path is not None:
        pending = path.with_suffix('.tmp')
        pending.write_text(str(port), encoding='ascii')
        pending.replace(path)


def config():
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / 'local.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    value = {'db_port': free_port(55432), 'owner_password': secrets.token_urlsafe(32),
             'app_password': secrets.token_urlsafe(32), 'secret': secrets.token_urlsafe(64),
             'demo_password': secrets.token_urlsafe(12)}
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')
    return value


def environment(owner=False):
    cfg = config()
    os.environ.update(PK_DATA_DIR=str(DATA), PK_SECRET_KEY=cfg['secret'],
                      PK_DB_PORT=str(cfg['db_port']), PK_DB_NAME=cfg.get('active_database', 'rekrutacja'),
                      PK_DOCUMENTS_PATH=cfg.get('documents_path', str(DATA / 'documents')),
                      PK_DB_USER='pk_owner' if owner else 'pk_app',
                      PK_DB_PASSWORD=cfg['owner_password'] if owner else cfg['app_password'],
                      DJANGO_SETTINGS_MODULE='server.settings')
    return cfg


def start_database():
    import psycopg
    from psycopg import sql
    cfg = config()
    if not (PG / 'pg_ctl.exe').exists():
        raise RuntimeError('Brak przenośnego PostgreSQL w vendor/pgsql. Uruchom przygotowanie pakietu.')
    cluster = DATA / 'postgres'
    if not (cluster / 'PG_VERSION').exists():
        pwfile = DATA / '.init-password'
        pwfile.write_text(cfg['owner_password'], encoding='utf-8')
        try:
            command([PG / 'initdb.exe', '-D', cluster, '-U', 'pk_owner', '--encoding=UTF8',
                     '--locale=C', '--auth=scram-sha-256', f'--pwfile={pwfile}'])
        finally:
            pwfile.unlink(missing_ok=True)
        with (cluster / 'postgresql.conf').open('a', encoding='utf-8') as f:
            f.write(f"\nlisten_addresses = '127.0.0.1'\nport = {cfg['db_port']}\nmax_connections = 40\nshared_buffers = '64MB'\n")
    status = subprocess.run([str(PG / 'pg_ctl.exe'), '-D', str(cluster), 'status'],
                            capture_output=True, creationflags=HIDDEN)
    if status.returncode:
        # A daemon must not inherit a captured pipe: communicate() would wait for its EOF forever.
        with (DATA / 'postgres-start.log').open('a', encoding='utf-8') as log:
            subprocess.run([str(PG / 'pg_ctl.exe'), '-D', str(cluster), '-l', str(DATA / 'postgres.log'),
                            '-w', '-t', '45', 'start'], stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                            creationflags=HIDDEN, check=True, timeout=60)
    conn = psycopg.connect(host='127.0.0.1', port=cfg['db_port'], user='pk_owner',
                           password=cfg['owner_password'], dbname='postgres', autocommit=True, connect_timeout=5)
    with conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='pk_app'").fetchone():
            conn.execute(sql.SQL('CREATE ROLE pk_app LOGIN PASSWORD {}').format(sql.Literal(cfg['app_password'])))
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname='rekrutacja'").fetchone():
            conn.execute('CREATE DATABASE rekrutacja OWNER pk_owner')
    return cfg


def stop_database():
    if (DATA / 'postgres' / 'PG_VERSION').exists():
        command([PG / 'pg_ctl.exe', '-D', DATA / 'postgres', '-w', '-t', '30', '-m', 'fast', 'stop'])


def initialize():
    cfg = start_database()
    environment(owner=True)
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connection
    call_command('migrate', interactive=False, verbosity=0)
    call_command('seed_demo', password=cfg['demo_password'], verbosity=0)
    with connection.cursor() as cursor:
        from psycopg import sql
        cursor.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO pk_app').format(sql.Identifier(os.environ['PK_DB_NAME'])))
        cursor.execute('GRANT USAGE ON SCHEMA public TO pk_app;'
                       'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pk_app;'
                       'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pk_app;'
                       'REVOKE UPDATE, DELETE, TRUNCATE ON admissions_auditevent, admissions_publication, admissions_rankingentry FROM pk_app;')
        # Raw SQL audit tables are owned by the migration role and written through SECURITY DEFINER triggers.
        cursor.execute("SELECT to_regclass('public.pk_row_audit')")
        if cursor.fetchone()[0]:
            cursor.execute('REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON pk_row_audit, pk_statement_audit, pk_offer_stats FROM pk_app;')
        # Contact writes go through the view; its trigger keeps the optional 6NF facts consistent.
        cursor.execute('REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON admissions_contactanchor, '
                       'admissions_candidatephone, admissions_candidateportfolio, '
                       'admissions_candidatenotificationaddress FROM pk_app;')
    connection.close()
    return cfg

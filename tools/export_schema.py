"""Export the actual PostgreSQL DDL, without rows, credentials or role grants."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from portable import DATA, PG, HIDDEN, config, start_database, stop_database

cfg = config()
running = subprocess.run([str(PG / 'pg_ctl.exe'), '-D', str(DATA / 'postgres'), 'status'],
                         capture_output=True, creationflags=HIDDEN).returncode == 0
try:
    start_database()
    target = ROOT / 'database' / 'schema.sql'
    subprocess.run([str(PG / 'pg_dump.exe'), '-h', '127.0.0.1', '-p', str(cfg['db_port']),
                    '-U', 'pk_owner', '-d', cfg.get('active_database', 'rekrutacja'),
                    '--schema-only', '--no-owner', '--no-acl', '-f', str(target)],
                   env=dict(os.environ, PGPASSWORD=cfg['owner_password']),
                   capture_output=True, check=True, creationflags=HIDDEN, timeout=60)
    print('DDL bez danych:', target)
finally:
    if not running:
        stop_database()

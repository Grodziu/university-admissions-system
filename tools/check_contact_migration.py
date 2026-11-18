"""Check migration and regression in an isolated PostgreSQL instance."""
from pathlib import Path
import os
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('PK_DATA_DIR', str(Path(__file__).resolve().parents[1] / 'tmp' / f'contact-check-{time.time_ns()}'))
from portable import initialize, stop_database
try:
    initialize()
    from django.core.management import call_command
    call_command('makemigrations', 'admissions', check=True, dry_run=True)
    call_command('test', 'admissions.test_contact_facts', 'admissions.test_mailing', interactive=False, verbosity=2)
finally:
    stop_database()

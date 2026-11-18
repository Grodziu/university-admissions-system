"""Consistent backup; restore into a NEW database and switch the local profile."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile
import psycopg
from psycopg import sql
from portable import DATA, PG, HIDDEN, config


def make_backup():
    from django.conf import settings
    from django.db import transaction
    from admissions.models import Campaign, Application, Document, HousingApplication, ProfileDocument, Publication, ProfilePhoto
    with transaction.atomic():
        list(Campaign.objects.select_for_update().order_by('id'))
        dest = DATA / 'backups'
        dest.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
        archive = dest / f'rekrutacja-{stamp}.zip'
        db = settings.DATABASES['default']
        env = os.environ.copy()
        env['PGPASSWORD'] = db['PASSWORD']
        with tempfile.TemporaryDirectory(prefix='pk-backup-', dir=DATA) as temp:
            dump = Path(temp) / 'database.dump'
            subprocess.run([str(PG / 'pg_dump.exe'), '-h', '127.0.0.1', '-p', str(db['PORT']),
                            '-U', db['USER'], '-d', db['NAME'], '-Fc', '--no-owner', '--no-acl', '-f', str(dump)],
                            env=env, check=True, capture_output=True, creationflags=HIDDEN, timeout=120)
            files = {'database.dump': dump}
            for records in (Document.objects.all(), ProfilePhoto.objects.all(), ProfileDocument.objects.all()):
                for doc in records.iterator():
                    files['documents/' + doc.file.name.replace('\\', '/')] = Path(doc.file.path)
            manifest = {'format': 1, 'created_at': stamp, 'postgres_major': '17',
                        'demo_password': config()['demo_password'],
                        'counts': {'applications': Application.objects.count(), 'documents': Document.objects.count(),
                                   'publications': Publication.objects.count(), 'photos': ProfilePhoto.objects.count(),
                                   'profile_documents': ProfileDocument.objects.count(), 'housing': HousingApplication.objects.count()},
                        'files': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}}
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
                for name, path in files.items():
                    z.write(path, name)
                z.writestr('manifest.json', json.dumps(manifest, indent=2))
        return archive


def restore_backup(path, activate=True):
    cfg = config()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    target = (DATA / 'restored' / stamp).resolve()
    target.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('format') != 1 or manifest.get('postgres_major') != '17':
            raise ValueError('Nieobsługiwany format kopii lub wersja PostgreSQL.')
        for name, checksum in manifest['files'].items():
            file = (target / name).resolve()
            if not file.is_relative_to(target) or name not in ['database.dump'] and not name.startswith('documents/'):
                raise ValueError('Niepoprawna ścieżka w archiwum.')
            if z.getinfo(name).file_size > 2 * 1024**3:
                raise ValueError('Zbyt duży plik w kopii.')
            content = z.read(name)
            if hashlib.sha256(content).hexdigest() != checksum:
                raise ValueError('Suma kontrolna kopii nie zgadza się: ' + name)
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(content)
    dbname = 'pk_restore_' + stamp
    credentials = dict(host='127.0.0.1', port=cfg['db_port'], user='pk_owner', password=cfg['owner_password'])
    with psycopg.connect(**credentials, dbname='postgres', autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {} OWNER pk_owner').format(sql.Identifier(dbname)))
    env = dict(os.environ, PGPASSWORD=cfg['owner_password'])
    subprocess.run([str(PG / 'pg_restore.exe'), '-h', '127.0.0.1', '-p', str(cfg['db_port']),
                    '-U', 'pk_owner', '-d', dbname, '--no-owner', '--no-acl', '--exit-on-error', str(target / 'database.dump')],
                    env=env, check=True, capture_output=True, creationflags=HIDDEN, timeout=180)
    with psycopg.connect(**credentials, dbname=dbname) as conn:
        tables = [('applications', 'application'), ('documents', 'document'), ('publications', 'publication')]
        if 'photos' in manifest['counts']:
            tables.append(('photos', 'profilephoto'))
        if 'profile_documents' in manifest['counts']:
            tables.append(('profile_documents','profiledocument'))
        if 'housing' in manifest['counts']:
            tables.append(('housing','housingapplication'))
        actual = {name: conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier('admissions_' + table))).fetchone()[0]
                  for name, table in tables}
        if actual != manifest['counts']:
            raise ValueError('Liczba rekordów po odtworzeniu nie zgadza się z manifestem.')
        # A delivery could have been sent between the snapshot and the recovery.
        if conn.execute("SELECT to_regclass('public.admissions_emaildelivery')").fetchone()[0]:
            conn.execute("UPDATE admissions_emaildelivery SET state='cancelled' WHERE state='pending'")
    if activate:
        cfg['active_database'] = dbname
        cfg['documents_path'] = str(target / 'documents')
        if manifest.get('demo_password'):
            cfg['demo_password'] = manifest['demo_password']
        (DATA / 'local.json').write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    return {'database': dbname, 'counts': actual, 'documents': str(target / 'documents'), 'activated': activate}

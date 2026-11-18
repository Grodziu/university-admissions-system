"""Exercise HTTP, SMTP, ranking and backup/restore with isolated demonstration data."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from email import policy
from email.parser import BytesParser
import json
import os
import math
import platform
from pathlib import Path
from queue import Queue
from socketserver import StreamRequestHandler, ThreadingTCPServer
import subprocess
import sys
from threading import Thread
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--executable', type=Path, help='Test the packaged EXE instead of the source entry point.')
parser.add_argument('--https', action='store_true', help='Use the public CA profile and exercise concurrent HTTPS clients.')
parser.add_argument('--capture-ui', action='store_true', help='Render Qt pages on the fresh demonstration data.')
args = parser.parse_args()
command = [str(args.executable.resolve())] if args.executable else [sys.executable, str(ROOT / 'start.py')]
sys.path.insert(0, str(ROOT))
from admissions.version import RELEASE, VERSION

release_slug = RELEASE.replace('.', '')
variant = 'exe' if args.executable else 'source'
TEST_DATA = ROOT / 'tmp' / f'e2e-{release_slug}-{variant}-{time.time_ns()}'
os.environ['PK_DATA_DIR'] = str(TEST_DATA)
from portable import HIDDEN, config, free_port, stop_database
from desktop.client import Client, ApiError
from admissions.identity import demo_pesel

TEST_DATA.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
port = free_port(58422)
base_url = f"{'https' if args.https else 'http'}://127.0.0.1:{port}/api"
trust = str(TEST_DATA / 'tls/ca.pem') if args.https else True
server_args = ['--https-server', str(port), '--bind', '127.0.0.1'] if args.https else ['--server', str(port)]
log = (TEST_DATA / 'server.log').open('w', encoding='utf-8')
server = None
mail_server = None
mail_thread = None
messages = Queue()
notification_address = 'e2e-notify@example.com'


class MailProbe(StreamRequestHandler):
    def handle(self):
        self.wfile.write(b'220 localhost test receiver\r\n')
        for line in self.rfile:
            command = line.split(maxsplit=1)[0].upper()
            if command == b'QUIT':
                self.wfile.write(b'221 bye\r\n')
                return
            if command == b'DATA':
                self.wfile.write(b'354 end with a single dot\r\n')
                data = bytearray()
                for message_line in self.rfile:
                    if message_line == b'.\r\n':
                        break
                    data.extend(message_line[1:] if message_line.startswith(b'..') else message_line)
                messages.put(BytesParser(policy=policy.default).parsebytes(bytes(data)))
            self.wfile.write(b'250 OK\r\n')


def start_server():
    return subprocess.Popen(command + server_args, env=env, stdout=log, stderr=log, creationflags=HIDDEN)


def wait_for_server(client):
    deadline = time.monotonic() + 50
    while True:
        try:
            health = client.request('/health')
            if health['ready']:
                assert health['version'] == VERSION
                return
        except (ApiError, OSError):
            if server.poll() is not None:
                raise RuntimeError(f'Server exited. Read {TEST_DATA / "server.log"}.')
        if time.monotonic() >= deadline:
            raise RuntimeError(f'Server not ready. Read {TEST_DATA / "server.log"}.')
        time.sleep(.25)


def capture_ui(stage='open', *, tokens=None):
    if args.capture_ui:
        subprocess.run([sys.executable, str(ROOT / 'tools/ui_smoke.py')],
                       env=dict(env, PK_TEST_API=base_url, PK_TEST_CA=str(trust) if args.https else '',
                                PK_TEST_SCREENSHOTS=str(ROOT / 'tmp' / f'screenshots-{release_slug}'),
                                PK_TEST_STAGE=stage, PK_TEST_TOKENS=json.dumps(tokens or {})),
                       stdout=log, stderr=log, check=True, creationflags=HIDDEN, timeout=100)


try:
    mail_server = ThreadingTCPServer(('127.0.0.1', 0), MailProbe)
    mail_server.daemon_threads = True
    mail_thread = Thread(target=mail_server.serve_forever, daemon=True)
    mail_thread.start()
    env.update(PK_SMTP_HOST='127.0.0.1', PK_SMTP_PORT=str(mail_server.server_address[1]),
               PK_SMTP_SECURITY='plain', PK_SMTP_FROM='rekrutacja@example.com',
               PK_SMTP_USER='', PK_SMTP_PASSWORD='')
    subprocess.run(command + ['--setup'], env=env, check=True,
                   stdout=log, stderr=log, creationflags=HIDDEN, timeout=240)
    server = start_server()
    client = Client(base_url, verify=trust)
    wait_for_server(client)
    if args.https:
        from networking import connection_profile
        connection_file = TEST_DATA / 'public-connection.json'
        connection_file.write_text(json.dumps(connection_profile('127.0.0.1', port)), 'utf-8')
        client_runtime = TEST_DATA / 'client-only'
        subprocess.run(command + ['--check-connection', str(connection_file)],
                       env=dict(env, PK_DATA_DIR=str(client_runtime)), stdout=log, stderr=log,
                       check=True, creationflags=HIDDEN, timeout=50)
        assert (client_runtime / 'client/connection.json').is_file()
        assert not (client_runtime / 'postgres').exists() and not (client_runtime / 'local.json').exists()
        try:
            Client(base_url).request('/health')
        except ApiError as error:
            assert 'tożsamości serwera' in str(error)
        else:
            raise AssertionError('HTTPS accepted without the project CA.')
    capture_ui()
    start = time.perf_counter()
    catalogs = client.request('/catalog')
    assert len(catalogs) == 58
    # N07: reproducible end-to-end local API criterion, one sequential client.
    for _ in range(5):
        client.request('/catalog')
    catalog_ms = []
    for _ in range(30):
        begin = time.perf_counter()
        assert len(client.request('/catalog')) == 58
        catalog_ms.append((time.perf_counter() - begin) * 1000)
    catalog_p95 = sorted(catalog_ms)[math.ceil(.95 * len(catalog_ms)) - 1]
    assert catalog_p95 <= 2000, f'N07 catalog p95 {catalog_p95:.1f} ms exceeded 2000 ms'
    api_performance = {'requirement': 'N07', 'path': '/api/catalog', 'offers': 58,
        'clients': 1, 'warmup': 5, 'samples': 30, 'runs_ms': catalog_ms,
        'p95_ms': catalog_p95, 'p95_method': 'nearest rank, ceil(0.95*N)', 'limit_ms': 2000,
        'scope': 'Loopback, client HTTP/TLS round trip and JSON decoding; GUI rendering excluded.',
        'os': platform.platform(), 'cpu': platform.processor(), 'python': platform.python_version()}
    assert len([o for o in catalogs if o['degree'] == 'PG']) == 8
    assert all(o['tuition_per_semester'] for o in catalogs if o['degree'] == 'PG' or o['mode'] == 'N')
    client.token = client.request('/login', {'email':'admin@demo.local','password':config()['demo_password']})['token']
    campaign_id = client.request('/workspace')['campaign']['id']
    api_performance['application_rows'] = len(client.request('/workspace')['applications'])
    client.request('/action', {'action':'demo_scenario','campaign_id':campaign_id,'scenario':'ready'})
    anna_housing = Client(base_url, verify=trust)
    anna_housing.token = anna_housing.request('/login', {'email': 'kandydat@demo.local', 'password': config()['demo_password']})['token']
    anna_housing.request('/action', {'action': 'housing_apply', 'campaign_id': campaign_id, 'preferred': 'DS2'})
    pending_housing = anna_housing.request('/workspace')['housing']
    assert pending_housing['request']['preferred'] == 'DS2' and pending_housing['request']['status'] == 'pending'
    assert pending_housing['capacity'] == 1800 and not pending_housing['published']
    client.token = ''
    candidate = client.request('/register', {'email': 'e2e@test.local', 'password': 'Candidate-e2e-456!',
        'first_name': 'Test', 'last_name': 'Odbiorczy', 'pesel': demo_pesel(190000), 'phone': '000000000',
        'notification_email': notification_address,
        'address': {'city': 'Kraków', 'street': 'Warszawska', 'building': '24', 'postal_code': '31-155'}})
    client.token = candidate['token']
    client.request('/action', {'action': 'profile', 'first_name': 'Test', 'last_name': 'Odbiorczy',
        'diploma': 'inżynier', 'average': '4.80',
        'exams': [{'subject': 'matematyka', 'level': 'basic', 'value': '100'}, {'subject': 'informatyka', 'level': 'extended', 'value': '100'}]})
    assert client.request('/workspace')['profile']['notification_email'] == notification_address
    offer = next(o for o in catalogs if o['name'] == 'Informatyka' and o['faculty'] == 'WIiM' and o['degree'] == 'I' and o['mode'] == 'S')
    app = client.request('/action', {'action': 'create_application', 'offer_id': offer['id']})
    photo = client.request('/profile/photo', {}, file=TEST_DATA/'demo-dokumenty/zdjecie-demo.png')
    assert client.request(photo['url'], binary=True).startswith(b'\x89PNG')
    education = client.request('/profile/document', {'kind': 'education'}, file=TEST_DATA / 'demo-dokumenty/swiadectwo.pdf')
    assert client.request(education['url'], binary=True).startswith(b'%PDF-')
    client.request(f"/upload/{app['id']}", {'kind': 'fee'}, file=TEST_DATA / 'demo-dokumenty/przelew-85zl.pdf')
    client.request('/action', {'action': 'submit', 'id': app['id']})
    assert client.request('/workspace')['applications'][0]['status'] == 'submitted'
    alternative = next(o for o in catalogs if o['program_id'] == offer['program_id'] and o['degree'] == 'I' and o['mode'] == 'N')
    alternate = client.request('/action', {'action': 'create_application', 'offer_id': alternative['id']})
    candidate_token = client.token
    client.token = ''
    client.token = client.request('/login', {'email': 'komisja@demo.local', 'password': config()['demo_password']})['token']
    reviewer_token = client.token
    review = {'action': 'review', 'id': app['id'], 'decision': 'verify', 'payment_matches': True,
              'photo_approved': True, 'expected_photo_id': photo['id'], 'feedback': 'Dokumenty poprawne.'}
    try:
        client.request('/action', dict(review, payment_amount='50'))
    except ApiError as error:
        assert 'wpisano inną kwotę' in str(error)
    else:
        raise AssertionError('The payment checkbox accepted a conflicting amount.')
    client.request('/action', review)
    client.token = candidate_token
    both = client.request('/workspace')['applications']
    assert {a['id'] for a in both} == {app['id'], alternate['id']}
    assert all(a['photo_approved'] and a['photo']['id'] == photo['id'] for a in both)
    assert not any(d['kind'] == 'photo' for a in both for d in a['documents'])
    submitted = next(a for a in both if a['id'] == app['id'])
    assert any(d['kind'] == 'education' and d['from_profile'] for d in submitted['documents'])
    assert not next(a for a in both if a['id'] == alternate['id'])['documents']
    client.token = ''
    client.token = client.request('/login', {'email': 'admin@demo.local', 'password': config()['demo_password']})['token']
    admin_token = client.token
    campaign = client.request('/workspace')['campaign']
    other_clients = []
    if args.https:
        demo_password = config()['demo_password']
        def demo_login(role):
            other = Client(base_url, verify=trust)
            other.token = other.request('/login', {'email': role + '@demo.local', 'password': demo_password})['token']
            return other
        with ThreadPoolExecutor(max_workers=12) as pool:
            other_clients = list(pool.map(demo_login, ['kandydat']*4 + ['komisja']*4 + ['admin']*4))
        assert len({other.token for other in other_clients}) == 12
        with ThreadPoolExecutor(max_workers=4) as pool:
            draft_ids = list(pool.map(lambda other: other.request('/action', {
                'action': 'create_application', 'offer_id': alternative['id']
            })['id'], other_clients[:4]))
        assert len(set(draft_ids)) == 1
        initial_revision = other_clients[0].request('/state')['revision']
    milestones = sorted({r[k] for r in campaign['rounds'] for k in ['application_end', 'end']})
    confirmed = False
    for index, moment in enumerate(milestones):
        client.request('/action', {'action': 'clock', 'campaign_id': campaign['id'], 'target': moment})
        if args.https and index == 0:
            with ThreadPoolExecutor(max_workers=12) as pool:
                states = list(pool.map(lambda other: other.request('/state'), other_clients))
            assert all(s['revision'] > initial_revision and s['now'] == moment for s in states)
            try:
                other_clients[0].request('/action', {'action': 'submit', 'id': draft_ids[0], 'expected_round': 1})
            except ApiError as error:
                assert 'zamknięte' in str(error)
            else:
                raise AssertionError('A form opened before the deadline allowed a stale submission.')
            with ThreadPoolExecutor(max_workers=4) as pool:
                publications = list(pool.map(lambda other: other.request('/action', {
                    'action': 'publish', 'offer_id': offer['id'], 'expected_round': 1
                }), other_clients[4:8]))
            assert len({publication['id'] for publication in publications}) == 1
            assert sum(publication['created'] for publication in publications) == 1
            assert len(client.request(f"/publications/{offer['id']}")) == 1
        state = client.request('/workspace')
        if state['campaign']['closed']:
            break
        for o in client.request('/catalog'):
            if o['publication_phase'] == 'ready':
                client.request('/action', {'action': 'publish', 'offer_id': o['id']})
        waiting=[a['id'] for a in client.request('/workspace')['applications'] if a['is_demo'] and a['status']=='qualified' and a['email']!='bezpotwierdzenia@demo.local']
        for start_at in range(0, len(waiting), 150):
            selected = waiting[start_at:start_at + 150]
            confirmed_demo=client.request('/action',{'action':'batch','operation':'confirm_demo','ids':selected})
            assert confirmed_demo['success']==len(selected)
        if not confirmed:
            client.token = candidate_token
            a = next(a for a in client.request('/workspace')['applications'] if a['id'] == app['id'])
            if a['status'] == 'qualified':
                assert a['result']['score'] == '800.00'
                client.request('/action', {'action': 'confirm', 'id': app['id']})
                confirmed = True
            client.token = admin_token
    assert confirmed
    final = next(r for r in client.request('/thresholds') if r['offer_id'] == offer['id'])
    assert final['state']=='launched'
    housing = anna_housing.request('/workspace')['housing']
    assert housing['published'] and housing['request']['status'] == 'awarded'
    assert housing['request']['allocated']['code'] in ('DS1', 'DS2', 'DS3', 'DS4')
    assert client.request('/workspace')['housing']['min_distance'] is not None
    capture_ui('closed', tokens={'kandydat': anna_housing.token, 'komisja': reviewer_token})
    client.token=candidate_token
    workspace = client.request('/workspace')
    assert next(a for a in workspace['applications'] if a['id'] == app['id'])['can_oath']
    assert workspace['unread_notifications'] > 0
    assert any(n['title'] == 'Opublikowano wyniki' for n in workspace['notifications'])
    message = messages.get(timeout=20)
    while 'Opublikowano wyniki' not in str(message['Subject']):
        message = messages.get(timeout=20)
    assert str(message['To']) == notification_address
    client.request('/action', {'action': 'read_notifications'})
    assert client.request('/workspace')['unread_notifications'] == 0
    client.request('/action',{'action':'oath','id':app['id'],'accepted':True})
    client.token=admin_token
    assert client.request('/history/' + str(app['id']))[0]['score'] == '800.00'
    archive = TEST_DATA / 'verified-backup.zip'
    archive.write_bytes(client.request('/backup', {}, binary=True))
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifest.json'))
    demo_password = config()['demo_password']
    assert manifest['demo_password'] == demo_password
    server.terminate()
    server.wait(timeout=10)
    server = None
    subprocess.run(command + ['--restore', str(archive)], env=env, check=True,
                   stdout=log, stderr=log, creationflags=HIDDEN, timeout=120)
    assert config()['active_database'].startswith('pk_restore_')
    assert config()['demo_password'] == demo_password
    subprocess.run(command + ['--setup'], env=env, check=True,
                   stdout=log, stderr=log, creationflags=HIDDEN, timeout=120)
    server = start_server()
    client.token = ''
    wait_for_server(client)
    client.token = client.request('/login', {'email': 'admin@demo.local', 'password': demo_password})['token']
    restored_apps = client.request('/workspace')['applications']
    assert len(restored_apps) == manifest['counts']['applications']
    restored_app = next(a for a in restored_apps if a['id'] == app['id'])
    for document in restored_app['documents']:
        blob=client.request('/document/' + str(document['id']), binary=True)
        assert blob.startswith(b'%PDF-')
    assert client.request(restored_app['photo']['url'], binary=True).startswith(b'\x89PNG')
    assert restored_app['sworn_at']
    assert restored_app['card_valid_from'] == '2027-10-01'
    assert restored_app['card_valid_until'] == '2028-03-31'
    assert client.request('/history/' + str(app['id']))[0]['score'] == '800.00'

    # Resume a manual progression after all unconfirmed places in I/1 expired.
    fresh = client.request('/action', {'action':'restart','campaign_id':campaign_id})['campaign_id']
    client.request('/action', {'action': 'demo_scenario', 'campaign_id': fresh, 'scenario': 'planning'})
    planning = client.request('/workspace')
    assert planning['can_create_offer'] and not planning['applications']
    configured = next(o for o in client.request('/catalog') if o['degree'] == 'I' and o['mode'] == 'N')
    assert configured['configurable']
    client.request('/action', {'action': 'configure_offer', 'offer_id': configured['id'],
                               'tuition': '3630.25', 'subjects': configured['subjects'], 'professions': configured['professions']})
    assert next(o for o in client.request('/catalog') if o['id'] == configured['id'])['tuition_per_semester'] == '3630.25'
    capture_ui('planning', tokens={'admin': client.token})
    client.request('/action', {'action':'demo_scenario','campaign_id':fresh,'scenario':'populate'})
    client.request('/action', {'action':'demo_scenario','campaign_id':fresh,'scenario':'ready'})
    first = next(r for r in client.request('/workspace')['campaign']['rounds'] if r['degree'] == 'I' and r['number'] == 1)
    client.request('/action', {'action':'clock','campaign_id':fresh,'target':first['application_end']})
    ready = [o for o in client.request('/catalog') if o['publication_phase'] == 'ready']
    published = client.request('/action', {'action':'batch','operation':'publish','ids':[o['id'] for o in ready]})
    assert ready and published['success'] == len(ready)
    client.request('/action', {'action':'clock','campaign_id':fresh,'target':first['end']})
    assert any(a['status'] == 'expired' and a['email'] == 'kandydat@demo.local' for a in client.request('/workspace')['applications'])
    final_demo = client.request('/action', {'action':'demo_scenario','campaign_id':fresh,'scenario':'final'})
    assert final_demo['launched'] == 58 and final_demo['anna_can_oath']
    anna_client = Client(base_url, verify=trust)
    anna_client.token = anna_client.request('/login', {'email':'kandydat@demo.local','password':demo_password})['token']
    anna = next(a for a in anna_client.request('/workspace')['applications'] if a['can_oath'])
    assert anna['name'] == 'Informatyka' and anna['status'] == 'confirmed' and anna['round'] == 2
    assert anna_client.request('/action', {'action':'oath','id':anna['id'],'accepted':True})['student_number']
    capture_ui('sworn', tokens={'kandydat': anna_client.token})
    result = {'result': 'PASS', 'offers': len(catalogs), 'application_id': app['id'],
              'api_performance_n07': api_performance,
              'runtime_variant': 'packaged-exe' if args.executable else 'python-source',
              'full_campaign': True, 'restored_counts': manifest['counts'],
              'restored_login_and_documents': True, 'restored_oath': True,
              'profile_photo_shared': True, 'conflicting_payment_blocked': True, 'new_edition_after_restore': True,
              'profile_evidence_copied_on_submit': True, 'planning_stage': True, 'housing_uses_launched_enrollment': True,
              'demo_launches_after_expired_round': final_demo['launched'], 'anna_oath_after_manual_progression': True,
              'result_received_via_smtp': True, 'unread_cleared': True, 'student_card_validity': True,
              'qt_views_checked': args.capture_ui,
              'elapsed_seconds': round(time.perf_counter() - start, 2)}
    if args.https:
        result.update(tls=True, private_ca_required=True, profile_import_without_postgresql=True,
                      simultaneous_https_clients=len(other_clients), shared_clock=True,
                      stale_submission_blocked=True, concurrent_publication_once=True,
                      network_scope='loopback on one Windows computer')
    filename = f'e2e-{release_slug}-{variant}-results.json'
    (ROOT / 'tmp' / filename).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
finally:
    if server:
        server.terminate()
        server.wait(timeout=10)
    if mail_server:
        mail_server.shutdown()
        mail_server.server_close()
        mail_thread.join()
    try:
        stop_database()
    except Exception:
        pass
    log.close()

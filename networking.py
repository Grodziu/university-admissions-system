"""LAN HTTPS pairing: clients receive only an address and a public CA certificate."""
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path
import socket
from urllib.parse import urlsplit
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from portable import DATA


def addresses():
    names = {'localhost', '127.0.0.1', socket.gethostname()}
    try:
        names.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return sorted(names)


def prepare_tls(hosts=None):
    hosts = sorted(set(hosts or addresses()))
    folder = DATA / 'tls'
    folder.mkdir(parents=True, exist_ok=True)
    ca_key_path, ca_path = folder / 'ca-key.pem', folder / 'ca.pem'
    now = datetime.now(timezone.utc)
    if ca_path.exists():
        ca = x509.load_pem_x509_certificate(ca_path.read_bytes())
        key = serialization.load_pem_private_key(ca_key_path.read_bytes(), None)
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        ca = None
    if ca is None or not any(isinstance(e.value, x509.SubjectKeyIdentifier) for e in ca.extensions):
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Rekrutacja PK — prywatny serwer projektu')])
        ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
              .not_valid_after(now + timedelta(days=3650))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
              .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False)
              .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True)
              .sign(key, hashes.SHA256()))
        ca_key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sans = []
    for host in hosts:
        try:
            sans.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            sans.append(x509.DNSName(host))
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, socket.gethostname())]))
            .issuer_name(ca.subject).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), True)
            .add_extension(x509.SubjectAlternativeName(sans), False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .sign(key, hashes.SHA256()))
    (folder / 'server.pem').write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    (folder / 'server-key.pem').write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return folder


def connection_profile(host, port):
    pem = (DATA / 'tls/ca.pem').read_text('ascii')
    cert = x509.load_pem_x509_certificate(pem.encode('ascii'))
    return {'format': 'rekrutacja-pk-connection-v1', 'url': f'https://{host}:{int(port)}',
            'server_name': socket.gethostname(), 'ca_pem': pem,
            'fingerprint': cert.fingerprint(hashes.SHA256()).hex()}


def import_profile(path):
    path = Path(path)
    if path.stat().st_size > 65536:
        raise ValueError('Plik połączenia jest zbyt duży.')
    value = json.loads(path.read_text('utf-8-sig'))
    if not isinstance(value, dict) or not all(isinstance(value.get(k), str) for k in ('url', 'ca_pem', 'fingerprint')):
        raise ValueError('Plik połączenia ma niekompletne dane.')
    url = urlsplit(value['url'])
    if (value.get('format') != 'rekrutacja-pk-connection-v1' or url.scheme != 'https' or not url.hostname
            or url.username or url.password or url.path not in ['', '/'] or url.query or url.fragment):
        raise ValueError('Niepoprawny plik połączenia HTTPS.')
    # Validate port and trust exactly the public certificate supplied by the host.
    port = url.port if url.port is not None else 443
    if not 1 <= port <= 65535:
        raise ValueError('Niepoprawny port serwera.')
    cert = x509.load_pem_x509_certificate(value['ca_pem'].encode('ascii'))
    constraints = next((ext.value for ext in cert.extensions if isinstance(ext.value, x509.BasicConstraints)), None)
    if constraints is None or not constraints.ca:
        raise ValueError('Plik nie zawiera certyfikatu urzędu serwera.')
    fingerprint = cert.fingerprint(hashes.SHA256()).hex()
    if value.get('fingerprint') != fingerprint:
        raise ValueError('Odcisk certyfikatu nie zgadza się z plikiem połączenia.')
    folder = DATA / 'client'
    folder.mkdir(parents=True, exist_ok=True)
    trust = folder / (fingerprint + '.pem')
    trust.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    value = {'format': value['format'], 'url': value['url'].rstrip('/'), 'ca_pem': value['ca_pem'],
             'fingerprint': fingerprint}
    saved = folder / 'connection.json'
    pending = folder / 'connection.json.tmp'
    pending.write_text(json.dumps(value, indent=2), 'utf-8')
    pending.replace(saved)
    return value['url'] + '/api', str(trust), value


def serve_https(port, bind='0.0.0.0', *, port_file=None):
    import os
    import ssl
    from portable import environment, report_bound_port
    from cheroot import wsgi
    from cheroot.ssl.builtin import BuiltinSSLAdapter
    hosts = addresses()
    folder = prepare_tls(hosts)
    os.environ['PK_SERVER_HOSTS'] = ','.join(hosts)
    environment()
    import django
    django.setup()
    from django.core.wsgi import get_wsgi_application
    from admissions.mailing import email_dispatcher
    server = wsgi.Server((bind, port), get_wsgi_application(), numthreads=12, request_queue_size=64, timeout=30)
    adapter = BuiltinSSLAdapter(str(folder/'server.pem'), str(folder/'server-key.pem'))
    adapter.context.minimum_version = ssl.TLSVersion.TLSv1_2
    server.ssl_adapter = adapter
    server.max_request_body_size = 12 * 1024 * 1024
    with email_dispatcher():
        try:
            try:
                server.prepare()
            except OSError:
                # Cheroot closes a failed listener and clears its socket. For the
                # GUI launcher, retry on a port assigned directly by the OS.
                if port_file is None or not port or server.socket is not None:
                    raise
                server.bind_addr = (bind, 0)
                server.prepare()
            report_bound_port(port_file, server.bind_addr[1])
            server.serve()
        finally:
            server.stop()

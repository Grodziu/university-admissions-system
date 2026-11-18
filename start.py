"""One entry point for source and the portable Windows application."""
import atexit
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import traceback
from portable import DATA, ROOT, HIDDEN, config, environment, initialize, report_bound_port, stop_database


def own_command(*args):
    return [sys.executable, *args] if getattr(sys, 'frozen', False) else [sys.executable, str(ROOT / 'start.py'), *args]


def main():
    port_file = Path(sys.argv[sys.argv.index('--port-file') + 1]) if '--port-file' in sys.argv else None
    if '--check-connection' in sys.argv:
        from networking import import_profile
        from desktop.client import Client
        url, trust, _ = import_profile(sys.argv[sys.argv.index('--check-connection') + 1])
        if not Client(url, verify=trust).request('/health')['ready']:
            raise RuntimeError('Serwer nie zakończył przygotowywania naboru.')
        return
    if '--https-server' in sys.argv:
        from networking import serve_https
        port = int(sys.argv[sys.argv.index('--https-server') + 1])
        bind = sys.argv[sys.argv.index('--bind') + 1] if '--bind' in sys.argv else '0.0.0.0'
        serve_https(port, bind, port_file=port_file)
        return
    if '--setup' in sys.argv:
        initialize()
        print('Środowisko i dane demonstracyjne są gotowe.')
        return
    if '--server' in sys.argv:
        environment()
        import django
        django.setup()
        from django.core.wsgi import get_wsgi_application
        from waitress import create_server
        from admissions.mailing import email_dispatcher
        port = int(sys.argv[sys.argv.index('--server') + 1])
        server = create_server(get_wsgi_application(), host='127.0.0.1', port=port, threads=6,
                               max_request_body_size=12 * 1024 * 1024)
        report_bound_port(port_file, server.effective_port)
        with email_dispatcher():
            server.run()
        return
    if '--test' in sys.argv:
        from portable import start_database
        start_database()
        environment(owner=True)
        import django
        django.setup()
        from django.core.management import call_command
        call_command('test', 'admissions', verbosity=2, interactive=False)
        return
    if '--export-model' in sys.argv:
        from PySide6.QtCore import QLockFile
        DATA.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(DATA / 'app.lock'))
        if not lock.tryLock(0):
            raise RuntimeError('Zamknij aplikację przed eksportem modelu tej instancji.')
        import os
        import psycopg
        from database.model_export import export
        output = DATA / 'models'
        try:
            initialize()
            with psycopg.connect(host='127.0.0.1', port=os.environ['PK_DB_PORT'], user=os.environ['PK_DB_USER'],
                 password=os.environ['PK_DB_PASSWORD'], dbname=os.environ['PK_DB_NAME']) as connection:
                print(export(connection, output))
            print(output)
        finally:
            stop_database()
            lock.unlock()
        return
    if any(flag in sys.argv for flag in ['--benchmark', '--benchmark-query', '--benchmark-denormalization']):
        from portable import start_database
        start_database()
        environment(owner=True)
        if '--benchmark-denormalization' in sys.argv:
            from database.denormalization import run
        elif '--benchmark-query' in sys.argv:
            from database.query_rewrite import run
        else:
            from database.benchmark import run
        print(run())
        return
    if '--restore' in sys.argv:
        from PySide6.QtCore import QLockFile
        DATA.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(DATA / 'app.lock'))
        if not lock.tryLock(0):
            raise RuntimeError('Zamknij aplikację przed odtworzeniem kopii.')
        from portable import start_database
        start_database()
        from backups import restore_backup
        try:
            result = restore_backup(sys.argv[sys.argv.index('--restore') + 1])
            print(result)
        finally:
            stop_database()
        return
    from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QMessageBox
    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtGui import QIcon
    from desktop.widgets import STYLE, label, chip, NAVY, MUTED
    from desktop.client import Client
    from desktop.app import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName('Rekrutacja PK')
    app.setOrganizationName('Rekrutacja PK')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    from desktop.launcher import choose_mode
    mode = {'mode': 'local'} if '--local' in sys.argv else {'mode': 'host'} if '--host' in sys.argv else choose_mode()
    if not mode:
        return
    if mode['mode'] == 'client':
        url, trust, profile = mode['profile']
        window = MainWindow(Client(url, verify=trust), connection_info={'mode': 'client', 'url': url, 'profile': profile})
        window.show()
        app.exec()
        return
    DATA.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(DATA / 'app.lock'))
    if not lock.tryLock(0):
        QMessageBox.information(None, 'Rekrutacja PK', 'Program jest już uruchomiony. Przejdź do istniejącego okna.')
        return
    cfg = config()
    loading = QDialog()
    loading.setWindowTitle('Rekrutacja PK')
    loading.setWindowIcon(QIcon(str(ROOT / 'assets' / 'pk.ico')))
    loading.setFixedSize(540, 240)
    layout = QVBoxLayout(loading)
    layout.setContentsMargins(36, 30, 36, 30)
    layout.addWidget(chip('POLITECHNIKA KRAKOWSKA'))
    layout.addWidget(label('Przygotowujemy Twój panel', 25, NAVY, True))
    status = label('Uruchamianie lokalnej bazy danych…', 14, MUTED)
    layout.addWidget(status)
    layout.addWidget(label('Pierwsze uruchomienie może potrwać chwilę.', 12, MUTED))
    loading.show()
    log = (DATA / 'application.log').open('a', encoding='utf-8')
    launch = TemporaryDirectory(prefix='launch-', dir=DATA)
    port_file = Path(launch.name) / 'port'
    process = subprocess.Popen(own_command('--setup'), stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=HIDDEN)
    hosted = mode['mode'] == 'host'
    server_command = ('--https-server', '58443') if hosted else ('--server', '0')
    if hosted:
        from networking import addresses
    trust = str(DATA / 'tls/ca.pem') if hosted else True
    state = {'phase': 'setup', 'process': process, 'started': time.monotonic(), 'window': None, 'port': None}
    def cleanup():
        p = state['process']
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        try:
            stop_database()
        except Exception:
            pass
        launch.cleanup()
        log.close()
        lock.unlock()
    atexit.register(cleanup)
    timer = QTimer()
    def poll():
        p = state['process']
        if time.monotonic() - state['started'] > 120:
            timer.stop()
            QMessageBox.critical(loading, 'Uruchamianie', 'Przekroczono czas uruchamiania. Szczegóły: ' + str(DATA / 'application.log'))
            app.quit()
            return
        if state['phase'] == 'setup':
            if p.poll() is None:
                return
            if p.returncode:
                timer.stop()
                QMessageBox.critical(loading, 'Uruchamianie', 'Nie udało się przygotować aplikacji. Szczegóły: ' + str(DATA / 'application.log'))
                app.quit()
                return
            status.setText('Łączenie z usługą rekrutacji…')
            state['process'] = subprocess.Popen(
                own_command(*server_command, '--port-file', str(port_file)), stdout=log, stderr=log,
                stdin=subprocess.DEVNULL, creationflags=HIDDEN,
            )
            state['phase'] = 'server'
        else:
            if p.poll() is not None:
                timer.stop()
                QMessageBox.critical(loading, 'Uruchamianie', 'Serwer zakończył pracę podczas uruchamiania. Szczegóły: ' + str(DATA / 'application.log'))
                app.quit()
                return
            if state['port'] is None:
                try:
                    state['port'] = int(port_file.read_text(encoding='ascii'))
                except FileNotFoundError:
                    return
            port = state['port']
            base_url = f"{'https' if hosted else 'http'}://127.0.0.1:{port}/api"
            try:
                import requests
                with requests.Session() as session:
                    session.trust_env = False
                    response = session.get(base_url + '/health', timeout=.25, verify=trust)
                if response.ok and response.json().get('ready'):
                    timer.stop()
                    info = {'mode': 'host' if hosted else 'local', 'port': port, 'addresses': addresses() if hosted else []}
                    window = MainWindow(Client(base_url, verify=trust), cfg['demo_password'], connection_info=info)
                    state['window'] = window
                    window.show()
                    loading.close()
            except (requests.RequestException, ValueError):
                pass
    timer.timeout.connect(poll)
    timer.start(250)
    app.exec()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        DATA.mkdir(parents=True, exist_ok=True)
        with (DATA / 'error.log').open('a', encoding='utf-8') as log:
            traceback.print_exc(file=log)
        if sys.stdout:
            traceback.print_exc()
        sys.exit(1)

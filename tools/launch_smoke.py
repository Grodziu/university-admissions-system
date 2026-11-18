"""Open the Qt launcher with PostgreSQL on the former preferred API port."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser()
parser.add_argument('--host', action='store_true', help='Exercise the team launcher on loopback.')
args = parser.parse_args()
mode = 'host' if args.host else 'local'
db_port = 58443 if args.host else 58421
runtime = ROOT / 'tmp' / f'launch-test-{mode}-{time.time_ns()}'
os.environ.update(PK_DATA_DIR=str(runtime), QT_QPA_PLATFORM='offscreen', PK_SMTP_HOST='')

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from admissions.version import RELEASE, VERSION
from desktop import app, launcher
from portable import config
import start

settings = config()
settings['db_port'] = db_port
(runtime / 'local.json').write_text(json.dumps(settings), encoding='utf-8')
results = {}
errors = []
choose = launcher.choose_mode
own_command = start.own_command


def choose_option():
    def click_mode():
        modal = QApplication.activeModalWidget()
        title = 'Uruchom serwer dla zespołu' if args.host else 'Na tym komputerze'
        next(button for button in modal.findChildren(QPushButton) if button.text() == title).click()

    QTimer.singleShot(0, click_mode)
    return choose()


def loopback_command(*options):
    if options[0] == '--https-server':
        options += ('--bind', '127.0.0.1')
    return own_command(*options)


class CheckedWindow(app.MainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QTimer.singleShot(0, self.check)

    def check(self):
        try:
            assert self.isVisible() and self.current == 'login'
            port = self.connection_info['port']
            assert self.connection_info['mode'] == mode and 0 < port <= 65535 and port != db_port
            health = self.client.request('/health')
            assert health['ready'] and health['version'] == VERSION
            self.client.token = self.client.request('/login', {
                'email': 'kandydat@demo.local', 'password': settings['demo_password'],
            })['token']
            assert self.client.request('/workspace')['user']['role'] == 'candidate'
            results.update(result='PASS', mode=mode, postgresql_port=db_port, api_port=port,
                           login_window=True, candidate_logged_in=True)
        except Exception as error:
            errors.append(error)
        finally:
            self.close()


sys.argv = sys.argv[:1]
with (patch.object(launcher, 'choose_mode', choose_option),
      patch.object(start, 'own_command', loopback_command),
      patch.object(app, 'MainWindow', CheckedWindow),
      patch.object(QMessageBox, 'critical', lambda _, title, message: errors.append(RuntimeError(message)))):
    start.main()
if errors:
    raise errors[0]
assert results
release_slug = RELEASE.replace('.', '')
(ROOT / 'tmp' / f'launch-{release_slug}-{mode}.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results))

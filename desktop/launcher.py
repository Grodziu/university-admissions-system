import json
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox
from .widgets import box, label, button, MUTED
from .visuals import FacultyRibbon
from portable import DATA


def choose_mode():
    dialog = QDialog()
    dialog.setWindowTitle('Rekrutacja PK • sposób uruchomienia')
    dialog.setMinimumWidth(620)
    layout = box(dialog, margins=30, spacing=16)
    layout.addWidget(label('Jak dziś pracujesz?', 28, bold=True))
    layout.addWidget(FacultyRibbon())
    layout.addWidget(label('Jedna baza, wspólne zgłoszenia i aktualny etap rekrutacji.', 14, MUTED, wrap=True))
    selected = {}
    def pick(mode, profile=None):
        selected.update(mode=mode, profile=profile)
        dialog.accept()
    layout.addWidget(button('Na tym komputerze', lambda: pick('local')))
    layout.addWidget(label('Samodzielna prezentacja. Serwer i baza uruchomią się automatycznie.', 12, MUTED, wrap=True))
    layout.addWidget(button('Uruchom serwer dla zespołu', lambda: pick('host'), secondary=True))
    layout.addWidget(label('Ten laptop przechowuje dane. Pozostaw go włączonego, gdy pracują inni.', 12, MUTED, wrap=True))
    def connect():
        path, _ = QFileDialog.getOpenFileName(dialog, 'Plik połączenia od administratora', '', 'Połączenie (*.json)')
        if path:
            try:
                from networking import import_profile
                pick('client', import_profile(path))
            except (ValueError, KeyError, OSError) as error:
                QMessageBox.warning(dialog, 'Plik połączenia', str(error))
    layout.addWidget(button('Połącz z serwerem — wybierz plik połączenia', connect, secondary=True))
    saved = DATA / 'client/connection.json'
    if saved.exists():
        def reconnect():
            try:
                from networking import import_profile
                pick('client', import_profile(saved))
            except Exception as error:
                QMessageBox.warning(dialog, 'Połączenie', str(error))
        layout.addWidget(button('Połącz z ostatnio używanym serwerem', reconnect, secondary=True))
    layout.addWidget(label('Wspólna sieć Wi-Fi / LAN wystarczy. Nie potrzebujesz kontenerów ani instalacji PostgreSQL na klientach.', 12, MUTED, wrap=True))
    dialog.exec()
    return selected

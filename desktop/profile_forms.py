from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHeaderView, QLineEdit, QMessageBox, QTableWidgetItem, QWidget
from shiboken6 import isValid

from admissions.domain import number
from .widgets import MUTED, NAVY, box, button, card, combo, field, label, table

EXAM_LEVELS = {'basic': 'Podstawowy', 'extended': 'Rozszerzony', 'technical': 'Technik'}


def address_fields(layout, saved=None):
    saved = saved or {}
    layout.addWidget(label('Adres zamieszkania', 19, NAVY, True))
    entries = {}
    for fields in [
        [('city', 'Miejscowość', 3), ('postal_code', 'Kod pocztowy', 1)],
        [('street', 'Ulica', 3), ('building', 'Nr domu', 1), ('apartment', 'Nr lokalu', 1)],
    ]:
        row = box(horizontal=True)
        for key, title, stretch in fields:
            column = box(spacing=5)
            entries[key] = field(column, title, saved.get(key, ''))
            row.addLayout(column, stretch)
        layout.addLayout(row)
    entries['postal_code'].setPlaceholderText('00-000')
    entries['street'].setPlaceholderText('Jeśli występuje')
    entries['apartment'].setPlaceholderText('Opcjonalny')
    return entries


def columns(left, right):
    row = box(horizontal=True, spacing=16)
    row.addWidget(left, 1)
    row.addWidget(right, 1)
    return row


class ProfilePages:
    def page_profile(self):
        user, profile = self.data['user'], self.data['profile']
        heading = box(horizontal=True)
        heading.addWidget(label('Mój profil', 30, bold=True), 1)
        heading.addWidget(button('Zapisz profil', lambda: save()))
        self.content.addLayout(heading)
        self.content.addWidget(label('Zapisz dane i dokumenty, z których korzystają Twoje zgłoszenia.', 14, MUTED, wrap=True))

        photo_card, notification_email = self.profile_photo(profile, user)
        documents, portfolio_url = self.profile_documents(profile)
        self.content.addLayout(columns(photo_card, documents))

        contact_card, contact = card(17)
        contact.addWidget(label('Dane kandydata', 19, NAVY, True))
        inputs = {}
        for group in [[('first_name', 'Imię', user['first_name']), ('last_name', 'Nazwisko', user['last_name'])],
                      [('phone', 'Telefon kontaktowy', profile['phone']), ('pesel', 'PESEL', '')]]:
            row = box(horizontal=True)
            for key, title, value in group:
                part = box(spacing=4)
                inputs[key] = field(part, title, value, secret=key == 'pesel')
                row.addLayout(part, 1)
            contact.addLayout(row)
        inputs['pesel'].setMaxLength(11)
        inputs['pesel'].setPlaceholderText('Zapisany · wpisz nowy, aby zmienić' if profile['has_pesel'] else '11 cyfr')
        if self.data['campaign']['demo'] and not profile['complete']:
            contact.addWidget(button('Uzupełnij brakujące dane testowe',
                                     lambda: self.mutate({'action': 'profile_demo_identity'}), secondary=True))
        contact.addStretch()

        residence_card, residence = card(17)
        address = address_fields(residence, profile['address'])
        distance = self.data['housing']['my_distance']
        location = (f"{float(distance):.1f}".replace('.', ',') + ' km do kampusu Warszawska' if distance is not None
                    else 'Ustal położenie adresu, aby złożyć wniosek o akademik.')
        residence.addWidget(label(location, 13, NAVY, True, True))
        residence.addWidget(label('Geoportal otrzymuje miejscowość, ulicę i numer domu.', 12, MUTED, wrap=True))
        residence.addWidget(button('Zapisz i ustal położenie adresu', lambda: save(locate=True), secondary=True))
        self.content.addLayout(columns(contact_card, residence_card))

        study_card, study = card(17)
        study.addWidget(label('Ukończone studia', 19, NAVY, True))
        study.addWidget(label('Uzupełnij, jeśli ubiegasz się o przyjęcie na II stopień lub studia podyplomowe.',
                              13, MUTED, wrap=True))
        inputs['diploma'] = field(study, 'Uzyskany tytuł', profile['diploma'])
        inputs['average'] = field(study, 'Średnia z I stopnia (2,00–5,00)', profile['average'])
        study.addStretch()
        exam_card, exams = self.profile_exams(profile['exams'])
        self.content.addLayout(columns(study_card, exam_card))
        self.content.addStretch()

        def save(*, locate=False):
            values = {key: entry.text() for key, entry in inputs.items()}
            values['average'] = values['average'].replace(',', '.')
            payload = {'action': 'profile', **values, 'exams': exams, 'portfolio_url': portfolio_url.text(),
                       'notification_email': notification_email.text(),
                       'address': {key: entry.text() for key, entry in address.items()}}
            if not locate:
                self.mutate(payload)
                return

            def located(result):
                suggested = result.get('postal_code_suggestion')
                if not suggested:
                    self.refresh()
                    return
                if not isValid(residence_card) or not residence_card.isVisible():
                    return
                if payload['address'] != {key: entry.text() for key, entry in address.items()}:
                    return
                prompt = QMessageBox(self)
                prompt.setWindowTitle('Kod pocztowy')
                prompt.setText(f'Geoportal podaje kod {suggested} dla tego adresu.')
                confirm = prompt.addButton(f'Zapisz z kodem {suggested}', QMessageBox.ButtonRole.AcceptRole)
                cancel = prompt.addButton('Wróć do formularza', QMessageBox.ButtonRole.RejectRole)
                prompt.setDefaultButton(cancel)
                prompt.exec()
                if prompt.clickedButton() == confirm:
                    address['postal_code'].setText(suggested)
                    save(locate=True)

            payload['action'] = 'profile_locate'
            self.run(lambda: self.client.request('/action', payload), located, 'Ustalanie położenia w Geoportalu…')

    def profile_photo(self, profile, user):
        panel, body = card(17)
        photo_row = box(horizontal=True, spacing=16)
        preview_holder = QWidget()
        preview = box(preview_holder)
        photo_row.addWidget(preview_holder, 0, Qt.AlignmentFlag.AlignTop)
        description = box(spacing=8)
        description.addWidget(label('Zdjęcie do legitymacji', 19, NAVY, True, True))
        description.addWidget(label('Akceptacja dotyczy tej wersji zdjęcia i obowiązuje we wszystkich zgłoszeniach.',
                                    13, MUTED, wrap=True))
        status = label('', 13, NAVY, True, True)
        description.addWidget(status)

        def show_photo(photo):
            if preview.count():
                old = preview.takeAt(0).widget()
                old.hide()
                old.deleteLater()
            if photo:
                preview.addWidget(self.photo_widget(photo, 112, 144))
                status.setText('Zaakceptowane przez komisję' if photo['approved'] else 'Oczekuje na akceptację')
            else:
                placeholder = label('Brak zdjęcia', 12, MUTED)
                placeholder.setFixedSize(112, 144)
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder.setStyleSheet('background:#E8EFF7; border-radius:8px; color:#53667E;')
                preview.addWidget(placeholder)
                status.clear()

        def upload_photo():
            path, _ = QFileDialog.getOpenFileName(self, 'Wybierz zdjęcie', '', 'Zdjęcia (*.png *.jpg *.jpeg)')
            if not path:
                return

            def done(result):
                profile['photo'] = result
                if isValid(preview_holder):
                    show_photo(result)

            self.run(lambda: self.client.request('/profile/photo', {}, file=path), done, 'Przesyłanie zdjęcia…')

        description.addWidget(button('Wybierz zdjęcie…', upload_photo, secondary=True))
        description.addWidget(label('JPG lub PNG · min. 200 × 200 px · do 10 MB', 11, MUTED, wrap=True))
        photo_row.addLayout(description, 1)
        body.addLayout(photo_row)
        show_photo(profile['photo'])

        body.addSpacing(6)
        body.addWidget(label('Powiadomienia e-mail', 17, NAVY, True))
        email = field(body, 'Adres do powiadomień (opcjonalny)', profile.get('notification_email', ''),
                      placeholder='twoj.adres@example.com')
        body.addWidget(label(f"Adres do logowania: {user['email']}", 11, MUTED, wrap=True))
        email.setMaxLength(254)
        delivery = ('Wpisz adres, aby otrzymywać wiadomości obok powiadomień w aplikacji.'
                    if profile.get('mail_enabled') else 'Adres zapisze się w profilu. Wysyłkę włącza administrator serwera.')
        body.addWidget(label(delivery, 12, MUTED, wrap=True))
        body.addStretch()
        return panel, email

    def profile_documents(self, profile):
        panel, body = card(17)
        body.addWidget(label('Dokumenty do zgłoszeń', 20, NAVY, True))
        body.addWidget(label('Zgłoszenie zachowuje wersje plików z chwili złożenia. Dowód wpłaty dodasz przy zgłoszeniu.',
                             13, MUTED, wrap=True))
        holder = QWidget()
        rows = box(holder, spacing=6)
        body.addWidget(holder)
        portfolio_url = field(body, 'Opcjonalny link HTTPS do portfolio', profile['portfolio_url'])

        def render():
            while rows.count():
                old = rows.takeAt(0).widget()
                old.hide()
                old.deleteLater()
            documents = {item['kind']: item for item in profile['documents']}
            for key, title in profile['document_kinds']:
                item = QWidget()
                line = box(item, horizontal=True)
                content = box(spacing=4)
                content.addWidget(label(title, 13, NAVY, True))
                doc = documents.get(key)
                content.addWidget(label(f"{doc['name']} · wersja {doc['version']}" if doc else 'Brak pliku', 12, MUTED, wrap=True))
                line.addLayout(content, 1)
                if doc:
                    line.addWidget(button('Podgląd', lambda _=False, entry=doc: self.open_document(entry), secondary=True))
                upload_button = button('Zastąp…' if doc else 'Dodaj plik…',
                                       lambda _=False, k=key, name=title: upload(k, name), secondary=True)
                upload_button.setAccessibleName(f'{upload_button.text()} {title}')
                line.addWidget(upload_button)
                rows.addWidget(item)

        def upload(selected, title):
            path, _ = QFileDialog.getOpenFileName(self, title, '', 'Dokumenty (*.pdf *.png *.jpg *.jpeg)')
            if not path:
                return

            def done(result):
                profile['documents'][:] = [doc for doc in profile['documents'] if doc['kind'] != selected] + [result]
                revision = result.get('workspace_revision')
                if self.sync_revision is not None and revision == self.sync_revision + 1:
                    self.sync_revision = revision
                    self.data['revision'] = revision
                if isValid(holder):
                    render()

            self.run(lambda: self.client.request('/profile/document', {'kind': selected}, file=path), done, 'Przesyłanie dokumentu…')

        render()
        return panel, portfolio_url

    def profile_exams(self, saved):
        panel, body = card(17)
        body.addWidget(label('Wyniki matury i kwalifikacje', 19, NAVY, True, True))
        body.addWidget(label('Dodaj matematykę podstawową, rozszerzenia albo wyniki procentowe z dyplomu technika.',
                             13, MUTED, wrap=True))
        exams = [dict(entry) for entry in saved]
        results = table(['Przedmiot lub zawód', 'Poziom', 'Wynik', ''], [])
        results.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        results.setColumnWidth(3, 72)
        results.verticalHeader().setDefaultSectionSize(39)
        body.addWidget(results)

        def remove(entry):
            exams.remove(entry)
            render()

        def render():
            results.clearContents()
            results.setRowCount(len(exams))
            results.setFixedHeight(45 + 39 * max(2, min(5, len(exams))))
            for index, entry in enumerate(exams):
                values = (entry['subject'], EXAM_LEVELS[entry['level']], entry['value'])
                for col, value in enumerate(values):
                    results.setItem(index, col, QTableWidgetItem(str(value)))
                action = button('Usuń', lambda _=False, exam=entry: remove(exam), secondary=True)
                action.setAccessibleName(f"Usuń wynik {entry['subject']}, {EXAM_LEVELS[entry['level']]}")
                action.setStyleSheet('QPushButton { padding: 3px 8px; }')
                results.setCellWidget(index, 3, action)

        row = box(horizontal=True)
        level = combo([('Rozszerzony', 'extended'), ('Podstawowy', 'basic'), ('Technik', 'technical')], 'Poziom egzaminu')
        level.setToolTip('Przy kilku kwalifikacjach technika wynik = 0,3 × średnia części pisemnych + 0,7 × średnia części praktycznych.')
        subject = combo([], 'Przedmiot lub kwalifikacja')
        row.addWidget(level, 1)
        row.addWidget(subject, 2)
        body.addLayout(row)
        score = QLineEdit()
        score.setPlaceholderText('Wynik 0–100')
        score.setAccessibleName('Wynik egzaminu')
        row = box(horizontal=True)
        row.addWidget(score, 1)

        def options():
            allowed = {'technical': self.data['professions'], 'basic': ['matematyka'], 'extended': self.data['subjects']}
            subject.clear()
            for name in allowed[level.currentData()]:
                subject.addItem(name, name)

        def add():
            if not subject.currentData():
                return
            try:
                value = str(number(score.text().replace(',', '.')))
            except ValueError as error:
                QMessageBox.warning(self, 'Wynik', str(error))
                return
            key = (subject.currentData(), level.currentData())
            exams[:] = [entry for entry in exams if (entry['subject'], entry['level']) != key]
            exams.append({'subject': key[0], 'level': key[1], 'value': value})
            score.clear()
            render()

        row.addWidget(button('Dodaj wynik', add, secondary=True))
        body.addLayout(row)
        level.currentIndexChanged.connect(options)
        options()
        render()
        return panel, exams

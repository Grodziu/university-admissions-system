"""Candidate and commission dialogs, with fixed action bars."""
from datetime import date as calendar_date
from pathlib import Path
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QCheckBox, QTextEdit
from shiboken6 import isValid
from .widgets import *
from .visuals import ScoreCard, FacultyHeader, status_chip, tint
from .pages import dialog, date
from .client import asynchronously
from .onboarding import onboarding
from portable import DATA


class WorkflowPages:
    def photo_widget(self,document,width=126,height=162):
        item=label('Ładowanie zdjęcia…',11,MUTED,wrap=True)
        item.setFixedSize(width,height)
        item.setAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setStyleSheet('background:#E8EFF7; border-radius:10px;')
        token = self.client.token
        url = document.get('url', f"/document/{document['id']}")
        def show(content):
            if not isValid(item) or self.client.token != token:
                return
            pixmap=QPixmap(); pixmap.loadFromData(content)
            if pixmap.isNull(): item.setText('Nie można odczytać zdjęcia.'); return
            item.setPixmap(pixmap.scaled(width,height,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            if url.startswith('/profile/photo/'):
                if len(self.photo_cache) >= 12:
                    self.photo_cache.pop(next(iter(self.photo_cache)))
                self.photo_cache[url] = content
        if url in self.photo_cache: show(self.photo_cache[url])
        else:
            self.tasks.append(asynchronously(lambda:self.client.request(url,binary=True),show,lambda error:item.setText('Podgląd niedostępny') if isValid(item) else None))
        return item

    def application_dialog(self,a):
        offer=next(o for o in self.offers if o['id']==a['offer_id'])
        d=dialog(self,a['name'],f"{a['candidate']} • {a['mode']} • tura {a['round']}",900,accent=a['color'])
        d.form.addWidget(status_chip(a['status'],a['status_label']))
        d.form.addWidget(label(a.get('status_help',''),14,MUTED,wrap=True))
        if a['feedback']: d.form.addWidget(label('Wiadomość komisji: '+a['feedback'],14,'#996020',True,True))
        if self.role == 'candidate':
            if a['sworn_at']:
                welcome, message = card(16)
                welcome.setStyleSheet('QFrame#card { background:#E7F4EC; border-color:#C6E0D3; }')
                message.addWidget(label('Gratulacje! Zaczynasz nowy rozdział.', 23, '#145848', True, True))
                message.addWidget(label('Ślubowanie zapisane.', 13, '#376759'))
                d.form.addWidget(welcome)
            if a['status'] == 'confirmed' and a['degree'] in ['I', 'II'] and offer.get('launch_ready'):
                d.form.addWidget(onboarding(offer))
        latest={}
        for doc in a['documents']:
            if doc['kind'] not in latest: latest[doc['kind']]=doc
        attached_latest = dict(latest)
        editable=self.role=='candidate' and a['status'] in ['draft','correction'] and offer['open']
        required = [('education', 'Świadectwo maturalne' if a['degree']=='I' else 'Dyplom studiów'),
                    ('fee', 'Potwierdzenie przelewu')]
        if offer['portfolio_required'] or offer['portfolio_bonus']:
            required.append(('portfolio', 'Portfolio' if offer['portfolio_required'] else 'Portfolio (opcjonalne)'))
        profile_sources = {'education': 'education' if a['degree']=='I' else 'diploma',
                           'portfolio': 'portfolio', 'bonus': 'bonus', 'qualification': 'qualification'}
        if editable:
            source_documents = {item['kind']: item for item in self.data['profile']['documents']}
            for kind, source_kind in profile_sources.items():
                if kind not in dict(required) and kind not in latest:
                    continue
                source = source_documents.get(source_kind)
                if source and latest.get(kind,{}).get('profile_source_id') != source['id']:
                    latest[kind] = dict(source, kind=kind, revision=source['version'],
                                        label=dict(required).get(kind,source['label']),
                                        from_profile=True)

        def add_document(kind, title):
            path,_=QFileDialog.getOpenFileName(d, 'Dodaj: '+title, '', 'Dokumenty (*.pdf *.png *.jpg *.jpeg)')
            if not path:
                return
            endpoint = f"/upload/{a['id']}" if kind=='fee' else '/profile/document'
            upload_kind = 'fee' if kind=='fee' else profile_sources[kind]
            def uploaded(result):
                d.accept()
                self.refresh(lambda:self.application_dialog(next(i for i in self.data['applications'] if i['id']==a['id'])))
            self.run(lambda:self.client.request(endpoint,{'kind':upload_kind},file=path),uploaded,'Przesyłanie pliku…')
        photo=a.get('photo')
        candidate_card, candidate_fields = card(16)
        row = box(horizontal=True, spacing=13)
        if photo:
            row.addWidget(self.photo_widget(photo, 88, 114), 0, Qt.AlignmentFlag.AlignTop)
        info_panel = QWidget()
        info = box(info_panel, spacing=8)
        info.addWidget(label(a['candidate'], 20, NAVY, True, True))
        info.addWidget(label(a['email'], 12, MUTED, wrap=True))
        info.addWidget(label('Złożono: '+date(a['submitted_at']),12,MUTED))
        if a['submitted_at']:
            reference = label('Numer referencyjny: '+a['public_id'][:8].upper(),11,MUTED)
            reference.setToolTip(a['public_id'])
            info.addWidget(reference)
        info.addWidget(chip('Zdjęcie zaakceptowane' if a['photo_approved'] else 'Zdjęcie do akceptacji' if photo else 'Brak zdjęcia'))
        info.addStretch()
        row.addWidget(info_panel, 1)
        candidate_fields.addLayout(row)
        snapshot=a['input']
        if a['degree'] != 'I' and snapshot.get('diploma'):
            candidate_fields.addWidget(label('Wykształcenie: ' + snapshot['diploma'], 13, MUTED, wrap=True))
        if a['degree'] == 'II' and snapshot.get('average'):
            candidate_fields.addWidget(label('Średnia z I stopnia: ' + str(snapshot['average']), 15, NAVY, True))
        candidate_fields.addStretch()

        docs_card, docs = card(16)
        docs.setSpacing(7)
        docs.addWidget(label('Dokumenty', 18, NAVY, True))
        if not latest and not editable:
            docs.addWidget(label('Brak załączników w zgłoszeniu.', 12, MUTED, wrap=True))
        visible_kinds = list(dict.fromkeys([kind for kind,_ in required] + list(latest))) if editable else list(latest)
        for kind in visible_kinds:
            doc = latest.get(kind)
            title = dict(required).get(kind, doc['label'] if doc else kind)
            row = box(horizontal=True, spacing=8)
            file = box(spacing=2)
            file.addWidget(label(title, 13, NAVY, True, True))
            optional = kind=='portfolio' and not offer['portfolio_required']
            file.addWidget(label(f"{doc['name']} · v{doc['revision']}" if doc else 'Brak pliku',
                                 11, MUTED if doc or optional else '#A56A16', wrap=True))
            if doc and doc.get('from_profile'):
                file.addWidget(label('Podpięto z profilu', 11, '#147D69', wrap=True))
            row.addLayout(file, 1)
            if doc:
                preview = button('Podgląd', lambda checked=False, item=doc: self.open_document(item), secondary=True)
                preview.setAccessibleName(f"Podgląd: {title}")
                preview.setFixedWidth(108)
                row.addWidget(preview)
            if editable and kind in {'fee',*profile_sources}:
                upload_button = button('Zastąp…' if doc else 'Dodaj plik…',
                    lambda checked=False,k=kind,t=title:add_document(k,t), secondary=True)
                upload_button.setObjectName('application-upload-'+kind)
                upload_button.setAccessibleName(('Zastąp: ' if doc else 'Dodaj: ')+title)
                upload_button.setFixedWidth(108)
                row.addWidget(upload_button)
            docs.addLayout(row)
        older = [doc for doc in a['documents'] if attached_latest[doc['kind']]['id'] != doc['id']]
        if older:
            def versions():
                v=dialog(d,'Wcześniejsze wersje dokumentów',width=660)
                for doc in older: v.form.addWidget(button(f"{doc['label']} • wersja {doc['revision']} • {doc['name']}",lambda checked=False,item=doc:self.open_document(item),secondary=True))
                v.exec()
            docs.addWidget(button('Wcześniejsze wersje plików', versions, secondary=True))
        docs.addStretch()
        overview = box(horizontal=True, spacing=12)
        overview.addWidget(candidate_card, 1)
        overview.addWidget(docs_card, 1)
        d.form.addLayout(overview)
        exams = snapshot.get('exams', [])
        if exams:
            exam_table = table(['Przedmiot / kwalifikacja', 'Poziom', 'Wynik'],
                               [[e['subject'], {'basic': 'Podstawowy', 'extended': 'Rozszerzony', 'technical': 'Technik'}.get(e['level'], e['level']),
                                 e['value']] for e in exams])
            exam_table.verticalHeader().setDefaultSectionSize(37)
            exam_table.setFixedHeight(48 + 37 * min(5, len(exams)))
            d.form.addWidget(exam_table)
        if editable:
            profile = self.data['profile']
            education = 'Świadectwo maturalne' if a['degree'] == 'I' else 'Dyplom studiów'
            d.form.addWidget(label(f'{education} i inne potrzebne załączniki system pobierze z Twojego profilu przy składaniu zgłoszenia.',
                                   13, MUTED, wrap=True))
            d.form.addWidget(button('Otwórz dokumenty w Moim profilu' if profile['complete'] else 'Uzupełnij dane i dokumenty w Moim profilu',
                                    lambda: (d.accept(), self.navigate('profile')), secondary=True))
            bonus=QCheckBox('Wnioskuję o premię za udokumentowane osiągnięcie (do 50 pkt)'); bonus.setChecked(a['bonus_claimed']); bonus.setVisible(a['degree']=='I'); d.form.addWidget(bonus)
            def save(submit=False):
                data={'action':'save_draft','id':a['id'],'bonus_claimed':bonus.isChecked()}
                def task():
                    self.client.request('/action',data)
                    if submit:
                        return self.client.request('/action', {'action': 'submit', 'id': a['id'], 'expected_round': offer['round']})
                self.run(task,lambda r:(d.accept(),self.refresh()))
            d.actions.addWidget(button('Zapisz szkic',lambda:save(False),secondary=True)); d.actions.addWidget(button('Złóż zgłoszenie',lambda:save(True)))
        elif a['portfolio_url']:
            d.form.addWidget(button('Otwórz portfolio / projekt',lambda:QDesktopServices.openUrl(QUrl(a['portfolio_url'])),secondary=True))
        if self.role=='candidate' and a['status'] in ['draft','correction'] and not offer['open']:
            d.form.addWidget(label(offer['block_reason'],14,'#996020',True,True))
        result=a['result']
        current_result = result if result and result['round'] == a['round'] else None
        explanation = current_result['explanation'] if current_result else a['preview']
        if self.role=='candidate':
            if a['status']=='qualified': d.actions.addWidget(button('Potwierdzam miejsce',lambda:self.mutate({'action':'confirm','id':a['id']},d)))
            if a['status'] in ['waitlist','expired','withdrawn','rejected'] and offer['open'] and offer['round']>a['round']:
                d.actions.addWidget(button('Zgłoś w kolejnej turze',lambda:self.mutate({'action':'continue','id':a['id']},d)))
            if a['sworn_at']:
                d.actions.addWidget(button('Podgląd legitymacji',lambda:self.student_card(a)))
            elif a['can_oath']:
                d.actions.addWidget(button('Złóż ślubowanie',lambda:self.oath_dialog(a,d)))
            elif a['status']=='confirmed' and a['campaign_closed'] and a['offer_state']=='launched':
                d.form.addWidget(label(a['oath_block'],14,'#996020',True,True))
                if not photo or not self.data['profile']['has_pesel']:
                    d.form.addWidget(button('Uzupełnij profil', lambda: (d.accept(), self.navigate('profile')), secondary=True))
            if a['status'] not in ['withdrawn','canceled','expired'] and not a['campaign_closed']:
                def withdraw():
                    if QMessageBox.question(d,'Wycofanie zgłoszenia','Wycofać zgłoszenie i zwolnić ewentualne miejsce?')==QMessageBox.StandardButton.Yes: self.mutate({'action':'withdraw','id':a['id']},d)
                d.form.addWidget(button('Wycofaj zgłoszenie',withdraw,danger=True))
        elif self.role in ['commission','admin']:
            if photo and not photo['approved'] and a['status'] != 'draft' and not a['sworn_at']:
                info.addWidget(button('Zaakceptuj zdjęcie w profilu', lambda: self.mutate({
                    'action': 'photo_review', 'id': a['id'], 'photo_approved': True,
                    'expected_revision': a['revision'], 'expected_photo_id': photo['id']
                }, d), secondary=True))
            if (a['status'] in ['submitted','correction','verified','rejected'] and not a['campaign_closed']
                    and not current_result and offer['round'] == a['round']):
                review_panel, review_fields = card(16)
                review_fields.addWidget(label('Decyzja komisji', 19, NAVY, True))
                payment=QCheckBox(f"Kwota na potwierdzeniu jest zgodna: {a['fee']} zł")
                payment.setChecked(a['payment_approved'])
                review_fields.addWidget(payment)
                amount=field(review_fields,'Kwota odczytana przy niezgodności','','np. 50,00')
                def payment_changed(matched):
                    if matched:
                        amount.clear()
                    amount.setEnabled(not matched)
                payment.toggled.connect(payment_changed)
                payment_changed(payment.isChecked())
                photo_ok=QCheckBox('Zdjęcie z profilu jest poprawne')
                if photo and not photo['approved']:
                    review_fields.addWidget(photo_ok)
                has_portfolio = 'portfolio' in latest or bool(a['portfolio_url'])
                portfolio = None
                if has_portfolio and (offer['portfolio_required'] or offer['portfolio_bonus']):
                    grades = [('Nie oceniono','none'),('Zaakceptowane','accepted'),('Odrzucone','rejected')]
                    if offer['portfolio_bonus']:
                        grades.insert(2, ('Wyróżnione · P₂ = 100','excellent'))
                    portfolio = combo(grades, 'Ocena portfolio')
                    portfolio.setCurrentIndex(max(0,portfolio.findData(a['portfolio_grade'])))
                    review_fields.addWidget(label('Portfolio wymagane' if offer['portfolio_required'] else 'Portfolio dodatkowe',12,MUTED,True))
                    review_fields.addWidget(portfolio)
                elif offer['portfolio_required']:
                    review_fields.addWidget(label('Brakuje wymaganego portfolio.',13,'#996020',True))
                catalog = list(self.data['bonus_catalog'])
                if a['bonus_category'] == 'legacy50':
                    catalog.append({'code': 'legacy50', 'points': 50, 'title': 'Poprzednia reguła',
                                    'evidence': 'Zachowaj premię już zatwierdzoną według reguły 2027.1.'})
                bonus = None
                if a['degree']=='I' and a['bonus_claimed']:
                    bonus = combo([(f"{r['points']} pkt • {r['title']}", r['code']) for r in catalog])
                    bonus.setCurrentIndex(max(0,bonus.findData(a['bonus_category'])))
                    review_fields.addWidget(label('Premia za osiągnięcie',12,MUTED,True)); review_fields.addWidget(bonus)
                    evidence=label('',12,MUTED,wrap=True); review_fields.addWidget(evidence)
                    def explain(): evidence.setText(next(r['evidence'] for r in catalog if r['code']==bonus.currentData()))
                    bonus.currentIndexChanged.connect(explain); explain()
                feedback=QTextEdit(); feedback.setPlaceholderText('Czego brakuje lub z jakiego powodu odrzucasz zgłoszenie?'); feedback.setMaximumHeight(90)
                review_fields.addWidget(feedback)
                d.form.addWidget(review_panel)
                def review(decision):
                    self.mutate({'action':'review','id':a['id'],'decision':decision,'payment_matches':payment.isChecked(),
                        'payment_amount':amount.text().replace(',','.'),
                        'photo_approved':bool(photo and (photo['approved'] or photo_ok.isChecked())),
                        'expected_photo_id':photo['id'] if photo else None,
                        'portfolio_grade':portfolio.currentData() if portfolio else 'none',
                        'bonus_category':bonus.currentData() if bonus else '', 'feedback':feedback.toPlainText(),
                        'expected_revision':a['revision']},d)
                correction = button('Do uzupełnienia',lambda:review('correct'),secondary=True)
                correction.setEnabled(offer['open'])
                d.buttons.addWidget(correction)
                d.buttons.addWidget(button('Odrzuć',lambda:review('reject'),danger=True))
                verify = button('Zatwierdź dokumenty i opłatę',lambda:review('verify'))
                verify.setEnabled(payment.isChecked())
                payment.toggled.connect(verify.setEnabled)
                d.buttons.addWidget(verify)
            elif a['status'] in ['qualified','waitlist','confirmed'] and a['degree']!='PG' and not a['campaign_closed']:
                d.form.addWidget(button('Korekta wyniku → nowa wersja listy',lambda:self.correction_dialog(a),secondary=True))
            d.form.addWidget(button('Ranking kierunku na żywo',lambda:self.ranking_dialog(offer),secondary=True))
        if explanation:
            heading = 'Skąd mój wynik?' if self.role == 'candidate' else 'Punktacja kandydata'
            d.form.addWidget(ScoreCard(explanation, a['degree'], heading=heading, published=bool(current_result)))
        if result:
            if current_result:
                d.form.addWidget(label(f"Pozycja {result['rank']} • tura {result['round']} • wersja {result['version']}",13,NAVY,True))
            d.form.addWidget(button('Historia opublikowanych wyników',lambda:self.history_dialog(a),secondary=True))
        d.resize(900,820); d.exec()

    def ranking_dialog(self,offer):
        d=dialog(self,'Ranking na żywo',f"{offer['name']} • {offer['degree_label']} • {offer['mode_label']}",980,accent=offer['color'])
        caption=label('Pobieranie…',14,MUTED,wrap=True); d.form.addWidget(caption)
        t=table(['Miejsce','Kandydat','Wynik','Prognoza','Obecny status'],[],1); t.setMinimumHeight(420); d.form.addWidget(t)
        pending={'busy':False}
        def fetch():
            if pending['busy']: return
            pending['busy']=True
            def done(data):
                pending['busy']=False
                if not isValid(d): return
                caption.setText(f"Tura {data['round']} • dostępne miejsca: {data['available']} • w granicy przyjęcia: {data['qualified']} • oczekuje na weryfikację: {data['pending']}\nPodgląd aktualizowany co 5 sekund. Nadmiar z remisów: {data['overflow']}.")
                rows=data['rows']; t.setRowCount(len(rows))
                for i,r in enumerate(rows):
                    for j,v in enumerate([r['rank'],r['candidate'],r['score'] if r['score'] is not None else date(r['submitted_at']),'W granicy przyjęcia' if r['selected'] else 'Rezerwa',r['status_label']]):
                        item=QTableWidgetItem(str(v)); item.setBackground(QColor('#EDF7F1' if r['selected'] else '#FFF6E8')); t.setItem(i,j,item)
            def fail(error):
                pending['busy']=False
                if isValid(caption): caption.setText(error)
            self.tasks.append(asynchronously(lambda:self.client.request(f"/ranking/{offer['id']}"),done,fail))
        timer=QTimer(d); timer.timeout.connect(fetch); timer.start(5000); fetch(); d.resize(980,720); d.exec(); timer.stop()

    def select_publications(self):
        ready = [o for o in self.visible_offers if o['publication_phase'] == 'ready']
        if not ready:
            return
        d=dialog(self,'Publikuj listy','Wybierz tryby, których wyniki chcesz ogłosić.',850)
        checks=[]
        for o in ready:
            b=QCheckBox(f"{o['name']} · {o['degree_label']} · {o['mode_label']} · tura {o['round']}")
            b.setChecked(True)
            d.form.addWidget(b)
            checks.append((o, b))
        def publish():
            selected = [o for o, b in checks if b.isChecked()]
            if not selected:
                return
            self.batch_dialog('publish', [o['id'] for o in selected], d)
        d.buttons.addWidget(button('Opublikuj zaznaczone…',publish))
        d.exec()

    def batch_dialog(self,operation,ids,parent_dialog=None):
        if not ids:
            QMessageBox.information(self,'Brak wyboru','Zaznacz zgłoszenia w tabeli.')
            return
        if len(ids) > 250:
            QMessageBox.information(self,'Zbyt duży wybór','Zawęź zestaw za pomocą filtrów do 250 zgłoszeń.')
            return
        titles = {'verify': 'Zatwierdzanie zgłoszeń', 'publish': 'Ogłoszenie wyników', 'confirm_demo': 'Potwierdzanie miejsc w symulacji'}
        d=dialog(self,titles[operation],f'Zaznaczono {len(ids)} pozycji.',910)
        payload = {'action': 'batch', 'operation': operation, 'ids': ids}
        options = {}
        if operation == 'verify':
            apps = [a for a in self.data['applications'] if a['id'] in ids]
            offers = {o['id']: o for o in self.offers}
            payload['expected_revisions'] = {str(a['id']): a['revision'] for a in apps}
            payload['expected_photos'] = {str(a['id']): a['photo']['id'] if a['photo'] else None for a in apps}
            options['payment_matches'] = QCheckBox('Sprawdziłem wszystkie potwierdzenia przelewów. Kwoty są zgodne.')
            if any(a['photo'] and not a['photo_approved'] for a in apps):
                options['photo_approved'] = QCheckBox('Obejrzałem zdjęcia oczekujące na akceptację. Są poprawne.')
            if any(offers[a['offer_id']]['portfolio_required'] for a in apps):
                options['portfolio_grade'] = QCheckBox('Sprawdziłem i akceptuję wymagane portfolio.')
            for check in options.values():
                d.form.addWidget(check)
        if operation == 'publish':
            payload['expected_rounds'] = {str(o['id']): o['round'] for o in self.offers if o['id'] in ids and o['round']}
        result_label = label('',14,NAVY,True,True)
        d.form.addWidget(result_label)
        results = table(['Pozycja','Stan','Szczegóły'],[],0)
        results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        results.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        results.setWordWrap(True)
        results.setMinimumHeight(240)
        results.hide()
        d.form.addWidget(results)
        preview_state = {}
        finished = False
        inflight = False
        apply=button({'verify':'Zatwierdź gotowe', 'publish':'Opublikuj gotowe', 'confirm_demo':'Potwierdź miejsca'}[operation])
        apply.setEnabled(False)
        d.buttons.addWidget(apply)
        timer = QTimer(d)
        timer.setSingleShot(True)
        timer.setInterval(250)
        def selection():
            current = dict(payload, preview=True)
            for key, check in options.items():
                current[key] = ('accepted' if check.isChecked() else 'none') if key == 'portfolio_grade' else check.isChecked()
            return current
        def render(result, submitted=False):
            count = result['success']
            word = 'Zapisano' if submitted else 'Gotowe do zatwierdzenia'
            result_label.setText(f"{word}: {count}.  Wymaga uwagi: {len(result['results']) - count}.")
            rows = sorted(result['results'], key=lambda r: r['ok'])
            results.setRowCount(len(rows))
            for i, item in enumerate(rows):
                state = ('Zapisano' if submitted else 'Gotowe') if item['ok'] else 'Pominięte'
                for j, value in enumerate([item['subject'], state, item['message']]):
                    cell = QTableWidgetItem(value)
                    if j == 1:
                        cell.setForeground(QColor('#147D69' if item['ok'] else '#A56A16'))
                    results.setItem(i,j,cell)
            results.show()
        def schedule():
            apply.setEnabled(False)
            preview_state.clear()
            results.hide()
            input_ready = 'payment_matches' not in options or options['payment_matches'].isChecked()
            result_label.setText('Ustalam, które pozycje są gotowe…' if input_ready else 'Potwierdź sprawdzenie opłat, aby zobaczyć gotowe zgłoszenia.')
            if input_ready and not inflight:
                timer.start()
            elif not input_ready:
                timer.stop()
        for item in options.values():
            item.toggled.connect(schedule)
        def check():
            nonlocal inflight
            current = selection()
            inflight = True
            def done(result):
                nonlocal inflight
                inflight = False
                if not isValid(d) or not d.isVisible():
                    return
                if current != selection():
                    schedule()
                    return
                preview_state.update(current, ids=[item['id'] for item in result['results'] if item['ok']])
                render(result)
                apply.setEnabled(bool(preview_state['ids']))
            def failed(error):
                nonlocal inflight
                inflight = False
                if isValid(d) and d.isVisible():
                    if current == selection():
                        result_label.setText(error)
                    else:
                        schedule()
            self.tasks.append(asynchronously(lambda:self.client.request('/action',current),done,failed))
            self.tasks = self.tasks[-20:]
        def commit():
            current = dict(preview_state,preview=False)
            if not current.get('ids'):
                return
            for option in options.values():
                option.setEnabled(False)
            apply.setEnabled(False)
            def done(result):
                nonlocal finished
                finished = bool(result['success'])
                if isValid(d):
                    render(result, submitted=True)
                    apply.hide()
            self.run(lambda:self.client.request('/action',current),done)
        apply.clicked.connect(commit)
        timer.timeout.connect(check)
        schedule()
        d.resize(910,680)
        d.exec()
        if finished:
            if parent_dialog:
                parent_dialog.accept()
            self.refresh()

    def history_dialog(self,app):
        def show(rows):
            d=dialog(self,'Historia wyników',app['name'],820,accent=app['color'])
            for r in rows:
                f,l=card()
                l.addWidget(label(f"Tura {r['round']} • wersja {r['version']}",20,NAVY,True))
                l.addWidget(label(date(r['published_at']),12,MUTED))
                l.addWidget(chip('Zakwalifikowano' if r['decision']=='qualified' else 'Lista rezerwowa'))
                l.addWidget(label(f"Miejsce {r['rank']} • wynik {r['score'] if r['score'] is not None else 'według kolejności'}",19,NAVY,True))
                l.addWidget(label(r['reason'] or 'Pierwsza publikacja listy tej tury.',13,MUTED,wrap=True))
                d.form.addWidget(f)
            if not rows: d.form.addWidget(label('Brak opublikowanych wyników.',14,MUTED))
            d.exec()
        self.run(lambda:self.client.request(f"/history/{app['id']}"),show)

    def oath_dialog(self,a,parent_dialog):
        d=dialog(self,'Witaj w społeczności akademickiej',a['name'],750,accent=a['color'])
        d.form.addWidget(label(self.data['oath_text'],16,NAVY,wrap=True))
        accepted=QCheckBox('Zapoznałem się z treścią i składam ślubowanie'); d.form.addWidget(accepted)
        def commit():
            def done(result):
                d.accept(); parent_dialog.accept()
                self.refresh(lambda:self.application_dialog(next(i for i in self.data['applications'] if i['id']==a['id'])))
            self.run(lambda:self.client.request('/action',{'action':'oath','id':a['id'],'accepted':accepted.isChecked()}),done)
        d.buttons.addWidget(button('Złóż ślubowanie',commit)); d.exec()

    def student_card(self,a):
        d=dialog(self,'Twoja legitymacja — podgląd projektu','Gratulacje! Każdy wielki projekt zaczyna się od ciekawości.',720,accent=a['color'])
        d.resize(720, 560)
        frame,l=card(26); l.addWidget(label('POLITECHNIKA KRAKOWSKA',20,NAVY,True)); l.addWidget(chip('WZÓR DEMONSTRACYJNY • NIE JEST DOKUMENTEM','#996020','#FFF4DF'))
        row=box(horizontal=True,spacing=24)
        photo=a.get('photo')
        if photo: row.addWidget(self.photo_widget(photo,150,192))
        info = box(spacing=8)
        info.addWidget(label(a['candidate'], 24, NAVY, True, True))
        info.addWidget(label(a['student_number'], 16, MUTED))
        info.addWidget(label(a['name'], 17, NAVY, True, True))
        info.addWidget(label(a['mode'], 13, MUTED))
        if a.get('card_valid_until'):
            valid_from = calendar_date.fromisoformat(a['card_valid_from']).strftime('%d.%m.%Y')
            valid_until = calendar_date.fromisoformat(a['card_valid_until']).strftime('%d.%m.%Y')
            info.addWidget(label(f'Ważność od {valid_from} do {valid_until}', 14, NAVY, True, True))
        info.addWidget(label('Ślubowanie: ' + date(a['sworn_at']), 12, MUTED))
        row.addLayout(info, 1)
        l.addLayout(row)
        d.form.addWidget(frame)
        d.exec()

    def security(self):
        if self.data['user']['totp_enabled']:
            d=dialog(self,'Wyłącz Authenticator','Potwierdź tożsamość hasłem i aktualnym kodem. Inne sesje tego konta zostaną zakończone.')
            password=field(d.form,'Hasło',secret=True); code=field(d.form,'Aktualny kod 6-cyfrowy'); code.setMaxLength(6)
            d.buttons.addWidget(button('Wyłącz weryfikację dwuetapową',lambda:self.mutate({'action':'totp_disable','password':password.text(),'code':code.text()},d),danger=True)); d.exec(); return
        def show(result):
            d=dialog(self,'Włącz Authenticator','Dodaj konto w aplikacji TOTP, wybierając ręczne wpisanie klucza. Internet nie jest potrzebny do generowania kodów.')
            secret=field(d.form,'Klucz do aplikacji',result['secret']); secret.setReadOnly(True)
            d.form.addWidget(button('Kopiuj klucz',lambda:QApplication.clipboard().setText(result['secret']),secondary=True))
            code=field(d.form,'Aktualny kod 6-cyfrowy'); code.setMaxLength(6)
            d.buttons.addWidget(button('Włącz',lambda:self.mutate({'action':'totp_enable','code':code.text()},d,lambda r:self.show_recovery(r['recovery_code'])))); d.exec()
        self.run(lambda:self.client.request('/action',{'action':'totp_setup'}),show)

    def open_document(self,doc):
        url = doc.get('url', f"/document/{doc['id']}")
        if Path(doc['name']).suffix.lower() in ['.png','.jpg','.jpeg']:
            d=dialog(self,doc['label'],doc['name'],660); d.form.addWidget(self.photo_widget(doc,550,550)); d.resize(660,780); d.exec(); return
        def done(content):
            target=DATA/'preview'; target.mkdir(parents=True,exist_ok=True)
            path=target/(url.strip('/').replace('/', '-')+Path(doc['name']).suffix.lower()); path.write_bytes(content)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        self.run(lambda:self.client.request(url,binary=True),done,'Otwieranie dokumentu…')

"""Shared workspace pages; all authoritative state comes from the API."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from PySide6.QtWidgets import QLineEdit, QMessageBox, QFileDialog, QApplication, QGridLayout, QProgressBar
from .widgets import *
from .visuals import RoundTimeline, tint
from .client import asynchronously
from shiboken6 import isValid

DEGREES = [('I stopień', 'I'), ('II stopień', 'II'), ('Podyplomowe', 'PG')]


def date(value):
    if not value:
        return '—'
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone().strftime('%d.%m.%Y, %H:%M')


def dialog(*args, **kwargs):
    from .app import FormDialog
    return FormDialog(*args, **kwargs)


class WorkspacePages:
    def campaign_query(self):
        return f'?campaign_id={self.campaign_id}' if self.campaign_id else ''

    def refresh(self, after=None):
        if self.current == 'login' or self.busy:
            return
        query, token = self.campaign_query(), self.client.token
        scroll = self.page.verticalScrollBar().value() if hasattr(self, 'page') and isValid(self.page) else 0
        def fetch():
            data = self.client.request('/workspace' + query) if token else self.data
            selected_query = f"?campaign_id={data['campaign']['id']}" if token else query
            return data, self.client.request('/catalog' + selected_query), self.client.request('/thresholds' + selected_query)
        def done(result):
            if token != self.client.token:
                return
            self.data, self.offers, self.threshold_rows = result
            self.sync_revision = self.data.get('revision')
            self.shell()
            self.page.verticalScrollBar().setValue(scroll)
            if callable(after):
                after()
        self.run(fetch, done, 'Odświeżanie danych z serwera…')

    def poll_server(self):
        if not self.client.token or self.sync_busy or self.busy or self.current == 'login':
            return
        self.sync_busy = True
        token = self.client.token
        query = self.campaign_query()
        def done(state):
            self.sync_busy = False
            if token != self.client.token or query != self.campaign_query() or 'campaign' not in self.data:
                return
            campaign = self.data['campaign']
            phase_changed = (state['campaign_id'] != campaign['id'] or state['phases'] != campaign['phases']
                             or state['closed'] != campaign['closed'])
            if state['revision'] != self.sync_revision or phase_changed:
                modal = QApplication.activeModalWidget()
                if modal or self.current == 'profile':
                    self.sync_notice.setText('Stan naboru się zmienił. Zakończ edycję i odśwież widok.')
                    self.sync_notice.show()
                    if phase_changed and hasattr(modal, 'sync_banner'):
                        modal.sync_banner.show()
                else:
                    self.refresh()
        def fail(message):
            self.sync_busy = False
            if token != self.client.token:
                if not self.client.token and self.data:
                    self.reset_session()
                return
            self.statusBar().showMessage(message)
        self.tasks.append(asynchronously(lambda: self.client.request('/state' + query), done, fail))
        self.tasks = self.tasks[-20:]

    def page_dashboard(self):
        if self.role in ['commission', 'admin']:
            self.staff_dashboard()
            return
        from .dashboard import CampusSlideshow, campus_resources
        from .onboarding import onboarding

        self.title(f"Dzień dobry, {self.data['user']['first_name']}", 'Twój nabór na Politechnikę Krakowską')
        apps = self.data['applications']
        household = self.data['housing']
        profile = self.data['profile']
        panels = QGridLayout()
        panels.setSpacing(16)
        panels.setColumnStretch(0, 7)
        panels.setColumnStretch(1, 5)
        f, l = card()
        l.addWidget(label('Twój następny krok', 22, bold=True))
        pending = next((a for a in apps if a.get('can_oath')), None)
        pending = pending or next((a for a in apps if a['status'] in ['qualified', 'correction', 'draft']), None)
        pending = pending or next((a for a in apps if a['status'] in ['confirmed', 'submitted', 'verified']), None)
        if not (profile['complete'] and profile['photo']) and not (pending and pending['status'] == 'confirmed'):
            l.addWidget(label('Uzupełnij dane i zdjęcie, aby złożyć zgłoszenie.', 15, NAVY, True, True))
            l.addStretch()
            l.addWidget(button('Uzupełnij profil', lambda: self.navigate('profile')))
        else:
            l.addWidget(label(pending['name'] if pending else 'Wybierz kierunek studiów', 17, NAVY, True, True))
            if pending and pending.get('sworn_at'):
                step = 'Gratulacje! Zaczynasz nowy rozdział.'
            elif pending and pending.get('can_oath'):
                step = 'Możesz teraz złożyć ślubowanie.'
            else:
                step = pending['status_help'] if pending else 'Przejrzyj ofertę wydziałów i sprawdź wymagania.'
            l.addWidget(label(step, 14, MUTED, wrap=True))
            l.addStretch()
            l.addWidget(button('Otwórz zgłoszenie' if pending else 'Poznaj kierunki', lambda: self.application_dialog(pending) if pending else self.navigate('catalog')))
        panels.addWidget(f, 0, 0)
        confirmed = {a['offer_id'] for a in apps if a['degree'] in ['I', 'II'] and a['status'] == 'confirmed'}
        starting = next((o for o in self.offers if o['id'] in confirmed and o.get('launch_ready')), None)

        agenda, contents = card(18)
        contents.addWidget(label('Terminy i sprawy studenckie', 18, NAVY, True, True))
        if household['published']:
            contents.addWidget(label('Wyniki naboru są już dostępne.', 13, MUTED, wrap=True))
        else:
            ends = sorted(r['application_end'] for r in self.data['campaign']['rounds'] if r['application_end'] > self.data['campaign']['now'])
            if ends:
                contents.addWidget(label('Najbliższe zamknięcie zapisów', 12, MUTED, wrap=True))
                contents.addWidget(label(date(ends[0]), 15, NAVY, True))
        contents.addStretch()
        shortcuts = box(horizontal=True, spacing=8)
        shortcuts.addWidget(button('Harmonogram', lambda: self.navigate('timeline'), secondary=True), 1)
        request = household['request']
        housing_label = f"Akademiki · {request['label']}" if request else 'Akademiki'
        shortcuts.addWidget(button(housing_label, lambda: self.navigate('housing'), secondary=True), 1)
        contents.addLayout(shortcuts)
        panels.addWidget(agenda, 0, 1)
        gallery_row = 1
        if starting:
            panels.addWidget(onboarding(starting), 1, 0, 1, 2)
            gallery_row = 2
        panels.addWidget(CampusSlideshow(lambda: self.navigate('krakow')), gallery_row, 0)
        panels.addWidget(campus_resources(), gallery_row, 1)
        self.content.addLayout(panels)
        self.content.addStretch()

    def staff_dashboard(self):
        self.title('Pulpit rekrutacji', self.data['campaign']['name'].removesuffix(' • demonstracja'))
        data = self.data['insights']
        metrics = box(horizontal=True, spacing=14)
        for title, key, color in [('Kandydaci', 'candidates', NAVY), ('Złożone zgłoszenia', 'applications', '#00679C'),
                                  ('Do sprawdzenia lub uzupełnienia', 'pending', '#996020'),
                                  ('Oczekują na potwierdzenie', 'qualified', '#714696'),
                                  ('Potwierdzone miejsca', 'confirmed', '#147D69')]:
            panel, body = card(16)
            body.addWidget(label(f"{data[key]:,}".replace(',', '\u202f'), 34, color, True))
            body.addWidget(label(title, 13, MUTED, True, True))
            body.addStretch()
            metrics.addWidget(panel, 1)
        self.content.addLayout(metrics)
        next_panel, body = card(18)
        body.addWidget(label('Następne działanie', 20, NAVY, True))
        ready = sum(o['publication_phase'] == 'ready' for o in self.offers)
        if self.data['campaign']['closed']:
            message = f"Uruchomione warianty kierunków: {sum(o['state'] == 'launched' for o in self.offers)} / {len(self.offers)}."
        elif self.data['can_create_offer']:
            message = 'Nabór jeszcze się nie rozpoczął. Możesz przygotować katalog ofert.'
        elif ready:
            message = f"Listy gotowe do publikacji: {ready}. Po ogłoszeniu wyników zakwalifikowani mogą potwierdzić miejsce."
        elif data['pending']:
            message = f"Do weryfikacji lub uzupełnienia pozostało {data['pending']} zgłoszeń."
        elif data['qualified']:
            message = f"Na potwierdzenie kandydata czeka {data['qualified']} miejsc."
        else:
            message = 'Terminy zamknięcia zapisów i ogłoszenia wyników znajdziesz w harmonogramie.'
        body.addWidget(label(message, 14, MUTED, wrap=True))
        actions = box(horizontal=True)
        for title, key in [('Weryfikacja zgłoszeń', 'review'), ('Kierunki i listy', 'catalog'), ('Harmonogram', 'timeline')]:
            actions.addWidget(button(title, lambda checked=False, key=key: self.navigate(key), secondary=True))
        body.addLayout(actions)
        self.content.addWidget(next_panel)

        charts = box(horizontal=True, spacing=16)
        popular, ranking = card(18)
        ranking.addWidget(label('Najczęściej wybierane kierunki', 19, NAVY, True, True))
        ranking.addWidget(label('Liczba złożonych zgłoszeń we wszystkich trybach', 12, MUTED, wrap=True))
        totals, colors = Counter(), {}
        for offer in self.offers:
            total = data['by_offer'].get(str(offer['id']), 0)
            totals[offer['name']] += total
            colors[offer['name']] = offer['color']
        top = [(name, count) for name, count in totals.most_common(6) if count]
        for name, value in top:
            row = box(horizontal=True, spacing=8)
            row.addWidget(label(name, 13, NAVY, wrap=True), 1)
            row.addWidget(label(value, 14, NAVY, True))
            ranking.addLayout(row)
            bar = QProgressBar()
            bar.setRange(0, top[0][1])
            bar.setValue(value)
            bar.setTextVisible(False)
            bar.setFixedHeight(7)
            bar.setAccessibleName(f'{name}, {value} zgłoszeń')
            bar.setStyleSheet(f'QProgressBar {{ border:none; border-radius:3px; background:#EAF0F7; }} QProgressBar::chunk {{ border-radius:3px; background:{colors[name]}; }}')
            ranking.addWidget(bar)
        if not top:
            ranking.addWidget(label('Pojawią się po złożeniu pierwszych zgłoszeń.', 13, MUTED, wrap=True))
        ranking.addStretch()
        charts.addWidget(popular, 1)
        rounds_card, breakdown = card(18)
        breakdown.addWidget(label('Zgłoszenia według tur', 19, NAVY, True))
        counts = {(v['degree'], v['round']): v['applications'] for v in data['by_round']}
        rows = [[name, *(counts.get((code, n), 0) if (code == 'I' or n < 3) else '—' for n in (1, 2, 3))]
                for name, code in DEGREES]
        t = table(['Stopień', 'Tura 1', 'Tura 2', 'Tura 3'], rows)
        t.setFixedHeight(200)
        breakdown.addWidget(t)
        breakdown.addWidget(label('Zgłoszenie liczy się w ostatniej turze, w której uczestniczyło.', 12, MUTED, wrap=True))
        breakdown.addStretch()
        charts.addWidget(rounds_card, 1)
        self.content.addLayout(charts)
        self.content.addStretch()

    def page_review(self):
        self.title('Weryfikacja zgłoszeń', 'Sprawdź dokumenty, opłatę i zdjęcie z profilu. Gotowe zgłoszenia trafią do rankingu.')
        saved = self.filters.get('review', {})
        choices = [('Wszystkie statusy',''),('Szkic','draft'),('Do weryfikacji','submitted'),('Do uzupełnienia','correction'),
            ('Dokumenty zatwierdzone','verified'),('Oczekuje na potwierdzenie miejsca','qualified'),('Miejsce potwierdzone','confirmed'),
            ('Lista rezerwowa','waitlist'),('Brak potwierdzenia — termin minął','expired'),('Odrzucone','rejected'),('Wycofane','withdrawn'),('Kierunek nieuruchomiony','canceled')]
        search = QLineEdit(saved.get('search',''))
        search.setPlaceholderText('Kandydat lub kierunek…')
        status, mode = combo(choices,'Status zgłoszenia'),combo([('Wszystkie tryby',''),('Stacjonarne','S'),('Niestacjonarne','N')],'Tryb studiów')
        for key,item in [('status',status),('mode',mode)]:
            item.setCurrentIndex(max(0,item.findData(saved.get(key))))
        filters = box(horizontal=True)
        filters.addWidget(search,2)
        filters.addWidget(status,2)
        filters.addWidget(mode,1)
        self.content.addLayout(filters)
        holder=QWidget(); layout=box(holder)
        self.content.addWidget(holder,1)
        selected=set()
        def render():
            self.filters['review']={'search':search.text(),'status':status.currentData(),'mode':mode.currentData()}
            while layout.count():
                item=layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            apps=[a for a in self.data['applications'] if (not status.currentData() or a['status']==status.currentData()) and (not mode.currentData() or a['mode_code']==mode.currentData()) and search.text().casefold() in (a['candidate']+' '+a['name']).casefold()]
            t=table(['✓','Kandydat','Kierunek','Tryb','Stopień','Tura','Status'],[['',a['candidate'],a['name'],a['mode'],a['degree'],a['round'],a['status_label']] for a in apps],2)
            t.setMinimumHeight(420)
            for i,a in enumerate(apps):
                t.item(i, 2).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item=t.item(i,0)
                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                if a['status'] == 'submitted':
                    item.setFlags(flags | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Checked if a['id'] in selected else Qt.CheckState.Unchecked)
                else:
                    item.setFlags(flags)
            def checked(item):
                if item.column()==0:
                    ident=apps[item.row()]['id']
                    selected.add(ident) if item.checkState()==Qt.CheckState.Checked else selected.discard(ident)
            t.itemChanged.connect(checked)
            t.cellDoubleClicked.connect(lambda r,c:self.application_dialog(apps[r]) if c else None)
            layout.addWidget(t)
            actions=QWidget(); row=box(actions,horizontal=True)
            def all_pending():
                for i,a in enumerate(apps):
                    if a['status'] == 'submitted':
                        t.item(i,0).setCheckState(Qt.CheckState.Checked)
            row.addWidget(button('Zaznacz oczekujące',all_pending,secondary=True))
            row.addWidget(button('Zatwierdź zaznaczone…',lambda:self.batch_dialog(
                'verify',[a['id'] for a in apps if a['id'] in selected and a['status'] == 'submitted']),secondary=True))
            row.addWidget(button('Otwórz zgłoszenie',lambda:self.application_dialog(apps[t.currentRow()]) if t.currentRow()>=0 else None))
            layout.addWidget(actions)
        for item in [status,mode]: item.currentIndexChanged.connect(render)
        search.textChanged.connect(render)
        render()
        actions=box(horizontal=True)
        actions.addWidget(button('Eksport przyjętych',self.export,secondary=True))
        self.content.addLayout(actions)

    def page_ranking(self):
        self.title('Ranking na żywo', 'Wybierz ofertę, aby zobaczyć bieżącą punktację, granicę przyjęcia i stan weryfikacji.')
        saved = self.filters.get('ranking', {})
        search = QLineEdit(saved.get('search', ''))
        search.setPlaceholderText('Szukaj kierunku…')
        search.setAccessibleName('Szukaj kierunku w rankingu')
        faculty = combo([('Wszystkie wydziały', '')] + [(f['code'], f['code']) for f in self.data['faculties']], 'Wydział')
        degree = combo([('Wszystkie stopnie', '')] + DEGREES, 'Stopień studiów')
        mode = combo([('Wszystkie tryby', ''), ('Stacjonarne', 'S'), ('Niestacjonarne', 'N')], 'Tryb studiów')
        controls = {'faculty': faculty, 'degree': degree, 'mode': mode}
        filters = box(horizontal=True)
        filters.addWidget(search, 2)
        for name, control in controls.items():
            control.setCurrentIndex(max(0, control.findData(saved.get(name))))
            filters.addWidget(control, 1)
        self.content.addLayout(filters)

        metrics = box(horizontal=True)
        for title, key in [('Złożone zgłoszenia', 'applications'), ('Do weryfikacji', 'pending'), ('Potwierdzone miejsca', 'confirmed')]:
            panel, metric = card(13)
            metric.addWidget(label(self.data['insights'][key], 25, NAVY, True))
            metric.addWidget(label(title, 12, MUTED, wrap=True))
            metrics.addWidget(panel, 1)
        self.content.addLayout(metrics)
        result_count = label('', 13, MUTED)
        self.content.addWidget(result_count)
        grid = table(['Kierunek', 'Wydział', 'Stopień', 'Tryb', 'Tura', 'Zgłoszenia'], [])
        grid.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        grid.setMinimumHeight(340)
        self.content.addWidget(grid, 1)
        visible = []
        actions = box(horizontal=True)
        live = button('Otwórz bieżący ranking', lambda: open_selected(True))
        published = button('Otwórz opublikowane listy', lambda: open_selected(False), secondary=True)
        actions.addStretch()
        actions.addWidget(published)
        actions.addWidget(live)
        self.content.addLayout(actions)

        def selected_offer():
            row = grid.currentRow()
            return visible[row] if 0 <= row < len(visible) else None

        def selection_changed():
            offer = selected_offer()
            live.setEnabled(bool(offer and offer['round'] and not offer['campaign_closed']))
            published.setEnabled(bool(offer))
            self.filters['ranking']['selected'] = offer['id'] if offer else None

        def open_selected(is_live):
            offer = selected_offer()
            if offer:
                if is_live and live.isEnabled():
                    self.ranking_dialog(offer)
                else:
                    self.publication_dialog(offer)

        def render():
            previous = self.filters.get('ranking', {}).get('selected')
            state = {key: control.currentData() for key, control in controls.items()}
            self.filters['ranking'] = {**state, 'search': search.text()}
            totals = self.data['insights']['by_offer']
            visible[:] = sorted((o for o in self.offers
                                 if all(not value or o[key] == value for key, value in state.items())
                                 and search.text().strip().casefold() in o['name'].casefold()),
                                key=lambda o: (-totals.get(str(o['id']), 0), o['name'], o['degree'], o['mode']))
            grid.blockSignals(True)
            grid.clearContents()
            grid.setRowCount(len(visible))
            for i, item in enumerate(visible):
                values = [item['name'], item['faculty'], item['degree'], item['mode_label'], item['round'] or '—', totals.get(str(item['id']), 0)]
                for column, val in enumerate(values):
                    cell = QTableWidgetItem(str(val))
                    cell.setToolTip(str(val))
                    grid.setItem(i, column, cell)
            if visible:
                row = next((i for i, offer in enumerate(visible) if offer['id'] == previous), 0)
                grid.setCurrentCell(row, 0)
            grid.blockSignals(False)
            selection_changed()
            result_count.setText(f'Pasujące oferty: {len(visible)}' if visible else 'Brak ofert pasujących do filtrów.')

        grid.itemSelectionChanged.connect(selection_changed)
        grid.cellDoubleClicked.connect(lambda *_: open_selected(live.isEnabled()))
        search.textChanged.connect(render)
        for control in controls.values():
            control.currentIndexChanged.connect(render)
        render()

    def page_timeline(self):
        self.title('Rekrutacja krok po kroku','Zapisy → ogłoszenie wyników po weryfikacji → potwierdzenie miejsca. Wszystkie komputery korzystają z czasu serwera.')
        c=self.data['campaign']
        self.content.addWidget(chip('Czas rekrutacji: '+date(c['now'])))
        for (title,degree),color in zip(DEGREES,['#009EE3','#77A43F','#714696']):
            f,l=card()
            l.addWidget(label(title,22,color,True))
            for r in c['rounds']:
                if r['degree']==degree: l.addWidget(RoundTimeline(r,c['now'],color))
            self.content.addWidget(f)
        self.content.addWidget(label('Minimalną liczbę miejsc znajdziesz przy danej ofercie. Po zamknięciu naboru system potwierdzi uruchomione kierunki i rozpatrzy wnioski o akademik.',13,MUTED,wrap=True))

    def page_admin(self):
        self.title('Administracja','Edycje naboru, dostęp i kopie zapasowe.')
        c=self.data['campaign']; now=datetime.fromisoformat(c['now'].replace('Z','+00:00'))
        f,l=card(); l.addWidget(label('Następny etap rekrutacji',22,bold=True))
        def play(scenario):
            messages = {
                'planning': 'Ustawić zegar pustej edycji dzień przed rozpoczęciem zapisów i przejść do konfiguracji kierunków?',
                'step': 'Rozpatrzyć dokumenty demo, opublikować gotowe wyniki i potwierdzić miejsca kont demo w najbliższym etapie?',
                'final': 'Przeprowadzić pozostałe etapy dla kandydatów demo aż do decyzji o uruchomieniu kierunków?',
                'populate': 'Dodać do pustej edycji kandydatów, zdjęcia i dokumenty demonstracyjne?',
                'ready': 'Rozpatrzyć oczekujące zgłoszenia kandydatów demo według scenariusza?',
            }
            if QMessageBox.question(self,'Symulacja naboru',messages[scenario]) == QMessageBox.StandardButton.Yes:
                def done(result):
                    if scenario == 'planning':
                        self.current = 'catalog'
                    QMessageBox.information(self,'Scenariusz',result['message'])
                self.mutate({'action':'demo_scenario','campaign_id':c['id'],'scenario':scenario}, done=done)
        milestones={}
        for r in c['rounds']:
            for key in ['start','application_end','end']:
                moment=r[key]
                if datetime.fromisoformat(moment.replace('Z','+00:00'))>now:
                    milestones.setdefault(moment,[]).append((r['degree'],r['number'],key))
        names = {'I': 'I stopień', 'II': 'II stopień', 'PG': 'Podyplomowe'}
        values = []
        for moment,events in sorted(milestones.items()):
            grouped = {}
            for degree, number, event in sorted(events):
                grouped.setdefault((number, event), []).append(names[degree])
            labels = {'start': 'otwarcie zapisów', 'application_end': 'koniec zapisów', 'end': 'koniec potwierdzeń'}
            descriptions = [f"{' i '.join(degrees)} · tura {number} · {labels[event]}"
                            for (number, event), degrees in sorted(grouped.items())]
            values.append((f"{date(moment)} · " + ('Koniec naboru' if moment == c['end'] else '  |  '.join(descriptions)), moment))
        if c['demo'] and values and not c['closed']:
            l.addWidget(label(values[0][0],15,NAVY,True,True))
            l.addWidget(label('W trybie automatycznym serwer ocenia dokumenty demo, publikuje listy i potwierdza miejsca w odpowiednich terminach.',13,MUTED,wrap=True))
            l.addWidget(button('Wykonaj następny etap',lambda:play('step')))
            l.addWidget(label('Ustawienie zegara naboru',13,MUTED,True))
            target=combo(values, 'Etap naboru')
            row=box(horizontal=True)
            row.addWidget(target, 1)
            def advance():
                if QMessageBox.question(self,'Zmiana etapu','Przesunąć wspólny zegar rekrutacji? Potwierdzenia, których termin minie, wygasną.')==QMessageBox.StandardButton.Yes:
                    self.mutate({'action':'clock','campaign_id':c['id'],'target':target.currentData()})
            row.addWidget(button('Ustaw zegar',advance,secondary=True))
            l.addLayout(row)
            l.addWidget(label('Tryb ręczny wymaga publikacji gotowych list w zakładce „Kierunki i listy”.',12,MUTED,wrap=True))
        elif not c['closed']:
            l.addWidget(label(values[0][0] if values else 'Wszystkie terminy upłynęły.',15,NAVY,True,True))
        if c['closed']:
            l.addWidget(label('Nabór zakończony. Wyniki tej edycji są dostępne w archiwum.',14,MUTED,wrap=True))
            def restart():
                if QMessageBox.question(self,'Nowa edycja','Rozpocząć nową edycję z tymi samymi kierunkami? Obecne wyniki i zgłoszenia pozostaną w archiwum.')==QMessageBox.StandardButton.Yes:
                    self.mutate({'action':'restart','campaign_id':c['id']},done=lambda r:setattr(self,'campaign_id',None))
            l.addWidget(button('Rozpocznij nową edycję rekrutacji',restart))
        self.content.addWidget(f)
        if c['demo'] and not c['closed']:
            f,l=card()
            l.addWidget(label('Symulacja naboru',20,bold=True))
            if not c['scenario'] and not self.data['applications']:
                l.addWidget(button('Zaplanuj ofertę przed pierwszą turą',lambda:play('planning'),secondary=True))
                l.addWidget(button('Dodaj kandydatów do pustej edycji',lambda:play('populate'),secondary=True))
            l.addWidget(button('Rozpatrz zgłoszenia przykładowe',lambda:play('ready'),secondary=True))
            l.addWidget(button('Odtwórz nabór do ślubowania',lambda:play('final'),secondary=True))
            self.content.addWidget(f)
        if self.connection_info:
            f,l=card(); l.addWidget(label('Połączenie zespołu',20,bold=True))
            mode=self.connection_info['mode']
            if mode=='host':
                hosts=[h for h in self.connection_info['addresses'] if h not in ['localhost','127.0.0.1']]
                address=combo([(f"https://{h}:{self.connection_info['port']}",h) for h in hosts]); l.addWidget(address)
                def export_profile():
                    from networking import connection_profile
                    path,_=QFileDialog.getSaveFileName(self,'Przekaż plik innym komputerom','Polaczenie-RekrutacjaPK.json','JSON (*.json)')
                    if path: Path(path).write_text(json.dumps(connection_profile(address.currentData(),self.connection_info['port']),ensure_ascii=False,indent=2),'utf-8')
                l.addWidget(button('Zapisz plik połączenia dla klientów',export_profile,secondary=True))
                l.addWidget(label('Wybierz adres Wi-Fi / LAN tego laptopa. Drugi komputer importuje plik w ekranie startowym. Serwer musi pozostać włączony. Zapora powinna dopuszczać port aplikacji w sieci prywatnej; PostgreSQL jest dostępny tylko lokalnie.',13,MUTED,wrap=True))
            else:
                l.addWidget(label('Klient połączony z '+self.connection_info.get('url','') if mode=='client' else 'Tryb lokalny. Aby połączyć inne komputery, przy kolejnym uruchomieniu wybierz „Serwer dla zespołu”.',13,MUTED,wrap=True))
            self.content.addWidget(f)
        f,l=card(); l.addWidget(label('Dostęp i kopie zapasowe',20,bold=True))
        users=combo([(u['email']+' • '+u['role_label'],u['id']) for u in self.data['users']])
        roles=combo([('Kandydat','candidate'),('Komisja','commission'),('Administrator','admin')])
        row=box(horizontal=True); row.addWidget(users,2); row.addWidget(roles,1)
        row.addWidget(button('Zmień rolę',lambda:self.mutate({'action':'role','user_id':users.currentData(),'role':roles.currentData()})))
        l.addLayout(row); l.addWidget(button('Utwórz kopię bazy i dokumentów',self.backup,secondary=True)); self.content.addWidget(f)
        events=self.data.get('audit',[])
        t=table(['Czas','Operacja','Wykonawca','Obiekt'],[[date(a['created_at']),a['action'],a['actor__email'] or 'System',a['entity']] for a in events],1)
        t.setMinimumHeight(320); self.content.addWidget(t)

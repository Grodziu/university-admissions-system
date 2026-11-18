from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QListWidget, QListWidgetItem, QWidget

from .widgets import MUTED, NAVY, box, field, label


def checked_list(values, existing):
    choices = QListWidget()
    choices.setMinimumHeight(145)
    choices.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    choices.setStyleSheet('QListWidget { background:white; border:1px solid #CCD7E5; border-radius:7px; } QListWidget::item { padding:5px; }')
    for value in values:
        row = QListWidgetItem(value, choices)
        row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        row.setCheckState(Qt.CheckState.Checked if value in existing else Qt.CheckState.Unchecked)
    return choices


def checked_values(choices):
    rows = (choices.item(i) for i in range(choices.count()))
    return [row.text() for row in rows if row.checkState() == Qt.CheckState.Checked]


class OfferTerms(QWidget):
    def __init__(self, data, offer=None):
        super().__init__()
        existing = offer or {}
        form = box(self)
        limits = box(horizontal=True)
        self.capacity = self._input(limits, 'Limit miejsc', existing.get('capacity', 30))
        self.minimum = self._input(limits, 'Minimum uruchomienia', existing.get('minimum', 20))
        self.fee = self._input(limits, 'Opłata rekrutacyjna w zł', existing.get('fee', 85))
        form.addLayout(limits)
        self.tuition_row = QWidget()
        self.tuition = field(box(self.tuition_row, spacing=5), 'Czesne za semestr w zł', existing.get('tuition_per_semester') or '')
        form.addWidget(self.tuition_row)

        self.require_portfolio = QCheckBox('Wymagaj portfolio')
        self.require_portfolio.setChecked(existing.get('portfolio_required', False))
        form.addWidget(self.require_portfolio)
        self.portfolio_bonus = QCheckBox('Wyróżnione portfolio podnosi P₂ do 100')
        self.portfolio_bonus.setChecked(existing.get('portfolio_bonus', False))
        form.addWidget(self.portfolio_bonus)

        self.criteria = QWidget()
        criteria = box(self.criteria)
        criteria.addWidget(label('Przedmioty i kwalifikacje uwzględniane w rankingu', 15, NAVY, True, True))
        row = box(horizontal=True)
        self.subjects = checked_list(data['subjects'], existing.get('subjects', ['matematyka']))
        self.professions = checked_list(data['professions'], existing.get('professions', []))
        for title, control in [('Rozszerzenia maturalne', self.subjects), ('Kwalifikacje technika', self.professions)]:
            column = box(spacing=5)
            column.addWidget(label(title, 12, MUTED, True, True))
            control.setAccessibleName(title)
            column.addWidget(control)
            row.addLayout(column, 1)
        criteria.addLayout(row)
        form.addWidget(self.criteria)

    @staticmethod
    def _input(row, title, value):
        column = box(spacing=5)
        control = field(column, title, value)
        row.addLayout(column, 1)
        return control

    def set_variant(self, degree, mode):
        self.degree = degree
        self.paid = mode == 'N' or degree == 'PG'
        self.tuition_row.setVisible(self.paid)
        self.criteria.setVisible(degree == 'I')
        self.portfolio_bonus.setVisible(degree == 'I')

    def values(self):
        return {'capacity': self.capacity.text(), 'minimum': self.minimum.text(), 'fee': self.fee.text().replace(',', '.'),
                'tuition': self.tuition.text().replace(',', '.') if self.paid else None,
                'portfolio_required': self.require_portfolio.isChecked(),
                'portfolio_bonus': self.degree == 'I' and self.portfolio_bonus.isChecked(),
                'subjects': checked_values(self.subjects), 'professions': checked_values(self.professions)}

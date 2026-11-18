"""Pure, deterministic admission policies. No database or UI dependencies."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


class RuleError(ValueError):
    pass


def number(value, minimum=0, maximum=100):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise RuleError('Wpisz poprawną liczbę.')
    if not result.is_finite() or not Decimal(str(minimum)) <= result <= Decimal(str(maximum)):
        raise RuleError(f'Wartość musi należeć do zakresu {minimum}–{maximum}.')
    if result != result.quantize(Decimal('.01')):
        raise RuleError('Dopuszczalne są najwyżej dwa miejsca po przecinku.')
    return result


@dataclass(frozen=True)
class Result:
    score: Decimal | None
    explanation: dict


class AdmissionStrategy(ABC):
    @abstractmethod
    def calculate(self, data: dict) -> Result:
        raise NotImplementedError


class BachelorStrategy(AdmissionStrategy):
    def calculate(self, data):
        m = number(data.get('M'))
        p1, p2 = number(data.get('P1')), number(data.get('P2', 0))
        if p2 > p1:
            p1, p2 = p2, p1
        # A portfolio improves the weaker component AFTER the normal ordering.
        original_p2 = p2
        if data.get('excellent_portfolio'):
            p2 = Decimal(100)
        bonus = number(data.get('bonus_points', 50 if data.get('bonus_approved') else 0), 0, 50)
        if bonus != int(bonus):
            raise RuleError('Premia musi być całkowitą liczbą punktów od 0 do 50.')
        raw = 2 * m + 6 * p1 + 2 * p2 + bonus
        score = min(Decimal(1000), raw).quantize(Decimal('.01'))
        return Result(score, {'policy': 'WR ' + data.get('rule_version', '2027.2'), 'M': str(m), 'P1': str(p1), 'P2': str(p2),
                             'P2_before_portfolio': str(original_p2), 'D': str(bonus),
                             'uncapped': str(raw), 'score': str(score), 'cap': 1000,
                             'formula': 'min(1000, 2 × M + 6 × P1 + 2 × P2 + D)'})


class MasterStrategy(AdmissionStrategy):
    def calculate(self, data):
        score = number(data.get('average'), 2, 5)
        return Result(score, {'policy': 'Średnia I stopnia 2027.1', 'average': str(score), 'score': str(score)})


class PostgraduateStrategy(AdmissionStrategy):
    def calculate(self, data):
        if not data.get('diploma'):
            raise RuleError('Wymagany jest dyplom ukończenia co najmniej studiów I stopnia.')
        return Result(None, {'policy': 'Kolejność kompletnych zgłoszeń 2027.1', 'submitted_at': data.get('submitted_at')})


STRATEGIES = {'I': BachelorStrategy(), 'II': MasterStrategy(), 'PG': PostgraduateStrategy()}


def select_with_ties(rows, capacity, degree):
    """rows = (stable id, Result, submitted_at). No point ties are discarded."""
    if degree == 'PG':
        ordered = sorted(rows, key=lambda r: (r[2], r[0]))
        return ordered, {r[0] for r in ordered[:max(0, capacity)]}
    ordered = sorted(rows, key=lambda r: (-r[1].score, r[0]))
    if capacity <= 0:
        return ordered, set()
    cutoff = ordered[min(capacity, len(ordered)) - 1][1].score if ordered else None
    return ordered, {r[0] for r in ordered if r[1].score >= cutoff}

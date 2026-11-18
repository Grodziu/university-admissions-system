"""Format and checksum validation for the candidate's PESEL."""
import re
from datetime import date

from .domain import RuleError


def check_digit(digits):
    weights = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    return str(-sum(int(digit) * weight for digit, weight in zip(digits, weights)) % 10)


def normalize_pesel(value):
    pesel = str(value).strip()
    if not re.fullmatch(r'[0-9]{11}', pesel):
        raise RuleError('PESEL powinien mieć dokładnie 11 cyfr.')
    encoded_month = int(pesel[2:4])
    century = {0: 1900, 20: 2000, 40: 2100, 60: 2200, 80: 1800}.get(encoded_month // 20 * 20)
    try:
        date(century + int(pesel[:2]), encoded_month % 20, int(pesel[4:6]))
    except (TypeError, ValueError):
        raise RuleError('Data zakodowana w numerze PESEL jest niepoprawna.') from None
    if pesel[-1] != check_digit(pesel[:10]):
        raise RuleError('Cyfra kontrolna numeru PESEL się nie zgadza.')
    return pesel


def demo_pesel(serial):
    # Format-valid fixture with a future birth date. Never use a registrable identity.
    day, suffix = divmod(serial, 10000)
    fixture_date = date.fromordinal(date(2290, 1, 1).toordinal() + day)
    digits = f'{fixture_date.year % 100:02}{fixture_date.month + 60:02}{fixture_date.day:02}{suffix:04}'
    return digits + check_digit(digits)

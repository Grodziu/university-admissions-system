"""Illustrative tuition for the project's fictional admission editions."""

PART_TIME = {'WA': (4200, 4500), 'WIiM': (3200, 3500), 'WIEiK': (3300, 3700),
             'WILiT': (3400, 3800), 'WIMiF': (3200, 3600), 'WIŚiE': (3200, 3500),
             'WIiTCh': (3300, 3700), 'WM': (3400, 3800)}
POSTGRADUATE = {'WA': 3600, 'WIiM': 3100, 'WIEiK': 3900, 'WILiT': 2800, 'WIMiF': 4200,
                'WIŚiE': 2600, 'WIiTCh': 2900, 'WM': 3300}


def demo_tuition(faculty, degree, mode):
    if degree == 'PG':
        return POSTGRADUATE.get(faculty, 3000)
    return PART_TIME.get(faculty, (3200, 3600))[degree == 'II'] if mode == 'N' else None

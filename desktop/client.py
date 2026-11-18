from pathlib import Path
import requests
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class ApiError(Exception):
    pass


def message(data):
    if isinstance(data, list):
        return '\n'.join(message(v) for v in data)
    if isinstance(data, dict):
        return '\n'.join(message(v) for v in data.values())
    return str(data)


class Client:
    def __init__(self, base_url, verify=True):
        self.base_url = base_url
        self.verify = verify
        self.token = ''

    def request(self, path, data=None, file=None, binary=False):
        token = self.token
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        try:
            kwargs = {'headers': headers, 'timeout': (4, 40), 'verify': self.verify, 'allow_redirects': False}
            with requests.Session() as session:
                session.trust_env = False
                if file:
                    with Path(file).open('rb') as source:
                        response = session.post(self.base_url + path, data=data,
                            files={'file': (Path(file).name, source)}, **kwargs)
                elif data is not None:
                    response = session.post(self.base_url + path, json=data, **kwargs)
                else:
                    response = session.get(self.base_url + path, **kwargs)
        except requests.exceptions.SSLError:
            raise ApiError('Nie udało się potwierdzić tożsamości serwera. Zaimportuj aktualny plik połączenia otrzymany od administratora i sprawdź datę komputera.')
        except requests.RequestException:
            raise ApiError('Brak połączenia z serwerem. Sprawdź sieć i czy laptop serwera nadal działa. Zapisane dane pozostają na serwerze; odśwież widok przed ponowieniem operacji.')
        if not 200 <= response.status_code < 300:
            if response.status_code == 401 and self.token == token:
                self.token = ''
            try:
                detail = message(response.json())
            except ValueError:
                detail = 'Serwer nie mógł wykonać operacji. Jeśli problem się powtarza, zgłoś go administratorowi.'
            raise ApiError(detail)
        return response.content if binary else response.json()


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = TaskSignals()

    def run(self):
        try:
            self.signals.done.emit(self.function())
        except Exception as error:
            self.signals.failed.emit(str(error))


def asynchronously(function, done, failed):
    task = Task(function)
    task.signals.done.connect(done)
    task.signals.failed.connect(failed)
    QThreadPool.globalInstance().start(task)
    return task

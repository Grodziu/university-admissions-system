"""Build a Windows x64 folder that includes Python, Qt and PostgreSQL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import zipfile
from admissions.version import RELEASE
from tools.package_source import public_assets, public_files

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
release = ROOT / 'dist' / RELEASE
build = ROOT / 'build' / RELEASE
release.mkdir(parents=True, exist_ok=True)
dest = release / 'RekrutacjaPK'
package_only = '--package-only' in sys.argv
if package_only and not (dest / 'RekrutacjaPK.exe').exists():
    raise SystemExit('Brak zbudowanej aplikacji. Najpierw uruchom pełne budowanie.')
if not package_only and (dest / 'runtime').exists():
    raise SystemExit(f'Katalog {dest} zawiera dane użytkownika. Zachowaj jego runtime poza katalogiem budowania przed przebudową.')
if not (ROOT / 'vendor/pgsql/bin/postgres.exe').exists():
    raise SystemExit('Najpierw przygotuj vendor/pgsql zgodnie z README.')
env = dict(os.environ, DJANGO_SETTINGS_MODULE='server.settings')
# Build tools may inject Poppler/other native libraries into PATH. Qt's Windows ICU
# dependency must resolve to Windows, not to another application's incompatible ICU.
windows = Path(os.environ.get('SystemRoot', 'C:/Windows'))
env['PATH'] = os.pathsep.join(str(p) for p in [Path(sys.executable).parent, Path(sys.base_prefix), windows/'System32', windows])
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed',
           '--distpath', str(release), '--workpath', str(build / 'work'), '--specpath', str(build),
           '--name', 'RekrutacjaPK', '--icon', str(ROOT / 'assets' / 'pk.ico'),
           '--hidden-import', 'server.settings', '--hidden-import', 'server.urls',
           '--additional-hooks-dir', str(ROOT / 'tools' / 'pyinstaller'),
           '--collect-submodules', 'admissions', '--collect-submodules', 'rest_framework',
           '--collect-submodules', 'database',
           '--exclude-module', 'PySide6.QtWebEngineCore', '--exclude-module', 'PySide6.QtWebEngineWidgets',
           '--exclude-module', 'tkinter']
for source in public_assets():
    command.extend(['--add-data', f'{source};{source.parent.relative_to(ROOT)}'])
command.append(str(ROOT / 'start.py'))
if not package_only:
    subprocess.run(command, check=True, env=env)
if not package_only:
    shutil.copytree(ROOT / 'vendor/pgsql', dest / 'vendor/pgsql', dirs_exist_ok=True)
elif not (dest / 'vendor/pgsql/bin/postgres.exe').exists():
    raise SystemExit('Niekompletny pakiet: brak PostgreSQL. Uruchom pełne budowanie.')
for filename in ['README.md', 'WYMAGANIA.md', 'THIRD-PARTY.md', 'Uruchom.bat']:
    shutil.copy2(ROOT / filename, dest / filename)
for source in public_files():
    relative = source.relative_to(ROOT)
    if relative.parts[0] in {'architecture', 'database'}:
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
# Windows supplies the ICU ABI used by this Qt build. A foreign icuuc.dll in
# _internal shadows it and causes "procedure not found" before any window opens.
if (dest / '_internal/icuuc.dll').exists():
    raise RuntimeError('Nieprawidłowa biblioteka ICU w pakiecie. Sprawdź PATH środowiska budowania.')
licenses = dest / 'licenses'
licenses.mkdir(exist_ok=True)
import importlib.metadata
for distribution in importlib.metadata.distributions():
    for file in distribution.files or []:
        if any(word in str(file).lower() for word in ['/licenses/', '/license', '/copying']):
            source = distribution.locate_file(file)
            if source.is_file():
                target = licenses / distribution.metadata['Name'] / file.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
archive = release / 'RekrutacjaPK-Windows-x64.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for file in dest.rglob('*'):
        if (file.is_file() and not {'runtime', 'results'} & set(file.relative_to(dest).parts)
                and file.name not in {'README-Marcin.md', 'UZASADNIENIA-I-DOWODY.md'}):
            z.write(file, file.relative_to(dest.parent))
print('Pakiet przenośny:', archive)

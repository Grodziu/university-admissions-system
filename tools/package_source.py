"""Export reviewed source files, assets and technical documentation."""
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ASSETS = (
    'pk.ico', 'pk.png', 'pk.webp', 'kampus-pk.jpg', 'makieta.jpg',
    'laboratorium.jpg', 'elektronika.jpg', 'energia.jpg', 'materialy.jpg',
    'most.jpg', 'pracownia-komputerowa.jpg', 'robotyka.jpg',
    'brands/facebook.png', 'brands/instagram.png', 'brands/spotify.png', 'brands/youtube.png',
    'krakow/bulwary.jpg', 'krakow/kazimierz.jpg', 'krakow/kopiec.jpg',
    'krakow/panorama.jpg', 'krakow/rynek.jpg', 'krakow/wawel.jpg',
    'krakow/zakrzowek.jpg', 'krakow/credits.json',
    'licenses/Python-LICENSE.txt',
    'maps/czyzyny-osm.json', 'maps/granice-natural-earth.json', 'maps/krakow-osm.json',
    'maps/region-natural-earth.json',
)
TOP_FILES = (
    '.gitignore', 'README.md', 'WYMAGANIA.md', 'THIRD-PARTY.md', 'requirements.txt',
    'requirements-lock.txt', 'start.py', 'portable.py', 'networking.py', 'backups.py',
    'manage.py', 'build_portable.py', 'Uruchom.bat',
)
SOURCE_TYPES = {
    'admissions': {'.py'}, 'desktop': {'.py'}, 'server': {'.py'}, 'tools': {'.py'},
    'database': {'.py', '.md', '.sql', '.mmd', '.dbml', '.puml', '.json'},
    'architecture': {'.md', '.puml'},
}
PRIVATE_PARTS = {
    'private', 'raporty-prywatne', 'sources', 'validation', 'runtime', 'results',
    'tmp', 'backups', 'dist', 'build', 'vendor', '__pycache__',
}
PRIVATE_NAMES = {'readme-marcin.md', 'uzasadnienia-i-dowody.md', 'local.json'}


def public_assets():
    for name in PUBLIC_ASSETS:
        source = ROOT / 'assets' / name
        if not source.is_file() or source.is_symlink() or source.resolve() != source:
            raise ValueError(f'Brak zatwierdzonego zasobu w projekcie: {name}')
        yield source


def public_files():
    yield from (ROOT / name for name in TOP_FILES)
    yield from public_assets()
    for folder, extensions in SOURCE_TYPES.items():
        for source in sorted((ROOT / folder).rglob('*')):
            parts = {part.lower() for part in source.relative_to(ROOT).parts}
            if (source.suffix.lower() in extensions and source.is_file()
                    and not source.is_symlink() and source.resolve() == source
                    and not parts & PRIVATE_PARTS
                    and source.name.lower() not in PRIVATE_NAMES
                    and not any(part.startswith('.') for part in parts)):
                yield source


def main():
    sys.path.insert(0, str(ROOT))
    from admissions.version import RELEASE

    dest = ROOT / 'dist' / RELEASE
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / 'RekrutacjaPK-zrodla.zip'
    github = dest / 'RekrutacjaPK-GitHub'
    export_directory = '--github-dir' in sys.argv
    if export_directory and github.exists():
        raise SystemExit(f'Katalog eksportu już istnieje: {github}. Wybierz nowy katalog wydania.')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for source in public_files():
            relative = source.relative_to(ROOT)
            bundle.write(source, Path('RekrutacjaPK-zrodla') / relative)
            if export_directory:
                target = github / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    print(archive)
    if export_directory:
        print(github)


if __name__ == '__main__':
    main()

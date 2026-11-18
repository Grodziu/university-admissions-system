from pathlib import Path
import sys
import pefile

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project))
from admissions.version import RELEASE

root = project / 'dist' / RELEASE / 'RekrutacjaPK' / '_internal'
dirs = [root / 'PySide6', root / 'shiboken6', root, Path('C:/Windows/System32')]
exports = {}
def symbols(path):
    if path not in exports:
        pe = pefile.PE(str(path), fast_load=True, max_symbol_exports=100000)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
        exports[path] = {s.name for s in getattr(pe, 'DIRECTORY_ENTRY_EXPORT', type('Empty', (), {'symbols': []})).symbols}
        pe.close()
    return exports[path]
for path in [root/'PySide6'/n for n in ['QtWidgets.pyd', 'pyside6.abi3.dll', 'Qt6Widgets.dll', 'Qt6Gui.dll', 'Qt6Core.dll']]:
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
    for dep in pe.DIRECTORY_ENTRY_IMPORT:
        name = dep.dll.decode()
        if name.lower().startswith(('api-ms-', 'ext-ms-')):
            continue
        target = next((d/name for d in dirs if (d/name).exists()), None)
        if not target:
            print(path.name, 'unresolved DLL:', name)
            continue
        missing = [f.name.decode() for f in dep.imports if f.name and f.name not in symbols(target)]
        if missing:
            print(path.name, 'missing symbols in', target, missing[:15])
    pe.close()

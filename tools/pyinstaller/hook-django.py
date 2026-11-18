"""Bundle the Django components used by the standalone PostgreSQL application."""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = [
    'django.contrib.auth.apps',
    'django.contrib.auth.backends',
    'django.contrib.contenttypes.apps',
    'django.core.cache.backends.locmem',
    'django.core.mail.backends.smtp',
    'django.core.mail.backends.locmem',
    'django.core.management.commands.check',
    'django.core.management.commands.migrate',
    'django.core.management.commands.test',
    'django.middleware.security',
    'django.template.backends.django',
    'django.test.runner',
]
for package in ('django.db.backends.postgresql', 'django.contrib.auth.migrations',
                'django.contrib.contenttypes.migrations', 'django.template', 'django.templatetags'):
    hiddenimports.extend(collect_submodules(package))

# Management and migration loaders discover commands and files on disk.
datas = collect_data_files('django', include_py_files=True, includes=[
    'conf/locale/pl/**', 'contrib/auth/locale/pl/**',
    'contrib/auth/common-passwords.txt.gz', 'views/templates/**',
    'contrib/auth/migrations/*.py', 'contrib/contenttypes/migrations/*.py',
    'core/management/commands/check.py', 'core/management/commands/migrate.py',
    'core/management/commands/test.py',
])
datas += collect_data_files('admissions', include_py_files=True, includes=[
    'migrations/*.py', 'management/commands/seed_demo.py', 'tests.py', 'test_*.py',
])

"""Export actual models and verify the lossless 6NF reference decomposition.

The generated schema is a read-only reference snapshot. Production constraints and
writes continue to be enforced by the operational schema and its migrations.
"""
from pathlib import Path
import json
import re
from psycopg import sql


def name(table, column=None):
    import hashlib
    raw = table + ('__' + column if column else '__anchor')
    return raw if len(raw) <= 63 else raw[:52] + '_' + hashlib.sha256(raw.encode()).hexdigest()[:10]


def inventory(conn):
    tables = []
    for table, in conn.execute("""
        SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname
    """):
        columns = conn.execute("""
            SELECT a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull
            FROM pg_attribute a
            WHERE a.attrelid=%s::regclass AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum
        """, [table]).fetchall()
        constraints = conn.execute("""
            SELECT conname,contype,pg_get_constraintdef(oid),
                   ARRAY(SELECT attname FROM unnest(conkey) WITH ORDINALITY k(num,ord)
                         JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.num ORDER BY ord)
            FROM pg_constraint c WHERE conrelid=%s::regclass ORDER BY conname
        """, [table]).fetchall()
        key = next(row[3] for row in constraints if row[1] == 'p')
        if len(key) != 1:
            raise ValueError(f'Add a composite-anchor mapping for {table}: {key}')
        tables.append({'table': table, 'key': key[0],
            'columns': [{'name': c, 'type': t, 'required': n} for c, t, n in columns],
            'constraints': [{'name': c, 'kind': k, 'definition': d, 'columns': cols} for c, k, d, cols in constraints],
            'category': 'technical' if table.startswith(('auth_', 'django_')) else
                        'derived' if table == 'pk_offer_stats' else 'operational',
            'fd': f"{key[0]} -> " + ', '.join(c for c, _, _ in columns if c != key[0])})
    return describe_dependencies(tables)


def describe_dependencies(tables):
    for t in tables:
        required = {c['name'] for c in t['columns'] if c['required']}
        key_constraints = [c for c in t['constraints'] if c['kind'] in ('p', 'u')]
        t['candidate_keys'] = [c['columns'] for c in key_constraints if set(c['columns']) <= required]
        t['conditional_unique_keys'] = [c['columns'] for c in key_constraints if not set(c['columns']) <= required]
        t['functional_dependencies'] = [
            {'determinant': k, 'dependent': [c['name'] for c in t['columns'] if c['name'] not in k]}
            for k in t['candidate_keys']
        ]
        t['reference_6nf'] = {
            'anchor': [t['key']],
            'facts': [[t['key'], c['name']] for c in t['columns'] if c['name'] != t['key']],
            'lossless_basis': 'Each intersection is the primary key; an existence anchor preserves rows with absent optional facts.',
            'constraint_preservation': 'Alternative keys and multi-column CHECK constraints apply to the reconstructed relation; the reference schema is read-only.',
            'dependency_scope': 'Declared keys and domain dependencies; no FD inferred merely from sample equality.',
        }
    return tables


def reference_ddl(tables):
    # One existence anchor plus key -> value facts. Missing nullable facts reconstruct NULL.
    commands = ['CREATE SCHEMA nf6_reference;']
    for t in tables:
        table, key = t['table'], t['key']
        key_type = next(c['type'] for c in t['columns'] if c['name'] == key)
        anchor = f'nf6_reference."{name(table)}"'
        commands.append(f'CREATE TABLE {anchor} (entity_id {key_type} PRIMARY KEY);')
        expressions = [f'a.entity_id AS "{key}"']
        joins = []
        for i, c in enumerate(t['columns']):
            if c['name'] == key:
                continue
            fact = f'nf6_reference."{name(table, c["name"])}"'
            commands.append(f'CREATE TABLE {fact} (entity_id {key_type} PRIMARY KEY REFERENCES {anchor}(entity_id), value {c["type"]} NOT NULL);')
            expressions.append(f'f{i}.value AS "{c["name"]}"')
            joins.append(f'LEFT JOIN {fact} f{i} ON f{i}.entity_id=a.entity_id')
        # Column order is deliberately the same as in the operational relation.
        ordered = []
        for c in t['columns']:
            ordered.append(next(e for e in expressions if e.endswith(f'AS "{c["name"]}"')))
        commands.append(f'CREATE VIEW nf6_reference."{table}__reconstructed" AS SELECT ' +
                        ', '.join(ordered) + f' FROM {anchor} a ' + ' '.join(joins) + ';')
    commands.append('REVOKE ALL ON SCHEMA nf6_reference FROM PUBLIC;')
    return '\n'.join(commands) + '\n'


def export(conn, output, verify=True):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    tables = inventory(conn)
    (output / 'model-catalog.json').write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding='utf-8')
    ddl = reference_ddl(tables)
    (output / 'model-6nf.sql').write_text(
        '-- Model logiczny / odczytowy; uruchamiaj w pustej bazie demonstracyjnej.\n'
        '-- Nie zastępuje migracji aplikacji. Brak wiersza faktu opcjonalnego oznacza NULL.\n'
        '-- UNIQUE alternatywne, CHECK i reguły między relacjami: model-catalog.json.\n'
        '-- Przed udostępnieniem zapisu w takim wariancie trzeba egzekwować te ograniczenia\n'
        '-- na zrekonstruowanych relacjach; sam rozkład nie zachowuje ich lokalnie.\n' + ddl, encoding='utf-8')
    er = ['erDiagram']
    dbml = ['// Aktualny model fizyczny. Kontakt jest osobnym widokiem zgodności.\n']
    for t in tables:
        table, key = t['table'], t['key']
        er += [f'    {table} {{']
        dbml += [f'Table {table} {{']
        for c in t['columns']:
            kind = 'PK' if c['name'] == key else 'FK' if any(k['kind'] == 'f' and c['name'] in k['columns'] for k in t['constraints']) else ''
            dtype = re.sub('[^A-Za-z0-9_]', '_', c['type']).strip('_')
            er.append(f'        {dtype} {c["name"]}' + (f' {kind}' if kind else ''))
            flags = ['pk'] if c['name'] == key else []
            if c['required']:
                flags.append('not null')
            dbml.append(f'  {c["name"]} "{c["type"]}"' + (' [' + ', '.join(flags) + ']' if flags else ''))
        er.append('    }')
        unique = [k for k in t['constraints'] if k['kind'] == 'u']
        if unique:
            dbml.append('  indexes {')
            dbml.extend('    (' + ', '.join(k['columns']) + ') [unique]' for k in unique)
            dbml.append('  }')
        dbml.append('}\n')
        for k in t['constraints']:
            if k['kind'] != 'f':
                continue
            target = re.search(r'REFERENCES (\w+)\((\w+)\)', k['definition'])
            if target:
                parent, field = target.groups()
                child_field = k['columns'][0]
                nullable = not next(c['required'] for c in t['columns'] if c['name'] == child_field)
                unique_fk = child_field == key or any(v['kind'] == 'u' and v['columns'] == [child_field] for v in t['constraints'])
                er.append(f'    {parent} ' + ('|o' if nullable else '||') + ('--o|' if unique_fk else '--o{') +
                          f' {table} : "{child_field}"')
                if unique_fk:
                    dbml.append(f'Ref: {parent}.{field} - {table}.{child_field}')
                else:
                    dbml.append(f'Ref: {table}.{child_field} > {parent}.{field}')
    (output / 'model.mmd').write_text('\n'.join(er) + '\n', encoding='utf-8')
    (output / 'model.dbml').write_text('\n'.join(dbml) + '\n', encoding='utf-8')
    from django.apps import apps
    classes = ['@startuml', 'hide methods', 'skinparam classAttributeIconSize 0', 'left to right direction',
               'title Rzeczywiste klasy modelu Django — atrybuty i związki']
    for model in apps.get_app_config('admissions').get_models(include_auto_created=True):
        classes.append(f'class {model.__name__} ' + '{')
        for field in model._meta.local_fields:
            flags = ' <<PK>>' if field.primary_key else ''
            flags += ' <<optional>>' if field.null else ''
            classes.append(f'  {field.name}: {field.get_internal_type()}{flags}')
        classes.append('}')
        for field in model._meta.local_fields:
            if field.is_relation:
                multiplicity = '0..1' if field.null else '1'
                back = '0..1' if field.unique else '0..*'
                classes.append(f'{field.related_model.__name__} "{multiplicity}" -- "{back}" {model.__name__} : {field.name}')
    classes += ['note as N', 'CandidateContact = widok zgodności.', 'ContactAnchor + trzy fakty = fizyczna dekompozycja 6NF.',
                'OfferStats = projekcja utrzymywana przez wyzwalacz.', 'end note', '@enduml']
    (output / 'classes.puml').write_text('\n'.join(classes) + '\n', encoding='utf-8')
    checks = []
    if verify:
        with conn.transaction(force_rollback=True):
            conn.execute(ddl)
            for t in tables:
                table, key = t['table'], t['key']
                q = sql.Identifier
                conn.execute(sql.SQL('INSERT INTO nf6_reference.{} SELECT {} FROM public.{}').format(q(name(table)), q(key), q(table)))
                for c in t['columns']:
                    if c['name'] != key:
                        conn.execute(sql.SQL('INSERT INTO nf6_reference.{} SELECT {},{} FROM public.{} WHERE {} IS NOT NULL')
                            .format(q(name(table, c['name'])), q(key), q(c['name']), q(table), q(c['name'])))
                diff = conn.execute(sql.SQL('''SELECT count(*) FROM (
                    (TABLE public.{} EXCEPT ALL TABLE nf6_reference.{})
                    UNION ALL (TABLE nf6_reference.{} EXCEPT ALL TABLE public.{})
                ) difference''').format(q(table), q(table+'__reconstructed'), q(table+'__reconstructed'), q(table))).fetchone()[0]
                rows = conn.execute(sql.SQL('SELECT count(*) FROM public.{}').format(q(table))).fetchone()[0]
                checks.append({'table': table, 'rows': rows, 'difference_rows': diff,
                               'anchor': name(table), 'facts': len(t['columns'])-1})
                if diff:
                    raise AssertionError(f'Lossy decomposition: {table}')
    return {'tables': len(tables), 'facts': sum(len(t['columns'])-1 for t in tables),
            'checks': checks, 'reference_schema_persisted': False}

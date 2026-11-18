"""Normalization witnesses using actual project relations; no production writes."""
def run(conn):
    results = {}
    def difference(before, after):
        return conn.execute(f"""SELECT count(*) FROM (
            (({before}) EXCEPT ALL ({after})) UNION ALL (({after}) EXCEPT ALL ({before}))
        ) d""").fetchone()[0]

    exam = """SELECT e.user_id,u.last_name,e.subject,e.level,e.value
        FROM admissions_examresult e JOIN admissions_user u ON u.id=e.user_id"""
    before3 = """SELECT o.id offer_id,o.program_id,p.faculty_id,f.name faculty_name
        FROM admissions_offer o JOIN admissions_program p ON p.id=o.program_id
        JOIN admissions_faculty f ON f.id=p.faculty_id"""
    bcnf = """SELECT e.user_id,i.pesel,e.subject,e.level,e.value
        FROM admissions_examresult e JOIN admissions_candidateidentity i ON i.user_id=e.user_id"""
    with conn.transaction(force_rollback=True):
        conn.execute('CREATE TEMP TABLE nf_exam AS ' + exam)
        conn.execute('ALTER TABLE nf_exam ADD PRIMARY KEY(user_id,subject,level)')
        conn.execute('CREATE TEMP TABLE nf_user AS SELECT DISTINCT user_id,last_name FROM nf_exam')
        conn.execute('CREATE TEMP TABLE nf_result AS SELECT user_id,subject,level,value FROM nf_exam')
        results['1NF'] = {'atomic_relation': 'ExamResult(user,subject,level,value)',
            'unique_key': ['user_id','subject','level'],
            'rows': conn.execute('SELECT count(*) FROM nf_result').fetchone()[0],
            'unf': "string_agg(subject || ':' || value, ';') is a presentation of a repeating group, not canonical storage"}
        diff = difference('TABLE nf_exam', 'SELECT u.user_id,u.last_name,e.subject,e.level,e.value FROM nf_user u JOIN nf_result e USING(user_id)')
        assert diff == 0
        conn.execute('SAVEPOINT anomaly')
        conn.execute("""UPDATE nf_exam SET last_name=last_name || ' (bledna zmiana)'
            WHERE ctid=(SELECT a.ctid FROM nf_exam a WHERE 1 < (SELECT count(*) FROM nf_exam b WHERE b.user_id=a.user_id) LIMIT 1)""")
        broken = conn.execute('SELECT count(*) FROM (SELECT user_id FROM nf_exam GROUP BY user_id HAVING count(DISTINCT last_name)>1) d').fetchone()[0]
        assert broken > 0
        conn.execute('ROLLBACK TO SAVEPOINT anomaly')
        from psycopg.errors import NotNullViolation
        try:
            with conn.transaction():
                conn.execute("INSERT INTO nf_exam(user_id,last_name) SELECT id,last_name FROM admissions_user WHERE NOT EXISTS(SELECT 1 FROM nf_exam e WHERE e.user_id=admissions_user.id) LIMIT 1")
        except NotNullViolation:
            insertion_rejected = True
        else:
            raise AssertionError('Flattened relation unexpectedly stored a candidate without an exam key.')
        removed_user = conn.execute('SELECT user_id FROM nf_exam LIMIT 1').fetchone()[0]
        conn.execute('DELETE FROM nf_exam WHERE user_id=%s', [removed_user])
        surname_lost = not conn.execute('SELECT 1 FROM nf_exam WHERE user_id=%s', [removed_user]).fetchone()
        normalized_user_kept = bool(conn.execute('SELECT 1 FROM nf_user WHERE user_id=%s', [removed_user]).fetchone())
        assert surname_lost and normalized_user_kept
        conn.execute('ROLLBACK TO SAVEPOINT anomaly')
        results['2NF'] = {'fd': 'user_id -> last_name (proper part of the composite exam key)',
            'lossless_difference': diff, 'update_anomaly_users': broken, 'before_sql': exam,
            'insertion_without_exam_rejected': insertion_rejected,
            'deletion_loses_surname_in_flat_relation': surname_lost,
            'deletion_keeps_normalized_user': normalized_user_kept,
            'after_sql': 'SELECT u.user_id,u.last_name,e.subject,e.level,e.value FROM nf_user u JOIN nf_result e USING(user_id)',
            'insertion_anomaly': 'A candidate without an exam cannot be stored in the flattened relation without violating the exam key.',
            'deletion_anomaly': 'Deleting the last exam deletes the only stored surname of that candidate.'}

        conn.execute('CREATE TEMP TABLE nf_offer_flat AS '+before3)
        reconstructed3 = """SELECT a.offer_id,a.program_id,p.faculty_id,f.faculty_name
            FROM (SELECT DISTINCT offer_id,program_id FROM nf_offer_flat) a
            JOIN (SELECT DISTINCT program_id,faculty_id FROM nf_offer_flat) p USING(program_id)
            JOIN (SELECT DISTINCT faculty_id,faculty_name FROM nf_offer_flat) f USING(faculty_id)"""
        diff = difference('TABLE nf_offer_flat', reconstructed3)
        assert diff == 0
        results['3NF'] = {'key': ['offer_id'], 'fd': ['offer_id -> program_id','program_id -> faculty_id','faculty_id -> faculty_name'],
            'lossless_difference': diff, 'before_sql': before3, 'after_sql': reconstructed3}

        conn.execute('CREATE TEMP TABLE nf_bcnf AS '+bcnf)
        reconstructed_bcnf = """SELECT e.user_id,i.pesel,e.subject,e.level,e.value
            FROM (SELECT DISTINCT user_id,pesel FROM nf_bcnf) i
            JOIN (SELECT user_id,subject,level,value FROM nf_bcnf) e USING(user_id)"""
        diff = difference('TABLE nf_bcnf', reconstructed_bcnf)
        assert diff == 0
        results['BCNF'] = {'candidate_keys': [['user_id','subject','level'],['pesel','subject','level']],
            'fd': ['user_id -> pesel','pesel -> user_id','(user_id,subject,level) -> value'],
            'third_nf_reason': 'user_id and pesel are prime attributes; value depends on a candidate key.',
            'bcnf_violation': 'user_id -> pesel, while user_id is not a superkey of the exam relation.',
            'lossless_difference': diff, 'before_sql': bcnf, 'after_sql': reconstructed_bcnf}

        conn.execute("""CREATE TEMP TABLE nf_multiple AS
            SELECT s.offer_id,s.subject,p.name profession FROM admissions_allowedsubject s
            JOIN admissions_allowedprofession p ON p.offer_id=s.offer_id""")
        reconstructed4 = """SELECT s.offer_id,s.subject,p.profession
            FROM (SELECT DISTINCT offer_id,subject FROM nf_multiple) s
            JOIN (SELECT DISTINCT offer_id,profession FROM nf_multiple) p USING(offer_id)"""
        diff = difference('TABLE nf_multiple', reconstructed4)
        witness = conn.execute("""SELECT offer_id,count(DISTINCT subject),count(DISTINCT profession),count(*)
            FROM nf_multiple GROUP BY offer_id HAVING count(DISTINCT subject)>1 AND count(DISTINCT profession)>1
            ORDER BY offer_id LIMIT 1""").fetchone()
        assert diff == 0 and witness
        results['4NF'] = {'mvd': ['offer_id ->> subject','offer_id ->> profession'],
            'independence': 'The application defines separate eligibility lists, without subject/profession compatibility pairs.',
            'lossless_difference': diff, 'witness_offer_subjects_professions_product': witness}

        wrong = conn.execute("""SELECT count(*) FROM (
            SELECT o.offer_id,p.name FROM (SELECT DISTINCT offer_id FROM admissions_allowedprofession) o
            CROSS JOIN (SELECT DISTINCT name FROM admissions_allowedprofession) p
            EXCEPT SELECT offer_id,name FROM admissions_allowedprofession
        ) d""").fetchone()[0]
        assert wrong > 0
        results['5NF'] = {'relation': 'AllowedProfession(offer_id,name)', 'key': ['offer_id','name'],
            'invalid_unary_decomposition_extra_pairs': wrong,
            'reason': 'The pair is an irreducible fact. No three-way JD is asserted without a domain rule. The 4NF outputs are already in 5NF.'}

        diff = conn.execute("""SELECT count(*) FROM (
            (SELECT a.user_id,coalesce(p.value,'') phone,coalesce(l.value,'') portfolio_url,
                    coalesce(e.value,'') notification_email
             FROM admissions_contactanchor a LEFT JOIN admissions_candidatephone p USING(user_id)
             LEFT JOIN admissions_candidateportfolio l USING(user_id)
             LEFT JOIN admissions_candidatenotificationaddress e USING(user_id)
             EXCEPT ALL TABLE admissions_candidatecontact)
            UNION ALL
            (TABLE admissions_candidatecontact EXCEPT ALL
             SELECT a.user_id,coalesce(p.value,''),coalesce(l.value,''),coalesce(e.value,'')
             FROM admissions_contactanchor a LEFT JOIN admissions_candidatephone p USING(user_id)
             LEFT JOIN admissions_candidateportfolio l USING(user_id)
             LEFT JOIN admissions_candidatenotificationaddress e USING(user_id))
        ) d""").fetchone()[0]
        assert diff == 0
        results['6NF'] = {'before': 'CandidateContact(user_id,phone,portfolio_url,notification_email)',
            'after': ['ContactAnchor(user_id)','CandidatePhone(user_id,value)','CandidatePortfolio(user_id,value)',
                      'CandidateNotificationAddress(user_id,value)'],
            'jd': '*{(user_id,phone),(user_id,portfolio_url),(user_id,notification_email)}',
            'lossless_difference': diff,
            'physical_migration': '0011_contact_facts_6nf; absence is represented by missing optional fact, blank restored only at compatibility boundary.'}
        # DKNF is a constraint-based criterion, not another numbered NF.
        results['DKNF'] = {'local_example': 'AcademicAverage(user_id,value): key user_id, numeric domain 2..5.',
            'whole_model': False,
            'counterexample': 'An application payment approval must agree with the fee of its offer; this is not implied only by domains and keys.',
            'enforcement': 'pk_application_guard and service validation; the rules are retained rather than silently discarded.'}
    return results

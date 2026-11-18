"""Executable PostgreSQL counterparts; these do not claim Oracle object equivalence."""
def run(conn, rows=100000):
    with conn.transaction(force_rollback=True):
        conn.execute("""CREATE TEMP TABLE ix_example AS
            SELECT n AS id,n %% 200 AS offer_id,lpad(n::text,12,'0') AS reference
            FROM generate_series(1,%s) n""", [rows])
        conn.execute('CREATE INDEX ix_offer_btree ON ix_example(offer_id)')
        conn.execute('CREATE INDEX ix_reference_reverse_expression ON ix_example(reverse(reference))')
        conn.execute('CREATE INDEX ix_offer_without_dedup ON ix_example(offer_id) WITH(deduplicate_items=off)')
        conn.execute('ANALYZE ix_example')
        bitmap_query = 'SELECT * FROM ix_example WHERE offer_id=42 OR offer_id=43'
        bitmap = conn.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+bitmap_query).fetchone()[0][0]
        reverse_query = "SELECT id FROM ix_example WHERE reverse(reference)=reverse('000000000042')"
        reverse = conn.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+reverse_query).fetchone()[0][0]
        assert conn.execute(reverse_query).fetchall() == [(42,)]
        sizes = dict(conn.execute("""SELECT v.name,pg_relation_size(v.name::regclass)
          FROM (VALUES ('ix_offer_btree'),('ix_offer_without_dedup')) v(name)""").fetchall())
        conn.execute('CLUSTER ix_example USING ix_offer_btree')
        clustered = conn.execute("SELECT indisclustered FROM pg_index WHERE indexrelid='ix_offer_btree'::regclass").fetchone()[0]
        # The last physical tuple is a newly inserted smallest key: order was not maintained.
        conn.execute("INSERT INTO ix_example VALUES(-1,-1,'-00000000001')")
        last = conn.execute('SELECT offer_id FROM ix_example ORDER BY ctid DESC LIMIT 1').fetchone()[0]
        assert clustered and last == -1
        return {'rows': rows, 'planner_switches_changed': False,
            'iot_native': False, 'persistent_bitmap_index_native': False, 'oracle_reverse_key_native': False,
            'bitmap': {'sql': bitmap_query, 'plan': bitmap},
            'reverse_expression': {'sql': reverse_query, 'plan': reverse, 'result_ids': [42],
                'equivalent_to_oracle_reverse_key': False},
            'cluster': {'marked_clustered': clustered, 'last_physical_offer_after_insert': last,
                        'continuous_ordering': False},
            'btree_deduplication_bytes': sizes, 'schema_persisted': False}

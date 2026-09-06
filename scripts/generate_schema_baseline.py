import psycopg,sys,datetime,collections
sys.path.insert(0,'/tmp/mig'); from env import creds
OUT='/sessions/sharp-trusting-planck/mnt/the-platform-workspace/probata/sql/bootstrap/schema_baseline_20260830.sql'
SKIP=('pg_catalog','information_schema','pg_toast')
L=[]
w=L.append
with psycopg.connect(**creds(),dbname='platform',connect_timeout=30) as cn:
    cn.read_only=True
    q=lambda s,p=(): cn.execute(s,p).fetchall()
    w(f"""-- schema_baseline_20260830.sql
-- Generated {datetime.datetime.now(datetime.timezone.utc).isoformat()} from the live `platform`
-- database using PostgreSQL's own DDL serializers (pg_get_constraintdef,
-- pg_get_indexdef, pg_get_viewdef, pg_get_functiondef).
--
-- THIS REPLACES sql/bootstrap/schema_baseline.sql (a pg_dump from 2026-08-10).
--
-- Why: the old baseline was a stale photograph. Tables deleted from the live
-- database kept reappearing on every rebuild because they still existed in that
-- photo. Re-baselining makes deletion permanent and collapses the build from
-- "baseline + 50 migrations replayed in 3 passes" to a single file.
--
-- Migrations 0001-0055 are now HISTORY, not build steps. The next new
-- migration is 0056.
--
-- NOTHING here is immutable. No append-only / forbid / assert guard is
-- included: all 131 such triggers in the old chain guarded context/working
-- (layers under construction), lookup registries, or a finished consolidation
-- -- ZERO guarded evidence.*. See docs/GUARD-TRIGGER-DISPOSITION.md.

SET client_min_messages = warning;
""")
    w("-- ============ schemas ============")
    for (n,) in q("""select nspname from pg_namespace where nspname !~ '^pg_'
        and nspname NOT IN ('information_schema','duckdb') order by 1"""):
        w(f"CREATE SCHEMA IF NOT EXISTS {n};")
    w("\n-- ============ extensions ============")
    for n,s in q("""select e.extname,nn.nspname from pg_extension e
        join pg_namespace nn on nn.oid=e.extnamespace order by 1"""):
        w(("-- OPTIONAL (analytics only; skip if it errors): " if n=='pg_duckdb' else "")
          + f'CREATE EXTENSION IF NOT EXISTS \"{n}\" SCHEMA {s};')
    w("\n-- ============ enum types ============")
    en=collections.OrderedDict()
    for s,t,v in q("""select nn.nspname,tt.typname,e.enumlabel from pg_enum e
        join pg_type tt on tt.oid=e.enumtypid join pg_namespace nn on nn.oid=tt.typnamespace
        where nn.nspname not in ('pg_catalog','information_schema','duckdb')
        order by nn.nspname,tt.typname,e.enumsortorder"""):
        en.setdefault(f"{s}.{t}",[]).append(v)
    for k,v in en.items():
        lits=", ".join("'"+x.replace("'","''")+"'" for x in v)
        w(f"CREATE TYPE {k} AS ENUM ({lits});")
    w("\n-- ============ composite types ============")
    for sc,nm,oid in q("""select nn.nspname, t.typname, t.oid
        from pg_type t join pg_namespace nn on nn.oid=t.typnamespace
        left join pg_class cl on cl.oid = t.typrelid
        where t.typtype='c' and (cl.oid is null or cl.relkind='c')
        and not exists (select 1 from pg_depend d where d.objid=t.oid and d.deptype='e')
        and nn.nspname NOT IN ('pg_catalog','information_schema','duckdb')
        order by 1,2"""):
        flds=q("""select a.attname, pg_catalog.format_type(a.atttypid,a.atttypmod)
            from pg_attribute a join pg_type t on t.typrelid=a.attrelid
            where t.oid=%s and a.attnum>0 and not a.attisdropped order by a.attnum""",(oid,))
        if not flds: continue
        w(f"CREATE TYPE {sc}.{nm} AS (\n" + ",\n".join(f"  {fn} {ft}" for fn,ft in flds) + "\n);")
    w("\n-- ============ domains ============")
    for sc,nm,base,notnull,dflt,chks in q("""select nn.nspname, t.typname,
            pg_catalog.format_type(t.typbasetype, t.typtypmod), t.typnotnull,
            t.typdefault,
            coalesce((select string_agg(pg_get_constraintdef(co.oid),' ') from pg_constraint co
                      where co.contypid = t.oid),'')
        from pg_type t join pg_namespace nn on nn.oid=t.typnamespace
        where t.typtype='d' and nn.nspname NOT IN ('pg_catalog','information_schema','duckdb')
        order by 1,2"""):
        line=f"CREATE DOMAIN {sc}.{nm} AS {base}"
        if dflt is not None: line+=f" DEFAULT {dflt}"
        if notnull: line+=" NOT NULL"
        if chks: line+=" "+chks
        w(line+";")
    w("\n-- ============ sequences ============")
    for s,n in q("""select nn.nspname,c.relname from pg_class c join pg_namespace nn on nn.oid=c.relnamespace
        where c.relkind='S' and nn.nspname NOT IN ('pg_catalog','information_schema','pg_toast','duckdb')
        order by 1,2"""):
        w(f"CREATE SEQUENCE IF NOT EXISTS {s}.{n};")
    w("\n-- ============ tables ============")
    tabs=q("""select nn.nspname,c.relname,c.oid from pg_class c join pg_namespace nn on nn.oid=c.relnamespace
        where c.relkind='r' and nn.nspname NOT IN ('pg_catalog','information_schema','pg_toast','duckdb') order by 1,2""")
    for s,t,oid in tabs:
        cols=q("""select a.attname, pg_catalog.format_type(a.atttypid,a.atttypmod), a.attnotnull,
            pg_get_expr(d.adbin,d.adrelid), a.attidentity, a.attgenerated
            from pg_attribute a left join pg_attrdef d on d.adrelid=a.attrelid and d.adnum=a.attnum
            where a.attrelid=%s and a.attnum>0 and not a.attisdropped order by a.attnum""",(oid,))
        parts=[]
        for nm,ty,nn_,dflt,ident,gen in cols:
            p=f'  {nm} {ty}'
            if gen=='s': p+=f' GENERATED ALWAYS AS ({dflt}) STORED'
            elif ident=='a': p+=' GENERATED ALWAYS AS IDENTITY'
            elif ident=='d': p+=' GENERATED BY DEFAULT AS IDENTITY'
            elif dflt: p+=f' DEFAULT {dflt}'
            if nn_: p+=' NOT NULL'
            parts.append(p)
        w(f"\nCREATE TABLE IF NOT EXISTS {s}.{t} (\n"+",\n".join(parts)+"\n);")
    w("\n-- ============ primary keys / unique / check ============")
    for s,t,cn_,df in q("""select nn.nspname,c.relname,con.conname,pg_get_constraintdef(con.oid)
        from pg_constraint con join pg_class c on c.oid=con.conrelid
        join pg_namespace nn on nn.oid=c.relnamespace
        where con.contype in ('p','u','c') and nn.nspname NOT IN ('pg_catalog','information_schema','pg_toast','duckdb') and c.relkind='r'
          and c.relname <> 'spatial_ref_sys'
        order by 1,2,3"""):
        w(f"ALTER TABLE {s}.{t} ADD CONSTRAINT {cn_} {df};")
    w("\n-- ============ foreign keys (after all tables exist) ============")
    for s,t,cn_,df in q("""select nn.nspname,c.relname,con.conname,pg_get_constraintdef(con.oid)
        from pg_constraint con join pg_class c on c.oid=con.conrelid
        join pg_namespace nn on nn.oid=c.relnamespace
        where con.contype='f' and nn.nspname NOT IN ('pg_catalog','information_schema','pg_toast','duckdb') order by 1,2,3"""):
        w(f"ALTER TABLE {s}.{t} ADD CONSTRAINT {cn_} {df};")
    w("\n-- ============ indexes ============")
    for df, in q("""select pg_get_indexdef(i.indexrelid) from pg_index i
        join pg_class c on c.oid=i.indrelid join pg_namespace nn on nn.oid=c.relnamespace
        where nn.nspname NOT IN ('pg_catalog','information_schema','pg_toast','duckdb') and not i.indisprimary
        and not exists (select 1 from pg_constraint k where k.conindid=i.indexrelid)
        order by 1"""):
        w(df.replace('CREATE INDEX ','CREATE INDEX IF NOT EXISTS ',1)
           .replace('CREATE UNIQUE INDEX ','CREATE UNIQUE INDEX IF NOT EXISTS ',1)+";")
    w("\n-- ============ functions (guards excluded by design) ============")
    nf=0
    for s,nm,df in q("""select nn.nspname,p.proname,pg_get_functiondef(p.oid)
        from pg_proc p join pg_namespace nn on nn.oid=p.pronamespace
        where nn.nspname not in ('pg_catalog','information_schema','duckdb')
        and not exists (select 1 from pg_depend d where d.objid=p.oid and d.deptype='e')
        order by 1,2""",()):
        if nm and any(k in nm for k in ('forbid','guard','assert','append_only','immutab')):
            continue
        w(df+";"); nf+=1
    w("\n-- ============ views ============")
    for s,t,df in q("""select nn.nspname,c.relname,pg_get_viewdef(c.oid,true)
        from pg_class c join pg_namespace nn on nn.oid=c.relnamespace
        where c.relkind='v' and nn.nspname NOT IN ('pg_catalog','information_schema','pg_toast','duckdb') order by 1,2"""):
        w(f"CREATE OR REPLACE VIEW {s}.{t} AS\n{df}")
    w("\n-- ============ functions, pass 2 (resolves intra-section dependency order) ============")
    nf2=0
    for s,nm,df in q("""select nn.nspname,p.proname,pg_get_functiondef(p.oid)
        from pg_proc p join pg_namespace nn on nn.oid=p.pronamespace
        where nn.nspname not in ('pg_catalog','information_schema','duckdb')
        and not exists (select 1 from pg_depend d where d.objid=p.oid and d.deptype='e')
        order by 1,2""",()):
        if nm and any(k in nm for k in ('forbid','guard','assert','append_only','immutab')):
            continue
        w(df+";"); nf2+=1
    w("\n-- ============ views, pass 2 ============")
    for s,t,df in q("""select nn.nspname,c.relname,pg_get_viewdef(c.oid,true)
        from pg_class c join pg_namespace nn on nn.oid=c.relnamespace
        where c.relkind='v' and nn.nspname NOT IN ('pg_catalog','information_schema','pg_toast','duckdb') order by 1,2"""):
        w(f"CREATE OR REPLACE VIEW {s}.{t} AS\n{df}")
    w("\n-- ============ comments ============")
    for s,t,c_,kind in q("""select nn.nspname,c.relname,obj_description(c.oid,'pg_class'),c.relkind
        from pg_class c join pg_namespace nn on nn.oid=c.relnamespace
        where c.relkind in ('r','v') and nn.nspname NOT IN ('pg_catalog','information_schema','pg_toast','duckdb')
        and obj_description(c.oid,'pg_class') is not null order by 1,2"""):
        w(f"COMMENT ON {'VIEW' if kind=='v' else 'TABLE'} {s}.{t} IS '{c_.replace(chr(39),chr(39)*2)}';")
txt="\n".join(L)+"\n"
open(OUT,'w',encoding='utf-8').write(txt)
print(f"wrote {OUT}")
print(f"  {len(txt):,} bytes   {len(tabs)} tables   {len(en)} enums   {nf} functions")

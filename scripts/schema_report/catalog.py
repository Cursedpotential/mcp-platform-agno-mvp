import re,sys,json
from pathlib import Path
env=Path.home()/".secrets"/"probata.env"; pw=None
for line in env.read_text(encoding="utf-8",errors="ignore").splitlines():
    m=re.match(r"^\s*(?:export\s+)?DB_PASS\s*=\s*['\"]?(.+?)['\"]?\s*$",line)
    if m: pw=m.group(1);break
import psycopg
def catalog(db, full=True):
    c=psycopg.connect(host="100.91.190.107",port=5432,dbname=db,user="ai",password=pw,connect_timeout=15); cur=c.cursor()
    cur.execute("""select c.oid, n.nspname, c.relname, c.relkind, obj_description(c.oid,'pg_class')
      from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where c.relkind in ('r','p','v','m') and n.nspname not in ('pg_catalog','information_schema','pg_toast') order by n.nspname,c.relname""")
    rels=cur.fetchall(); out=[]
    for oid,sch,tbl,kind,cmt in rels:
        d={"schema":sch,"table":tbl,"kind":{"r":"table","p":"table","v":"view","m":"matview"}[kind],"comment":cmt,"rows":None,"columns":[],"constraints":[],"inbound_fk":[],"indexes":[]}
        if kind in ("r","p"):
            cur.execute(f'select count(*) from "{sch}"."{tbl}"'); d["rows"]=cur.fetchone()[0]
        if full:
            cur.execute("""select a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull, pg_get_expr(x.adbin,x.adrelid), col_description(a.attrelid,a.attnum)
              from pg_attribute a left join pg_attrdef x on x.adrelid=a.attrelid and x.adnum=a.attnum where a.attrelid=%s and a.attnum>0 and not a.attisdropped order by a.attnum""",(oid,))
            d["columns"]=[{"name":n,"type":t,"notnull":nn,"default":df,"comment":cc} for n,t,nn,df,cc in cur.fetchall()]
            cur.execute("select conname, contype, pg_get_constraintdef(oid) from pg_constraint where conrelid=%s order by contype,conname",(oid,))
            d["constraints"]=[{"name":a,"type":{"p":"PK","f":"FK","u":"UNIQUE","c":"CHECK","x":"EXCL"}.get(b,b),"def":cc} for a,b,cc in cur.fetchall()]
            cur.execute("select n.nspname||'.'||c.relname from pg_constraint k join pg_class c on c.oid=k.conrelid join pg_namespace n on n.oid=c.relnamespace where k.confrelid=%s and k.contype='f'",(oid,))
            d["inbound_fk"]=sorted(set(x[0] for x in cur.fetchall()))
            cur.execute("select indexname from pg_indexes where schemaname=%s and tablename=%s",(sch,tbl)); d["indexes"]=[x[0] for x in cur.fetchall()]
            if kind in("v","m"):
                cur.execute("select pg_get_viewdef(%s,true)",(oid,)); d["viewdef"]=cur.fetchone()[0]
        out.append(d)
    c.close(); return out
res={"ai":catalog("ai",True),"ai_test_ingest":catalog("ai_test_ingest",False),"traceiq":catalog("traceiq",False)}
Path(sys.argv[1]).write_text(json.dumps(res,default=str),encoding="utf-8")
print({k:len(v) for k,v in res.items()})

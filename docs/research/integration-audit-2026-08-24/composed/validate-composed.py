# -*- coding: utf-8 -*-
"""Structural validation of the Stage-4 composed n8n workflow JSONs."""
import json, glob, os, re, sys

OUT = r"E:\AI_Workspace\Projects\the-platform-workspace\Agno-MCP-Platform\docs\research\integration-audit-2026-08-24\composed"
SECRET_KEYS = re.compile(r'"(api[-_]?key|apiKey|password|secret|token|accessToken|bearer)"\s*:\s*"([^"]+)"', re.I)
PLACEHOLDER = re.compile(r'\{\{[A-Z_]+\}\}')

allok = True
allids = {}
for path in sorted(glob.glob(os.path.join(OUT, "*.json"))):
    fn = os.path.basename(path)
    raw = open(path, encoding="utf-8").read()
    errs, warns = [], []
    try:
        d = json.loads(raw)
    except Exception as e:
        print("FAIL", fn, "JSON parse:", e); allok = False; continue

    nodes = d.get("nodes")
    conns = d.get("connections")
    if not isinstance(nodes, list) or not nodes: errs.append("nodes[] missing/empty")
    if not isinstance(conns, dict): errs.append("connections{} missing")
    if "meta" not in d: errs.append("meta missing")
    if "name" not in d: errs.append("name missing")

    names = [n.get("name") for n in nodes]
    ids = [n.get("id") for n in nodes]
    if len(set(names)) != len(names): errs.append("duplicate node NAMES: %s" % [x for x in names if names.count(x) > 1])
    if len(set(ids)) != len(ids): errs.append("duplicate node IDs")
    for n in nodes:
        if not n.get("id"): errs.append("node without id: %s" % n.get("name"))
        if n.get("typeVersion") is None: errs.append("node without typeVersion: %s" % n.get("name"))
        if not isinstance(n.get("position"), list) or len(n["position"]) != 2:
            errs.append("bad position: %s" % n.get("name"))
        if not isinstance(n.get("parameters"), dict): errs.append("bad parameters: %s" % n.get("name"))
        gid = n["id"]
        if gid in allids and allids[gid] != fn:
            errs.append("node id collides with %s" % allids[gid])
        allids[gid] = fn

    nameset = set(names)
    # connections sanity: every source key and every target node must exist
    conn_count = 0
    for src, out in (conns or {}).items():
        if src not in nameset: errs.append("connection SOURCE not a node: %r" % src)
        for ctype, outputs in out.items():
            for oi, arr in enumerate(outputs or []):
                for c in arr or []:
                    conn_count += 1
                    if c.get("node") not in nameset:
                        errs.append("connection TARGET not a node: %r (from %r)" % (c.get("node"), src))
                    if "type" not in c or "index" not in c:
                        errs.append("connection missing type/index: %r -> %r" % (src, c.get("node")))

    # every non-sticky, non-trigger, non-subnode node should be reachable or be a source
    referenced = set()
    for src, out in (conns or {}).items():
        referenced.add(src)
        for ctype, outputs in out.items():
            for arr in outputs or []:
                for c in arr or []:
                    referenced.add(c.get("node"))
    for n in nodes:
        t = n.get("type", "")
        if t.endswith("stickyNote"): continue
        if n.get("disabled"): continue
        if n["name"] not in referenced:
            warns.append("orphan node (no connections): %s" % n["name"])

    # trigger present
    triggers = [n for n in nodes if any(k in n.get("type", "").lower()
                                        for k in ("trigger", "webhook"))]
    if not triggers: errs.append("no trigger node")

    # sticky notes present
    stickies = [n for n in nodes if n.get("type", "").endswith("stickyNote")]
    if not stickies: errs.append("no sticky notes")

    # secrets scan
    for mobj in SECRET_KEYS.finditer(raw):
        val = mobj.group(2)
        if val not in ("REPLACE_ME",) and not PLACEHOLDER.search(val) and "placeholder" not in val.lower():
            errs.append("possible secret VALUE for key %s: len=%d" % (mobj.group(1), len(val)))

    ph = sorted(set(PLACEHOLDER.findall(raw)))
    cred_names = sorted({c.get("name") for n in nodes for c in (n.get("credentials") or {}).values()})

    status = "OK  " if not errs else "FAIL"
    if errs: allok = False
    print("%s %-26s nodes=%2d (sticky=%d) conns=%2d placeholders=%s creds=%s"
          % (status, fn, len(nodes), len(stickies), conn_count, ph, cred_names))
    for e in errs: print("      ERROR:", e)
    for w in warns: print("      note :", w)

print("\nALL STRUCTURALLY VALID" if allok else "\nVALIDATION FAILED")
sys.exit(0 if allok else 1)

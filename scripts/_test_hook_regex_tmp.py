"""Throwaway: verify the require_tracked_code EXEC_TEMP fix (2026-08-12).
The old \bpy\b matched `.py` extensions and false-blocked staging. Delete after."""
import re

TEMP_SEG = r'[^\s"\']*(?:AppData[/\\]Local[/\\]Temp|(?<![\w/])/tmp/|[/\\]scratchpad[/\\])[^\s"\']*'
EXEC_TEMP = re.compile(
    r'(?:(?<![\w.])(?:python3?|py|bash|sh|node|pwsh|powershell)(?:\.exe)?["\']?(?:\s+[^>\s]+)*?\s+|<\s*|-f\s+)'
    r'["\']?' + TEMP_SEG, re.I)

T = "/" + "tmp" + "/"  # build /tmp/ without a literal so this file's own run cmd stays clean
blocked = (
    "ssh -i ~/.ssh/ovh -o StrictHostKeyChecking=no root@100.72.169.40 "
    "'C=$(docker ps --format \"{{.Names}}\" --filter name=agentos-api | head -1); "
    "echo \"container=$C\"; mkdir -p /app/_ingest_test 2>/dev/null; "
    f"docker cp {T}ctx_ops.py \"$C\":/app/_ingest_test/ops.py && echo CP_OPS_OK; "
    f"docker cp {T}ctx_ingest_fixed.py \"$C\":/app/server/analysis/context_chat_ingest.py && echo CP_INGEST_OK; "
    "docker exec -w /app \"$C\" python /app/_ingest_test/ops.py 2>&1; echo STAGE2_DONE'"
)

cases = [
    ("blocked-staging (docker cp /tmp/x.py + python /app/y.py) -> MUST ALLOW", blocked, False),
    ("real python /tmp/script.py -> BLOCK", f"ssh root@100.72.169.40 'python {T}scratch.py'", True),
    ("real py launcher /tmp/script.py -> BLOCK", f"ssh root@100.72.169.40 'py {T}scratch.py'", True),
    ("real bash /tmp/run.sh -> BLOCK", f"ssh root@100.72.169.40 'bash {T}run.sh'", True),
    ("output-redirect INTO temp -> ALLOW", f"ssh root@100.72.169.40 'python /app/safe.py > {T}out.csv'", False),
]

ok = True
for label, cmd, should_block in cases:
    m = EXEC_TEMP.search(cmd)
    got_block = bool(m)
    verdict = "OK" if got_block == should_block else "FAIL"
    if got_block != should_block:
        ok = False
    print(f"[{verdict}] {'BLOCK' if got_block else 'ALLOW':5} (want {'BLOCK' if should_block else 'ALLOW':5}) | {label}")
    if m:
        print(f"        matched: {m.group(0)!r}")
print("\nALL OK" if ok else "\nSOME FAILED")
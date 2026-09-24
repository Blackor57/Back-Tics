import subprocess, sys, re

out = subprocess.run(
    ["docker", "compose", "logs", "--tail=2000", "chatbot_service"],
    capture_output=True, text=True,
)
t = out.stdout

# Guarda los últimos 3 bloque de traceback completos (cada uno desde 'Traceback' hasta la línea
# 'async with' / 'raise' / fin protegido) extrayendo SÓLO líneas del proyecto (app/ chatb...)
blocks = re.split(r"\n(?=Traceback \(most recent call last\))", t)
latest = blocks[-1] if len(blocks) > 1 else t
keep = []
for line in latest.splitlines():
    s = line.strip()
    if (s.startswith('File "/') or s.startswith('File "D:\\') or s.startswith('File "C:\\')) or s.startswith("await ") or s.startswith("rows ") or "@" in s[:60]:
        keep.append(s)
    elif s and s[0].isupper() and ":" not in s[:80] and len(s) < 80:
        keep.append(s)

print("===== TRAZA PROYECTO (archivos de chatbot_service) =====")
for k in keep[:70]:
    print(k)

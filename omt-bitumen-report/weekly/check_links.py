import zipfile, re

PPTX = r"Рынок СрАзии_25_05_2026.pptx"

with zipfile.ZipFile(PPTX) as z:
    for name in z.namelist():
        if not name.endswith(".rels"):
            continue
        txt = z.read(name).decode("utf-8")
        for m in re.finditer(r'Target="([^"]+\.xlsx[^"]*)"', txt):
            print(m.group(1))

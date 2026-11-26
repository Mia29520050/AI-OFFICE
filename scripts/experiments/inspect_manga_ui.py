with open("app/ui/index.html", encoding="utf-8") as f:
    text = f.read()

import re
matches = re.finditer(r'data-studio-tab=[\'"]manga[\'"]|function renderManga[a-zA-Z0-9_]*', text)
for m in matches:
    p = m.start()
    print("MATCH:", text[p:p+250])
    print("=" * 40)

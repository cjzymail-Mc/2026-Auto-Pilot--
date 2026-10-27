# CASE-08 阶段一：从原件 PDF 提取内嵌文本（机读通道，零业务写入）
import fitz, json, os

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ROOT, '..', '..', '..', '..'))
MAN = os.path.join(REPO, 'automation', 'runs', '20261026-193100-0527f5dc', 'materials', 'manifest.json')
OUT = os.path.join(ROOT, 'pdf-text')
os.makedirs(OUT, exist_ok=True)

man = json.load(open(MAN, encoding='utf-8'))
n_ok = n_empty = 0
index = {}
for f in man['files']:
    rel = f['relative_path']
    if not rel.lower().endswith('.pdf'):
        continue
    doc = fitz.open(f['path'])
    text = '\n'.join(p.get_text() for p in doc)
    doc.close()
    safe = rel.replace('\\', '__').replace('/', '__') + '.txt'
    with open(os.path.join(OUT, safe), 'w', encoding='utf-8') as fh:
        fh.write(text)
    index[rel] = {'sha256': f['sha256'], 'chars': len(text.strip())}
    if text.strip():
        n_ok += 1
    else:
        n_empty += 1
json.dump(index, open(os.path.join(OUT, '_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('pdfs with text:', n_ok, 'empty:', n_empty)

# CASE-08 阶段一：机读通道——从 72 份 PDF 文本层确定性解析票面字段
# 输入：pdf-text/*.txt（PyMuPDF 提取的原件内嵌文本）；输出：machine-parse.json + 控制台表
import json, os, re
from decimal import Decimal

ROOT = os.path.dirname(os.path.abspath(__file__))
TXT = os.path.join(ROOT, 'pdf-text')
MAN = os.path.abspath(os.path.join(ROOT, '..', '..', '..', '..',
                                  'automation', 'runs', '20261026-193100-0527f5dc',
                                  'materials', 'manifest.json'))

man = json.load(open(MAN, encoding='utf-8'))
sha_by_rel = {f['relative_path']: f['sha256'] for f in man['files']}

tail_re = re.compile(
    r'(?m)^(\d{12})\n(\d{8})\n(20\d{2}年\d{2}月\d{2}日)\n((?:\d{5} ){3}\d{5})\n(￥[\d.,]+)\s*$')
amt_re = re.compile(r'(￥[\d.,]+)')
date_re = re.compile(r'(20\d{2}年\d{2}月\d{2}日)')

records = []
for rel, sha in sorted(sha_by_rel.items()):
    if not rel.lower().endswith('.pdf'):
        continue
    safe = rel.replace('\\', '__').replace('/', '__') + '.txt'
    txt = open(os.path.join(TXT, safe), encoding='utf-8').read()
    rec = {'relative_path': rel, 'sha256': sha, 'kind': None}
    if '汇总单' in txt:
        rec['kind'] = 'summary'
        m = re.search(r'汇总单号[:：]\s*(\d+)', txt)
        rec['summary_no'] = m.group(1) if m else None
        m = re.search(r'共\s*(\d+)\s*张票据', txt)
        rec['ticket_count'] = int(m.group(1)) if m else None
        # 行程行：通行日期起止 YYYYMMDD YYYYMMDD + 出入口（闽·福建XX站 至 闽·福建XX站）
        rec['routes'] = re.findall(r'闽·福建(\S+?)站\s*至\s*闽·福建(\S+?)站', txt)
        # 价税合计小写（最后一个 ￥ 金额）
        amts = amt_re.findall(txt)
        rec['total_lower'] = amts[-1] if amts else None
        # 票据表行：12位代码 + 8位号码 相邻两行
        rec['tickets'] = [
            {'code': a, 'number': b}
            for a, b in re.findall(r'(?m)^(\d{12})\n(\d{8})$', txt)
        ]
        # 每票金额（表格中“金额（含税）”后逐行金额，随后税率）
        rec['ticket_amounts'] = re.findall(r'(?m)^\d+\.\d{2}$', txt)
    elif '成品油' in txt or '汽油' in txt or '柴油' in txt:
        rec['kind'] = 'oil_invoice'
        m = re.search(r'发票号码[:：]\s*(\d{20})', txt)
        rec['invoice_number'] = m.group(1) if m else None
        m = date_re.search(txt)
        rec['issue_date'] = m.group(1) if m else None
        amts = amt_re.findall(txt)
        rec['amounts_all'] = amts
        m = re.search(r'价税合计（大写）\s*\S+\s*（小写）(￥[\d.,]+)', txt.replace('\n', ''))
        rec['total_lower'] = m.group(1) if m else (amts[-1] if amts else None)
        rec['item'] = re.findall(r'\*(汽油|柴油)\*(\S+?)升', txt.replace('\n', ''))
    else:
        rec['kind'] = 'toll_invoice'
        m = tail_re.search(txt)
        if m:
            rec['invoice_code'] = m.group(1)
            rec['invoice_number'] = m.group(2)
            rec['issue_date'] = m.group(3)
            rec['checksum'] = m.group(4)
            rec['total_lower'] = m.group(5)
        else:
            rec['tail_error'] = 'TAIL_5TUPLE_NOT_FOUND'
        # 车牌、不含税/税率/税额行
        rec['plate'] = (re.search(r'(闽D\d{4,5}[A-Z]?|[^\n]*闽[A-Z][^\n]*车牌)', txt) or [None]) and (
            re.search(r'闽D263GG|闽D\w{5}', txt).group(0) if re.search(r'闽D\w{5}', txt) else None)
        rec['travel_dates'] = re.findall(r'(?m)^(20\d{6})$', txt)[:2]
        rec['amount_lines'] = re.findall(r'(?m)^(\d+\.\d{2})$\n^(3%|1%|不征税)$\n^(\d+\.\d{2}|-)$', txt, )
        rec['amounts_all'] = amt_re.findall(txt)
        rec['upper_total'] = re.findall(r'(?m)^([零壹贰叁肆伍陆柒捌玖拾佰仟万亿角分圆元整⊗]+)$', txt)
    records.append(rec)

json.dump(records, open(os.path.join(ROOT, 'machine-parse.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

# 控制台总览
for r in records:
    if r['kind'] == 'summary':
        print(f"SUMMARY {r['relative_path'][:34]:36s} no={r.get('summary_no')} n={r.get('ticket_count')} "
              f"total={r.get('total_lower')} tickets={[(t['code'][:4], t['number']) for t in r.get('tickets', [])]} "
              f"routes={r.get('routes')}")
    elif r['kind'] == 'oil_invoice':
        print(f"OIL     {r['relative_path'][:34]:36s} num={r.get('invoice_number')} date={r.get('issue_date')} "
              f"total={r.get('total_lower')} item={r.get('item')}")
    else:
        print(f"TOLL    {r['relative_path'][:34]:36s} code={r.get('invoice_code')} num={r.get('invoice_number')} "
              f"date={r.get('issue_date')} total={r.get('total_lower')} {'ERR' if 'tail_error' in r else ''}")

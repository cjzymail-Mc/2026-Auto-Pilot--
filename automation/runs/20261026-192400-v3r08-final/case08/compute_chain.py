# CASE-08 阶段一：事实链最终计算（Decimal 严格口径）
# 通道：pdf-text 机读（PyMuPDF 文本层）+ machine-parse.json；零业务写入
import json, os, re
from decimal import Decimal

ROOT = os.path.dirname(os.path.abspath(__file__))
recs = json.load(open(os.path.join(ROOT, 'machine-parse.json'), encoding='utf-8'))

def yuan(s):
    return Decimal(s.replace('￥', '').replace('¥', '').replace(',', ''))

AMT = re.compile(r'[￥¥][\d,]+\.\d{2}')

# --- 油票总额：价税合计（小写）为文本最后一个 ￥/¥ 金额；打印全部序列人工核对 ---
print('== OIL amounts ==')
oil_total = Decimal('0')
oil_list = []
for r in recs:
    if r['kind'] != 'oil_invoice':
        continue
    txt = open(os.path.join(ROOT, 'pdf-text',
                            r['relative_path'].replace('\\', '__').replace('/', '__') + '.txt'),
               encoding='utf-8').read()
    amts = AMT.findall(txt)
    print(r['relative_path'], r['invoice_number'], amts)
    assert amts, 'no amounts in oil invoice'
    t = yuan(amts[-1])
    oil_list.append({'path': r['relative_path'], 'number': r['invoice_number'], 'total': str(t)})
    oil_total += t
O = oil_total
print('O =', O)

# --- 通行费：27 张发票（已证互异）票面合计 ---
toll = [(r['relative_path'], r['invoice_number'], yuan(r['total_lower'])) for r in recs if r['kind'] == 'toll_invoice']
nums = [t[1] for t in toll]
assert len(nums) == len(set(nums)) == 27, f'toll distinct fail: {len(nums)}/{len(set(nums))}'
T = sum((t[2] for t in toll), Decimal('0'))
print('T =', T, ' tickets =', len(toll))
for p, n, a in sorted(toll):
    print(f'  {p:42s} {n} {a}')

# --- 汇总单身份账：20 身份，票号↔发票一一对应 ---
sums = [r for r in recs if r['kind'] == 'summary']
by_no = {}
for r in sums:
    by_no.setdefault(r['summary_no'], set()).update(t['number'] for t in r['tickets'])
assert len(by_no) == 20, len(by_no)
covered = set()
for no, tk in sorted(by_no.items()):
    covered |= tk
print('summary identities =', len(by_no), ' covered toll numbers =', len(covered))
assert covered == set(nums), 'summary coverage mismatch with invoices'

# --- 金额模型（合同 §4） ---
K = Decimal('1438')            # Excel 公里数合计（已闭合：新刚1022+乔丹二厂152+中乔264）
M = K * Decimal('1.00')        # 1 元/公里
R = M + T
F = O + T
margin = F - R
gate = F > R
print(f'K={K} M={M} T={T} O={O}')
print(f'R=M+T={R}  F=O+T={F}  margin=F-R={margin}  F>R strict gate: {gate}')
assert margin == O - M

# 落盘机读结论
out = {
    'K_km': str(K), 'M_subsidy': str(M), 'T_toll': str(T),
    'O_oil': str(O), 'R_claim': str(R), 'F_coverage': str(F),
    'margin': str(margin), 'gate_F_gt_R': gate,
    'toll_tickets': [{'path': p, 'invoice_number': n, 'amount': str(a)} for p, n, a in sorted(toll)],
    'oil_invoices': oil_list,
    'summary_identities': {no: sorted(tk) for no, tk in sorted(by_no.items())},
}
json.dump(out, open(os.path.join(ROOT, 'fact-recompute.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('fact-recompute.json written')

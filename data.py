"""Read source values without evaluating, repairing or inventing observations."""
from pathlib import Path
import hashlib
import json
import math

import openpyxl
import pandas as pd

SHEETS = {'工艺参数库': '记录ID', '焊接Case': 'CaseID', '逐道参数': 'PassID', '实验结果': 'ResultID'}
NUM = ['Thickness', 'GrooveAngle', 'RootGap']
CAT = ['Position', 'PassRole']
FEATURES = NUM + CAT
TARGETS = {'Current': '推荐_实测电流_A', 'Voltage': '推荐_实测电压_V', 'TravelSpeed': '推荐_实测焊速_mm_min'}
ROLES = ['Root', 'Fill', 'Cap']


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def position(value):
    return {'PA / AWS 1G': 'PA', '1G (flat)': 'PA', '平对接': 'PA',
            'Vertical up': 'PF', '3G Uphill': 'PF', '45°斜立对接（向上）': 'Inclined45Up'}.get(value)


def roles(value):
    if value == 'Root/Fill/Cap共用固定电流电压':
        return ROLES
    if value and ('打底' in value or value == 'Root'):
        return ['Root']
    if value in ['填充', 'Fill']:
        return ['Fill']
    if value and ('盖面' in value or value == 'Cap'):
        return ['Cap']
    return [None]


def read_source(path):
    raw = openpyxl.load_workbook(path, data_only=False)
    cached = openpyxl.load_workbook(path, data_only=True)
    tables, issues, formula_cells = {}, [], set()
    summary = {}
    for name, key in SHEETS.items():
        s, c = raw[name], cached[name]
        headers = [v.value for v in s[1]]
        records = []
        for row in s.iter_rows(min_row=2):
            # Ignore formatting-only rows and empty template formulas without a key.
            if not row[0].value:
                if any(x.value is not None and x.data_type != 'f' for x in row):
                    issues.append({'Sheet': name, 'Cell': f'A{row[0].row}', 'Issue': 'missing primary key'})
                continue
            record = {h: c.cell(row[0].row, i + 1).value for i, h in enumerate(headers) if h}
            record['ExcelRow'] = row[0].row
            for i, cell in enumerate(row):
                if cell.data_type == 'f':
                    formula_cells.add((name, row[0].row, headers[i]))
                    issues.append({'Sheet': name, 'Cell': cell.coordinate, 'RecordID': row[0].value,
                                   'Issue': 'formula in source', 'Formula': cell.value,
                                   'CachedValue': c[cell.coordinate].value, 'Field': headers[i]})
            records.append(record)
        df = pd.DataFrame(records, columns=[h for h in headers if h] + ['ExcelRow'])
        if df[key].duplicated().any():
            raise ValueError(f'Duplicate {key} in {name}')
        tables[name] = df
        summary[name] = {'records': len(df), 'fields': len(df.columns) - 1,
                         'missing': df.isna().sum().to_dict(),
                         'field_names': list(df.columns),
                         'formatted_rows': s.max_row}
    ids = set(tables['焊接Case']['CaseID'])
    for name in ['逐道参数', '实验结果']:
        orphans = set(tables[name]['CaseID']) - ids
        if orphans:
            raise ValueError(f'Orphan CaseID in {name}: {orphans}')
    passes = tables['逐道参数'].set_index('PassID')
    for r in tables['实验结果'].to_dict('records'):
        pid = r.get('PassID_可空')
        if pd.notna(pid) and (pid not in passes.index or passes.loc[pid, 'CaseID'] != r['CaseID']):
            raise ValueError(f'Invalid result PassID: {pid}')
    # Validate all bounds and cached single values, including constraints.
    for name, df in tables.items():
        for r in df.to_dict('records'):
            for lo in [k for k in r if '下限' in k]:
                hi = lo.replace('下限', '上限')
                a, b = number(r.get(lo)), number(r.get(hi))
                if a is not None and b is not None and a > b:
                    issues.append({'Sheet': name, 'RecordID': r[SHEETS[name]], 'Issue': f'reversed bounds: {lo}'})
            if name == '逐道参数':
                for label, value, lo, hi in [('Current', '推荐_实测电流_A', '电流下限_A', '电流上限_A'),
                                            ('Voltage', '推荐_实测电压_V', '电压下限_V', '电压上限_V'),
                                            ('TravelSpeed', '推荐_实测焊速_mm_min', '焊速下限_mm_min', '焊速上限_mm_min')]:
                    v, a, b = number(r.get(value)), number(r.get(lo)), number(r.get(hi))
                    if v is not None and ((a is not None and v < a) or (b is not None and v > b)):
                        issues.append({'Sheet': name, 'RecordID': r['PassID'], 'Issue': f'{label} outside own bounds', 'CachedValue': v})
    summary['sha256'] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return tables, issues, formula_cells, summary


def prepare(path):
    tables, issues, formulas, summary = read_source(path)
    # Prefix fields so pass and case provenance can never silently overwrite one another.
    c = tables['焊接Case'].rename(columns=lambda x: x if x == 'CaseID' else 'Case_' + x)
    p = tables['逐道参数'].rename(columns=lambda x: x if x == 'CaseID' else 'Pass_' + x)
    merged = p.merge(c, on='CaseID', how='left', validate='many_to_one')
    records = []
    for original in merged.to_dict('records'):
        r = {k: (None if pd.isna(v) else v) for k, v in original.items()}
        rr = roles(r['Pass_焊道功能'])
        for role in rr:
            out = dict(r)
            out.update(ObservationID=r['Pass_PassID'], PassID=r['Pass_PassID'], PassRole=role,
                       ContextWeight=1 / len(rr), RoleBasis='Explicit shared setting' if len(rr) > 1 else 'Source role',
                       Thickness=number(r['Case_板厚_mm']), RootGap=number(r['Case_根部间隙_mm']),
                       GrooveAngle=None, Position=position(r['Case_焊接位置_原文']),
                       SourceGroup=r['Case_来源链接'] or r['Case_来源名称'],
                       Approved=r['Case_训练准入'] in ['是', '可用于训练', '可训练'] and r['Pass_训练准入'] in ['是', '可用于训练', '可训练'])
            if '总夹角' in (r['Case_坡口角度定义'] or '') and '未' not in r['Case_坡口角度定义']:
                out['GrooveAngle'] = number(r['Case_坡口角度_deg'])
            nature = r['Pass_参数性质'] or ''
            reason = []
            if r['Case_材料牌号'] != 'AH36' or number(r['Case_ISO4063']) != 136:
                reason.append('Material/process not confirmed AH36/136')
            if r['Case_训练准入'] == '否' or r['Pass_训练准入'] == '否':
                reason.append('Source explicitly excludes training')
            if '候选' in nature:
                reason.append('Engineering starting values, not experiments')
            if any(out[k] is None for k in FEATURES):
                reason.append('Missing or ambiguous input: ' + ','.join(k for k in FEATURES if out[k] is None))
            if nature not in ['实验控制参数', 'PQR实测参数', '文献实测参数', '同行评议实验参数', '研究稿实验参数']:
                reason.append('Not an eligible experimental point')
            if not (r['Pass_核验状态'] or '').startswith('已核验'):
                reason.append('Source not verified in workbook')
            is_range = '范围' in nature or '窗口' in nature
            if '候选' in nature:
                is_range = False
            for target, field in TARGETS.items():
                v = number(r['Pass_' + field])
                out[target + '_SourceValue'] = v
                formula = ('逐道参数', r['Pass_ExcelRow'], field) in formulas
                out[target] = None if formula else v
                out[target + '_Eligible'] = not reason and v is not None and v > 0 and not formula
                out[target + '_Reason'] = '; '.join(reason + (['Formula-based target excluded'] if formula else []) + (['Missing target'] if v is None else []))
            out['DataClass'] = 'TrainableResearch' if any(out[t + '_Eligible'] for t in TARGETS) else ('Constraint' if is_range else 'Auxiliary')
            out['ExclusionReason'] = '; '.join(reason)
            records.append(out)
    training = pd.DataFrame(records)
    summary['contexts'] = len(training)
    summary['class_counts'] = training.groupby('DataClass')['ObservationID'].nunique().to_dict()
    summary['target_coverage'] = {t: {'contexts': int(training[t + '_Eligible'].sum()),
                                    'observations': int(training.loc[training[t + '_Eligible'], 'ObservationID'].nunique()),
                                    'cases': int(training.loc[training[t + '_Eligible'], 'CaseID'].nunique()),
                                    'sources': int(training.loc[training[t + '_Eligible'], 'SourceGroup'].nunique())} for t in TARGETS}
    summary['approved_contexts'] = int(training.Approved.sum())
    summary['cases_without_passes'] = sorted(set(c.CaseID) - set(p.CaseID))
    return tables, training, issues, summary


def save_data(path, destination):
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    tables, training, issues, summary = prepare(path)
    for name, frame in tables.items():
        frame.to_csv(dest / f'{name}.csv', index=False, encoding='utf-8-sig')
    training.to_csv(dest / 'Model_Training_V1.csv', index=False, encoding='utf-8-sig')
    for label in ['TrainableResearch', 'Auxiliary', 'Constraint']:
        training[training.DataClass == label].to_csv(dest / f'{label}.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(issues).to_csv(dest / 'data_issues.csv', index=False, encoding='utf-8-sig')
    (dest / 'audit.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return tables, training, issues, summary

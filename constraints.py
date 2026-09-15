"""Advisory range checks. Never clip, replace or otherwise change predictions."""
import pandas as pd
from data import number

BOUNDS = {'Current': ('电流下限_A', '电流上限_A', 1),
          'Voltage': ('电压下限_V', '电压上限_V', 1),
          'TravelSpeed': ('焊接速度下限_cm_min', '焊接速度上限_cm_min', 10)}


def check_constraints(query, prediction, constraints, consumable='T492T1-1C1A', diameter=1.2):
    details = []
    for r in constraints.to_dict('records'):
        if r['模型用途'] != 'Constraint' or number(r['ISO4063']) != 136:
            continue
        if '窄间隙' in str(r['接头适用']):
            continue
        lo, hi = number(r['板厚下限_mm']), number(r['板厚上限_mm'])
        if (lo is not None and query['Thickness'] < lo) or (hi is not None and query['Thickness'] > hi):
            continue
        role = {'打底': 'Root', '填充': 'Fill', '盖面': 'Cap'}.get(r['焊层/电极'])
        if role is not None and role != query['PassRole']:
            continue
        pos = str(r['焊接位置'])
        positions = {'立焊': ['PF'], '平焊、横焊、仰焊': ['PA', 'PC', 'PE'], '全位置': ['PA', 'PC', 'PF', 'PG', 'PE'],
                     '平焊/横角焊（F & HF）': ['PA'], '立向上/仰焊': ['PF', 'PE'], '立向下': ['PG'],
                     '1G/2F/3G/4G（全位置）': ['PA', 'PF', 'PE']}.get(pos, [])
        if query['Position'] not in positions:
            continue
        pending = []
        material = str(r['母材范围'])
        if material not in ['A～DH36', 'A～EH36'] and 'AH36' not in material:
            pending.append('母材适用性需确认')
        if consumable != str(r['焊接材料']).split(' / ')[0].strip():
            pending.append('焊材牌号需确认')
        wire = number(r['规格直径_mm'])
        if wire is None:
            pending.append('焊丝直径适用性需确认')
        elif abs(wire - diameter) > 1e-6:
            continue
        for target, (low_field, high_field, factor) in BOUNDS.items():
            low, high = number(r[low_field]), number(r[high_field])
            if low is None and high is None:
                continue
            low = low * factor if low is not None else None
            high = high * factor if high is not None else None
            v = prediction.get(target)
            if v is None or pd.isna(v):
                state = 'NoPrediction'
            elif (low is not None and v < low) or (high is not None and v > high):
                state = 'Outside'
            else:
                state = 'Within'
            details.append({'RuleID': r['记录ID'], 'Target': target, 'RawPrediction': v, 'Lower': low, 'Upper': high,
                            'RangeCheck': state, 'Applicability': 'NeedsContext' if pending else 'Matched',
                            'Note': '；'.join(pending), 'Source': r['来源名称'], 'URL': r['来源链接']})
    statuses = {}
    for target in BOUNDS:
        relevant = [r for r in details if r['Target'] == target and r['Applicability'] == 'Matched']
        values = {r['RangeCheck'] for r in relevant}
        if prediction.get(target) is None:
            statuses[target] = 'NoPrediction'
        elif not relevant:
            statuses[target] = 'NoApplicableRule'
        elif 'Outside' in values and 'Within' in values:
            statuses[target] = 'MixedRules'
        elif values == {'Outside'}:
            statuses[target] = 'Outside'
        else:
            statuses[target] = 'WithinMatchedRanges'
    return statuses, details

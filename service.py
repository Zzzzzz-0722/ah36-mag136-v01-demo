import numpy as np
import pandas as pd
from data import ROLES, TARGETS, NUM
from constraints import check_constraints

DEMOS = {
    '已有文献工况 / 12 mm': dict(Thickness=12., GrooveAngle=50., RootGap=5., Position='PA'),
    '间隙外推 / 12 mm': dict(Thickness=12., GrooveAngle=40., RootGap=8., Position='PA'),
    '立焊覆盖缺口 / 18 mm': dict(Thickness=18., GrooveAngle=35., RootGap=6., Position='PF'),
}


def recommend(query, models, constraints, method='GPR', consumable='T492T1-1C1A', diameter=1.2):
    rows, all_checks = [], []
    for role in ROLES:
        q = {**query, 'PassRole': role}
        predictions = {t: models[f'{t}_{method}'].predict(q) for t in TARGETS}
        values = {t: p['Prediction'] for t, p in predictions.items()}
        states, checks = check_constraints(q, values, constraints, consumable, diameter)
        all_checks.extend([{'PassRole': role, **c} for c in checks])
        for target, p in predictions.items():
            rows.append({'PassRole': role, **p, 'ConstraintCheck': states[target]})
    return pd.DataFrame(rows), pd.DataFrame(all_checks)


def nearest_references(query, frame, count=8):
    ref = frame.drop_duplicates('ObservationID').copy()
    scores, compared = [], []
    scales = [5., 10., 2.]
    for _, row in ref.iterrows():
        known = [(float(row[k]) - query[k]) / scale for k, scale in zip(NUM, scales) if pd.notna(row[k])]
        matched = len(known)
        if pd.notna(row.Position):
            known.append(0. if row.Position == query['Position'] else 2.)
            matched += 1
        scores.append(float(np.sqrt(np.mean(np.square(known)))) + (4 - matched) if known else 99.)
        compared.append(matched)
    ref['ReferenceDistance'] = scores
    ref['ComparedInputs'] = compared
    return ref.sort_values(['ReferenceDistance', 'CaseID']).head(count)

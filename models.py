"""Case-separated estimation with explicit unsupported-target states."""
import warnings
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.exceptions import ConvergenceWarning
from data import FEATURES, NUM, CAT, TARGETS

SCALE_FLOOR = {'Current': 1., 'Voltage': .1, 'TravelSpeed': 1.}


class TargetModel:
    def __init__(self, target, method):
        self.target, self.method = target, method
        self.status = 'Not fitted'
        self.warnings = []

    def fit(self, frame, approved_only=False):
        eligible = frame[self.target + '_Eligible'].astype(bool)
        if approved_only:
            eligible &= frame.Approved.astype(bool)
        self.train = frame.loc[eligible].copy().reset_index(drop=True)
        if self.train.empty:
            self.status = 'Unavailable: no eligible labels'
            return self
        self.pre = ColumnTransformer([('numeric', StandardScaler(), NUM),
                                      ('category', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CAT)])
        self.x = self.pre.fit_transform(self.train[FEATURES])
        self.y = self.train[self.target].to_numpy(dtype=float)
        if self.method == 'GPR':
            self.mean = float(self.y.mean())
            self.constant = bool(np.ptp(self.y) < 1e-10)
            self.scale = max(float(self.y.std()), SCALE_FLOOR[self.target])
            kernel = ConstantKernel(1., (.01, 100.)) * Matern(length_scale=1., length_scale_bounds=(.1, 10.), nu=1.5) + WhiteKernel(.01, (.001, 1.))
            # Downweight shared contexts; this is not a correlated-noise likelihood.
            alpha = .0025 / self.train.ContextWeight.to_numpy(dtype=float)
            self.gp = GaussianProcessRegressor(kernel=kernel, alpha=alpha,
                                              optimizer=None if self.constant else 'fmin_l_bfgs_b',
                                              n_restarts_optimizer=0, random_state=42)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always', ConvergenceWarning)
                self.gp.fit(self.x, (self.y - self.mean) / self.scale)
            self.warnings = [str(x.message) for x in caught]
        self.status = 'Research fit; source approval retained'
        return self

    def predict(self, query):
        result = dict(Target=self.target, Model=self.method, Prediction=None, Std=None,
                      Lower95=None, Upper95=None, Support='Unavailable', NearestCase=None,
                      NearestPass=None, Distance=None, Note=self.status)
        if self.train.empty:
            return result
        if any(k not in query or pd.isna(query[k]) for k in FEATURES):
            result['Note'] = 'Missing query input'
            return result
        if any(not np.isfinite(float(query[k])) for k in NUM) or query['Thickness'] <= 0 or not 0 < query['GrooveAngle'] < 180 or query['RootGap'] < 0:
            result['Note'] = 'Invalid geometry'
            return result
        same = (self.train.Position == query['Position']) & (self.train.PassRole == query['PassRole'])
        if not same.any():
            result['Note'] = 'No training support for position / role'
            return result
        q = self.pre.transform(pd.DataFrame([query])[FEATURES])
        distances = np.linalg.norm(self.x - q, axis=1)
        neighbors = self.train.loc[same, ['CaseID', 'ObservationID']].copy()
        neighbors['Distance'] = distances[same.to_numpy()]
        neighbors = neighbors.sort_values(['Distance', 'CaseID', 'ObservationID'])
        nearest = neighbors.iloc[0]
        result.update(NearestCase=nearest.CaseID, NearestPass=nearest.ObservationID, Distance=float(nearest.Distance))
        subset = self.train.loc[same]
        out = [k for k in NUM if query[k] < subset[k].min() or query[k] > subset[k].max()]
        result['Support'] = 'Extrapolation: ' + ', '.join(out) if out else 'Within marginal ranges (not a validity guarantee)'
        if self.method == 'Baseline':
            # One contribution per Case avoids favoring cases with more passes.
            neighbors['Value'] = self.train.loc[neighbors.index, self.target]
            per_case = neighbors.groupby('CaseID', sort=False).agg(Distance=('Distance', 'min'), Value=('Value', 'mean')).sort_values('Distance')
            selected = per_case.head(3)
            exact = selected.Distance < 1e-10
            if exact.any():
                prediction = float(selected.loc[exact, 'Value'].mean())
            else:
                prediction = float(np.average(selected.Value, weights=1 / selected.Distance))
            result.update(Prediction=prediction, Note='Up to 3 nearest cases; inverse-distance interpolation; no probabilistic uncertainty')
        else:
            mu, std = self.gp.predict(q, return_std=True)
            prediction, sigma = float(mu[0] * self.scale + self.mean), float(std[0] * self.scale)
            result.update(Prediction=prediction, Std=sigma, Lower95=prediction - 1.96 * sigma, Upper95=prediction + 1.96 * sigma,
                          Note='Uncalibrated GP interval; includes configured WhiteKernel noise; ' + ('constant labels: prior-scale dependent' if self.constant else 'estimated from training fold'))
        return result


def fit_models(frame, approved_only=False):
    return {f'{target}_{method}': TargetModel(target, method).fit(frame, approved_only)
            for target in TARGETS for method in ['Baseline', 'GPR']}


def evaluate(frame, group_column='CaseID'):
    predictions, metrics, splits = [], [], []
    for target in TARGETS:
        data = frame.loc[frame[target + '_Eligible']].copy().reset_index(drop=True)
        groups = data[group_column]
        for method in ['Baseline', 'GPR']:
            start = len(predictions)
            if groups.nunique() >= 2:
                for fold, (tr, te) in enumerate(LeaveOneGroupOut().split(data[FEATURES], groups=groups)):
                    train, test = data.iloc[tr], data.iloc[te]
                    assert not set(train.CaseID) & set(test.CaseID)
                    splits.append({'Target': target, 'Model': method, 'Grouping': group_column, 'Fold': fold,
                                   'TrainCases': sorted(set(train.CaseID)), 'TestCases': sorted(set(test.CaseID))})
                    model = TargetModel(target, method).fit(train)
                    for _, row in test.iterrows():
                        pred = model.predict(row.to_dict())
                        predictions.append({**pred, 'CaseID': row.CaseID, 'PassID': row.PassID,
                                            'PassRole': row.PassRole, 'Actual': float(row[target]),
                                            'Fold': fold, 'Grouping': group_column})
            scored = [p for p in predictions[start:] if p['Prediction'] is not None]
            metric = {'Grouping': group_column, 'Target': target, 'Model': method,
                      'Cases': int(data.CaseID.nunique()), 'Sources': int(data.SourceGroup.nunique()),
                      'N': len(scored), 'EligibleContexts': len(data), 'Coverage': len(scored) / len(data) if len(data) else 0.,
                      'MAE': None, 'RMSE': None, 'CaseMacroMAE': None, 'CaseMacroRMSE': None,
                      'Coverage95': None, 'Status': 'Insufficient independent groups / labels'}
            if scored:
                scored = pd.DataFrame(scored)
                e = scored.Prediction - scored.Actual
                case_mae = e.abs().groupby(scored.CaseID).mean()
                case_mse = (e ** 2).groupby(scored.CaseID).mean()
                metric.update(MAE=float(e.abs().mean()), RMSE=float(np.sqrt((e ** 2).mean())),
                              CaseMacroMAE=float(case_mae.mean()), CaseMacroRMSE=float(np.sqrt(case_mse).mean()),
                              Status='Descriptive only: single source, constant targets' if data[target].nunique() <= 1 else 'Grouped out-of-fold')
                if method == 'GPR':
                    metric['Coverage95'] = float(((scored.Actual >= scored.Lower95) & (scored.Actual <= scored.Upper95)).mean())
            metrics.append(metric)
    return pd.DataFrame(metrics), pd.DataFrame(predictions), splits

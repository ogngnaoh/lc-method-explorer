"""Development-only out-of-fold method-median baseline; no holdout scoring."""
from datetime import datetime, timezone
import importlib.metadata
import json
import platform
import time

import numpy as np
import pandas as pd

from chromrt.prepare import ROOT, sha256, write_json
from chromrt.splits import validate_splits, make_splits


def predict_method_medians(train, validation):
    medians = train.groupby('method_id')['rt_min'].median()
    predicted = validation['method_id'].map(medians)
    if predicted.isna().any():
        raise ValueError('Validation contains an unsupported method')
    return predicted.to_numpy()


def metrics(data):
    error = data['prediction_min'].to_numpy() - data['rt_min'].to_numpy()
    absolute = np.abs(error)
    group_mae = data.assign(absolute_error=absolute).groupby('compound_group')['absolute_error'].mean()
    return {'observations': len(data), 'compound_groups': data['compound_group'].nunique(),
            'mae_min': float(absolute.mean()), 'rmse_min': float(np.sqrt(np.mean(error**2))),
            'median_absolute_error_min': float(np.median(absolute)),
            'p90_absolute_error_min': float(np.quantile(absolute,.9)),
            'mean_group_mae_min': float(group_mae.mean())}


def development_data():
    prepared = ROOT/'data/processed'
    protocol = json.loads((ROOT/'data/splits/protocol.json').read_text())
    for name, expected in protocol['input_sha256'].items():
        if sha256(prepared/name) != expected:
            raise ValueError(f'Frozen input changed: {name}')
    splits = pd.read_csv(ROOT/'data/splits/compounds.csv')
    validate_splits(splits)
    expected = make_splits(pd.read_csv(prepared/'compounds.csv'))
    if not splits.equals(expected):
        raise ValueError('Frozen split differs from the declared protocol')
    data = pd.read_csv(prepared/'observations.csv').merge(splits, on='compound_id', validate='many_to_one')
    # Filter before fitting, scoring, or selecting any model.
    return data.loc[data['partition'] == 'development'].copy()


def main():
    start = time.perf_counter()
    data = development_data()
    predictions = []
    for fold in range(5):
        train = data.loc[data['cv_fold'] != fold]
        valid = data.loc[data['cv_fold'] == fold].copy()
        if set(train['compound_group']) & set(valid['compound_group']):
            raise ValueError('Group leakage')
        valid['prediction_min'] = predict_method_medians(train, valid)
        predictions.append(valid)
    oof = pd.concat(predictions).sort_values(['compound_id','method_id'])
    folder = ROOT/'reports/baseline'
    folder.mkdir(exist_ok=True)
    oof[['compound_id','compound_group','method_id','cv_fold','rt_min','prediction_min']].to_csv(
        folder/'development_predictions.csv', index=False, float_format='%.12g')
    by_method = [{'method_id': name, **metrics(group)} for name, group in oof.groupby('method_id')]
    pd.DataFrame(by_method).to_csv(folder/'by_method.csv', index=False)
    result = {'model': 'per-method training median', 'evaluation': 'development 5-fold grouped out-of-fold',
              'holdout_evaluated': False, 'overall': metrics(oof),
              'folds': {str(f):metrics(g) for f,g in oof.groupby('cv_fold')},
              'runtime_seconds': time.perf_counter()-start,
              'run_at_utc': datetime.now(timezone.utc).isoformat(),
              'split_sha256': sha256(ROOT/'data/splits/compounds.csv'),
              'data_protocol_sha256': sha256(ROOT/'data/splits/protocol.json'),
              'lock_sha256': sha256(ROOT/'uv.lock'),
              'python_version': platform.python_version(), 'platform': platform.platform(),
              'source_sha256': {str(p.relative_to(ROOT)):sha256(p) for p in sorted((ROOT/'chromrt').glob('*.py'))},
              'versions': {p:importlib.metadata.version(p) for p in ['numpy','pandas','rdkit','scikit-learn','openpyxl']}}
    write_json(folder/'metrics.json',result)
    print(json.dumps(result['overall'],indent=2))
    print('Final holdout remains unevaluated.')


if __name__ == '__main__':
    main()

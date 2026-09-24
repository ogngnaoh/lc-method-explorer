"""Read-only inference adapter; the frozen experiment stays unchanged."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
from chromrt.chemistry import describe
from chromrt.experiment import provenance
from chromrt.prepare import sha256
from chromrt.recommend import rank_methods

EXPERIMENT = 'mcmrt-v3-compound-v1'
RESULTS = ROOT / 'reports/experiments' / EXPERIMENT
LABELS = {'xgb_depth5': 'XGBoost', 'rf_leaf1': 'Random Forest', 'median': 'Method median'}


def load_bundle():
    selection = json.loads((RESULTS / 'selection.json').read_text())
    metrics = json.loads((RESULTS / 'holdout/metrics.json').read_text())
    if provenance() != selection['hashes'] or sha256(RESULTS / 'selection.json') != metrics['selection_sha256']:
        raise ValueError('Frozen experiment verification failed. Run scripts/verify_results.py.')
    protocol = json.loads((ROOT / 'data/splits/protocol.json').read_text())
    for name, checksum in protocol['input_sha256'].items():
        if sha256(ROOT / 'data/processed' / name) != checksum:
            raise ValueError(f'Prepared data changed: {name}')
    model_dir = ROOT / 'models' / EXPERIMENT
    for name, checksum in metrics['model_hashes'].items():
        if sha256(model_dir / name) != checksum:
            raise ValueError(f'Saved model changed: {name}')
    return {
        'models': {key: joblib.load(model_dir / f'{key}.joblib') for key in LABELS},
        'schema': json.loads((ROOT / 'data/processed/feature_schema.json').read_text()),
        'compounds': pd.read_csv(ROOT / 'data/processed/compounds.csv'),
        'methods': pd.read_csv(ROOT / 'data/processed/methods.csv'),
        'observations': pd.read_csv(ROOT / 'data/processed/observations.csv'),
        'gradients': pd.read_csv(ROOT / 'data/processed/gradients.csv'),
        'splits': pd.read_csv(ROOT / 'data/splits/compounds.csv'),
        'metrics': metrics, 'selection': selection,
    }


def predict(bundle, model_id, low, high, *, compound_id=None, smiles=None):
    if (compound_id is None) == (smiles is None):
        raise ValueError('Provide either a held-out compound or a SMILES string.')
    if compound_id is not None:
        holdout = bundle['splits'].query("partition == 'holdout'").compound_id
        if compound_id not in set(holdout):
            raise ValueError('Example must belong to the fixed holdout.')
        molecular = bundle['compounds'].set_index('compound_id').loc[compound_id].to_dict()
    else:
        if len(smiles) > 10000:
            raise ValueError('Please use a SMILES string under 10,000 characters.')
        molecular = describe(smiles)
    candidates = bundle['methods'].copy()
    schema = bundle['schema']
    for name in schema['molecular']:
        candidates[name] = molecular[name]
    fields = schema['molecular'] + schema['method_numeric'] + schema['method_categorical']
    model = bundle['models'][model_id]
    candidates['prediction_min'] = (candidates.method_id.map(model) if model_id == 'median'
                                    else model.predict(candidates[fields]))
    if not np.isfinite(candidates.prediction_min).all():
        raise ValueError('Model returned a nonfinite prediction.')
    candidates['physical_status'] = np.where(
        (candidates.prediction_min < 0) | (candidates.prediction_min > candidates.run_time_min),
        'Invalid time', 'Within run')
    # Measured truth is joined only AFTER ordering and never influences ranking.
    ranked = rank_methods(candidates, low, high).reset_index(drop=True)
    ranked.insert(0, 'rank', np.arange(1, len(ranked) + 1))
    if compound_id is not None:
        truth = bundle['observations'].query('compound_id == @compound_id')[['method_id', 'rt_min']]
        ranked = ranked.merge(truth, on='method_id', how='left', validate='one_to_one')
    else:
        ranked['rt_min'] = np.nan
    return molecular, ranked


def export_frame(ranked, model_id, low, high, reveal=False):
    fields = ['rank', 'method_id', 'prediction_min', 'physical_status', 'predicted_window_distance',
              'run_time_min', 'column_name', 'column_dimensions_raw', 'column_temperature_c',
              'mobile_phase_a_raw', 'mobile_phase_b_raw']
    if reveal:
        fields += ['rt_min']
    exported = ranked[fields].copy()
    exported['model'] = model_id
    exported['window_low_min'] = low
    exported['window_high_min'] = high
    exported['experiment'] = EXPERIMENT
    return exported

"""Verify frozen result artifacts and saved-model predictions without fitting."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import joblib
import numpy as np
import pandas as pd
from chromrt.experiment import feature_frame,provenance
from chromrt.prepare import sha256


def main():
    config=json.loads((ROOT/'config/experiment.json').read_text())
    folder=ROOT/'reports/experiments'/config['experiment_id']
    selection=json.loads((folder/'selection.json').read_text())
    result=json.loads((folder/'holdout/metrics.json').read_text())
    if provenance()!=selection['hashes']:
        raise ValueError('Current experiment inputs/code do not match the frozen run')
    if sha256(folder/'selection.json')!=result['selection_sha256']:
        raise ValueError('Selection record changed')
    splits=pd.read_csv(ROOT/'data/splits/compounds.csv')
    expected=set(splits.loc[splits.partition=='holdout','compound_id'])
    truth=pd.read_csv(ROOT/'data/processed/observations.csv')
    model_dir=ROOT/'models'/config['experiment_id']
    for name,checksum in result['model_hashes'].items():
        if sha256(model_dir/name)!=checksum:raise ValueError(f'Model artifact changed: {name}')
    for name in selection['best_by_family'].values():
        pred=pd.read_csv(folder/f'holdout/{name}_predictions.csv')
        if set(pred.compound_id)!=expected or pred.duplicated(['compound_id','method_id']).any():
            raise ValueError('Holdout coverage or uniqueness mismatch')
        merged=pred.merge(truth[['compound_id','method_id','rt_min']],on=['compound_id','method_id'],
                          suffixes=('_saved','_source'),validate='one_to_one')
        np.testing.assert_allclose(merged.rt_min_saved,merged.rt_min_source)
        np.testing.assert_allclose(abs(pred.rt_min-pred.prediction_min).mean(),result['models'][name]['retention']['mae_min'])
        model=joblib.load(model_dir/f'{name}.joblib')
        if name=='median': reproduced=pred.method_id.map(model).to_numpy()
        else:
            x,_=feature_frame(pred)
            reproduced=model.predict(x)
        np.testing.assert_allclose(reproduced,pred.prediction_min,rtol=1e-6)
    print('Verified frozen provenance, model hashes, holdout coverage, saved predictions, and MAE.')


if __name__=='__main__':main()

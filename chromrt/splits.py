"""Freeze compound groups before model selection. Never overwrite changed splits."""
import json

import pandas as pd
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

from chromrt.prepare import ROOT, sha256, write_json

SEED = 20260924


def make_splits(compounds):
    result = compounds[['compound_id','compound_group']].sort_values('compound_id').reset_index(drop=True).copy()
    train, test = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=SEED).split(
        result, groups=result['compound_group']))
    result['partition'] = 'development'
    result.loc[test, 'partition'] = 'holdout'
    result['cv_fold'] = -1
    development = result.loc[train]
    splitter = GroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    for fold, (_, validation) in enumerate(splitter.split(development, groups=development['compound_group'])):
        result.loc[development.iloc[validation].index, 'cv_fold'] = fold
    validate_splits(result)
    return result


def validate_splits(splits):
    if splits['compound_id'].duplicated().any():
        raise ValueError('Duplicate compound split assignment')
    if splits.groupby('compound_group')['partition'].nunique().max() != 1:
        raise ValueError('Compound group crosses the holdout boundary')
    if splits.groupby('compound_group')['cv_fold'].nunique().max() != 1:
        raise ValueError('Compound group crosses CV folds')
    dev = splits['partition'] == 'development'
    if set(splits['partition']) != {'development','holdout'} or set(splits.loc[dev,'cv_fold']) != set(range(5)):
        raise ValueError('Incomplete split assignment')
    if not (splits.loc[~dev,'cv_fold'] == -1).all():
        raise ValueError('Holdout assigned a CV fold')


def main():
    compounds = pd.read_csv(ROOT / 'data/processed/compounds.csv')
    result = make_splits(compounds)
    directory = ROOT / 'data/splits'
    directory.mkdir(exist_ok=True)
    path = directory / 'compounds.csv'
    text = result.to_csv(index=False)
    if path.exists() and path.read_text() != text:
        raise ValueError('Frozen split would change. Review and version a new experiment explicitly.')
    state = {'seed': SEED, 'holdout_group_fraction': .2, 'cv_folds': 5,
             'input_sha256': {p.name:sha256(p) for p in sorted((ROOT/'data/processed').glob('*.csv'))}}
    state_path = directory/'protocol.json'
    if state_path.exists() and json.loads(state_path.read_text()) != state:
        raise ValueError('Prepared data changed after splits were frozen')
    path.write_text(text)
    write_json(state_path, state)
    counts = result.groupby(['partition','cv_fold']).agg(compounds=('compound_id','size'), groups=('compound_group','nunique'))
    print(counts.to_string())


if __name__ == '__main__':
    main()

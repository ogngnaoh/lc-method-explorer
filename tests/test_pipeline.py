import numpy as np
import pandas as pd
import pytest

from chromrt.baseline import predict_method_medians
from chromrt.chemistry import describe
from chromrt.methods import dimensions, mobile_phase, encode_method
from chromrt.splits import make_splits, validate_splits
from chromrt.prepare import ROOT
import json


def test_structure_groups_prevent_salt_stereo_and_tautomer_leakage():
    def key(s): return describe(s)['compound_group']
    assert key('CC(=O)[O-].[Na+]') == key('CC(=O)O')
    assert key('N[C@@H](C)C(=O)O') == key('N[C@H](C)C(=O)O')
    assert key('CC(=O)C') == key('C=C(O)C')
    assert key('CCO') != key('CCCO')
    with pytest.raises(ValueError): describe('not-a-molecule')
    with pytest.raises(ValueError): describe('CCO trailing-name')


def test_method_units_and_premixed_solvent():
    assert dimensions('2.1 x 50 mm,1.8 μm')['column_length_mm'] == 50
    assert dimensions('100x2.1 mm, 1.9 μm')['column_id_mm'] == 2.1
    settings = {'Analytical column':'example', 'Column dimensions':'100 x 2.1 mm, 1.8 μm',
                'Column temperature (°C)':30, 'Sample temperature (°C)':10,
                'Mobile phase A':'Water/methanol=90:10, v/v with 5 mM ammonium formate',
                'Mobile phase B':'Methanol with 5 mM ammonium formate'}
    f = encode_method('M01',settings,[[0,.2,0],[10,.4,100]])
    assert f['knot_0_meoh_fraction'] == .1
    assert f['knot_1_meoh_fraction'] == 1
    assert f['knot_1_flow_ml_min'] == .4
    assert f['knot_6_time_min'] == 10
    with pytest.raises(ValueError): mobile_phase('Unknown solvent')
    with pytest.raises(ValueError): encode_method('M01',settings,[[0,.2,0],[0,.2,100]])


def test_duplicate_parent_groups_stay_together_and_splits_reproduce():
    compounds = pd.DataFrame({'compound_id': range(60), 'compound_group':[f'g{i//2}' for i in range(60)]})
    a,b = make_splits(compounds),make_splits(compounds.sample(frac=1,random_state=3))
    pd.testing.assert_frame_equal(a,b)
    assert a.groupby('compound_group')['partition'].nunique().max() == 1
    assert a.groupby('compound_group')['cv_fold'].nunique().max() == 1
    broken = a.copy()
    pair = broken.index[broken.compound_group == 'g0']
    broken.loc[pair[0],'partition'] = 'holdout'
    broken.loc[pair[1],'partition'] = 'development'
    with pytest.raises(ValueError): validate_splits(broken)


def test_baseline_uses_training_labels_only():
    train = pd.DataFrame({'method_id':['A','A','A','B'], 'rt_min':[1,2,20,9]})
    validation = pd.DataFrame({'method_id':['A','B'], 'rt_min':[1000,-1000]})
    np.testing.assert_allclose(predict_method_medians(train,validation),[2,9])
    validation['rt_min'] = 0
    np.testing.assert_allclose(predict_method_medians(train,validation),[2,9])
    with pytest.raises(ValueError):
        predict_method_medians(train,pd.DataFrame({'method_id':['C']}))


def test_prepared_data_integrity_and_predictor_boundary():
    compounds = pd.read_csv(ROOT/'data/processed/compounds.csv')
    methods = pd.read_csv(ROOT/'data/processed/methods.csv')
    observations = pd.read_csv(ROOT/'data/processed/observations.csv')
    schema = json.loads((ROOT/'data/processed/feature_schema.json').read_text())
    assert len(compounds) == 343 and len(methods) == 30 and len(observations) == 10073
    assert compounds['inchi_connectivity_matches'].all()
    assert compounds['compound_group'].nunique() == 341
    assert set(observations.compound_id) == set(compounds.compound_id)
    assert set(observations.method_id) == set(methods.method_id)
    assert np.isfinite(compounds[schema['molecular']].to_numpy()).all()
    assert np.isfinite(methods[schema['method_numeric']].to_numpy()).all()
    all_features = set(sum(schema.values(), []))
    assert not all_features & {'rt_min','retention_factor_source','rsd_source','compound_id','method_id','dead_time_min'}
    assert not observations.duplicated(['compound_id','method_id']).any()

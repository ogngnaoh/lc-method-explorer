"""Check the demo's scientific boundaries against the frozen experiment."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from service import load_bundle, predict, export_frame, RESULTS, LABELS

@pytest.fixture(scope='module')
def bundle():
    return load_bundle()


def test_saved_predictions_and_missingness(bundle):
    for model in LABELS:
        saved = pd.read_csv(RESULTS/f'holdout/{model}_predictions.csv')
        rows = []
        for cid in saved.compound_id.unique():
            _, ranked = predict(bundle, model, 5, 10, compound_id=cid)
            assert len(ranked) == 30
            ranked['compound_id'] = cid
            rows.append(ranked)
        actual = pd.concat(rows).merge(saved, on=['compound_id','method_id'],suffixes=('_app','_saved'))
        assert len(actual) == 2047
        np.testing.assert_allclose(actual.prediction_min_app,actual.prediction_min_saved,rtol=1e-6)
        np.testing.assert_allclose(actual.rt_min_app,actual.rt_min_saved)
    _, incomplete = predict(bundle,'xgb_depth5',5,10,compound_id=45)
    assert incomplete.rt_min.isna().any()


def test_new_structure_has_no_truth_and_export_hides_it(bundle):
    known = bundle['compounds'].query('compound_id == 52').source_smiles.iloc[0]
    _, rows = predict(bundle,'xgb_depth5',5,10,smiles=known)
    assert rows.rt_min.isna().all()
    assert 'rt_min' not in export_frame(rows,'xgb_depth5',5,10)
    assert 'rt_min' in export_frame(rows,'xgb_depth5',5,10,True)
    with pytest.raises(ValueError): predict(bundle,'xgb_depth5',5,10,smiles='invalid')
    with pytest.raises(ValueError): predict(bundle,'xgb_depth5',10,5,smiles='CCO')


def test_negative_values_are_flagged_not_clipped(bundle):
    saved = pd.read_csv(RESULTS/'holdout/xgb_depth5_predictions.csv')
    bad = saved.query('prediction_min < 0').iloc[0]
    _, rows = predict(bundle,'xgb_depth5',0,2,compound_id=bad.compound_id)
    row = rows.set_index('method_id').loc[bad.method_id]
    assert row.prediction_min < 0 and row.physical_status == 'Invalid time'


def test_interface_states():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == 'LC Method Explorer'
    app.sidebar.checkbox[0].check().run()
    assert not app.exception
    assert any('Rank 1' in x.value for x in app.info)
    app.sidebar.number_input[0].set_value(11.0).run()
    assert any('upper limit' in x.value for x in app.error)
    app.sidebar.number_input[0].set_value(5.0)
    app.sidebar.radio[0].set_value('New SMILES').run()
    app.sidebar.text_area[0].set_value('not-a-smiles').run()
    assert not app.exception and len(app.error) == 1
    app.sidebar.text_area[0].set_value('CCO').run()
    assert not app.exception and not app.error

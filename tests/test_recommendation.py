import numpy as np
import pandas as pd
import pytest

from chromrt.recommend import window_distance,rank_methods,evaluate_ranking,fixed_method_orders
from chromrt.experiment import feature_frame,build_model
from chromrt.baseline import development_data


def panel():
    return pd.DataFrame({'compound_id':[1,1,1],'compound_group':['g','g','g'],
                         'method_id':['A','B','C'],'rt_min':[4.,8.,12.],
                         'prediction_min':[9.,4.,15.],'run_time_min':[20.,20.,20.]})


def test_ranking_does_not_use_measured_retention_and_regret_is_measured():
    p=panel()
    assert rank_methods(p,3,5).method_id.tolist()==['B','A','C']
    p['rt_min']=[500,-100,1]
    assert rank_methods(p,3,5).method_id.tolist()==['B','A','C']
    cases,summary=evaluate_ranking(panel(),[[3,5]],expected_methods=3)
    assert cases.iloc[0].excess_distance_min==3
    assert not cases.iloc[0].top1_hit and cases.iloc[0].top3_hit and cases.iloc[0].feasible
    assert summary['overall']['top1_hit_rate']==0


def test_infeasible_windows_and_incomplete_panels_remain_explicit():
    p=panel()
    extra=p.iloc[:2].copy();extra['compound_id']=2;extra['compound_group']='h'
    cases,summary=evaluate_ranking(pd.concat([p,extra]),[[30,40]],expected_methods=3)
    assert summary['excluded_incomplete_compounds']==1
    assert summary['overall']['feasible_rate']==0
    assert summary['overall']['top1_hit_given_feasible'] is None
    assert cases.iloc[0].excess_distance_min==0
    with pytest.raises(ValueError): window_distance([1],5,3)
    with pytest.raises(ValueError): window_distance([np.nan],3,5)


def test_fixed_ranking_is_learned_from_training_measurements():
    order=fixed_method_orders(panel(),[[3,5]],expected_methods=3)
    assert order['3-5']==['A','B','C']
    cases,_=evaluate_ranking(panel(),[[3,5]],order,expected_methods=3)
    assert cases.iloc[0].top1_hit


def test_both_model_pipelines_fit_without_target_columns():
    data=development_data().iloc[:90]
    x,schema=feature_frame(data)
    assert 'rt_min' not in x and 'compound_id' not in x and 'method_id' not in x
    for family in ['random_forest','xgboost']:
        c={'family':family,'params':{'n_estimators':3,'max_depth':2}}
        model=build_model(c,schema,{'seed':1,'workers':1})
        model.fit(x,data.rt_min)
        p=model.predict(x)
        assert len(p)==len(data) and np.isfinite(p).all()

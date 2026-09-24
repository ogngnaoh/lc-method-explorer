"""Bounded grouped-CV selection followed by a separate final evaluation."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import platform
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

from chromrt.baseline import development_data, metrics, predict_method_medians
from chromrt.prepare import ROOT, sha256, write_json
from chromrt.recommend import evaluate_ranking, fixed_method_orders

CONFIG_PATH = ROOT/'config/experiment.json'


def provenance():
    paths = [CONFIG_PATH,ROOT/'reports/EVALUATION_PROTOCOL.md',ROOT/'uv.lock',ROOT/'data/splits/compounds.csv',ROOT/'data/splits/protocol.json',
             ROOT/'data/processed/feature_schema.json',*sorted((ROOT/'chromrt').glob('*.py'))]
    return {str(p.relative_to(ROOT)):sha256(p) for p in paths}


def feature_frame(data):
    folder = ROOT/'data/processed'
    schema = json.loads((folder/'feature_schema.json').read_text())
    molecular = schema['molecular']
    method = schema['method_numeric']+schema['method_categorical']
    frame = data[['compound_id','method_id']].merge(
        pd.read_csv(folder/'compounds.csv')[['compound_id']+molecular], on='compound_id',validate='many_to_one').merge(
        pd.read_csv(folder/'methods.csv')[['method_id']+method],on='method_id',validate='many_to_one')
    if len(frame) != len(data) or frame[molecular+method].isna().any().any():
        raise ValueError('Incomplete feature join')
    return frame[molecular+method],schema


def with_duration(data):
    return data.merge(pd.read_csv(ROOT/'data/processed/methods.csv')[['method_id','run_time_min']],
                      on='method_id',validate='many_to_one')


def build_model(candidate, schema, config):
    encoder = ColumnTransformer([
        ('numeric','passthrough',schema['molecular']+schema['method_numeric']),
        ('column',OneHotEncoder(sparse_output=False,handle_unknown='error'),schema['method_categorical'])])
    if candidate['family'] == 'random_forest':
        model = RandomForestRegressor(random_state=config['seed'],n_jobs=config['workers'],**candidate['params'])
    elif candidate['family'] == 'xgboost':
        model = XGBRegressor(objective='reg:squarederror',tree_method='hist',device='cpu',
                             random_state=config['seed'],n_jobs=config['workers'],**candidate['params'])
    else:
        raise ValueError('Unknown candidate family')
    return Pipeline([('features',encoder),('regressor',model)])


def save_predictions(folder, name, data):
    cols = ['compound_id','compound_group','method_id','cv_fold','rt_min','prediction_min','run_time_min']
    data[cols].sort_values(['compound_id','method_id']).to_csv(folder/f'{name}_predictions.csv',index=False,float_format='%.12g')


def save_scores(folder, name, data, config, fixed_orders=None):
    cases,ranking = evaluate_ranking(data,config['windows_min'],fixed_orders)
    cases.to_csv(folder/f'{name}_ranking_cases.csv',index=False)
    if fixed_orders is not None:
        return {'ranking':ranking}
    by_method = [{'method_id':m,**metrics(g)} for m,g in data.groupby('method_id')]
    pd.DataFrame(by_method).to_csv(folder/f'{name}_by_method.csv',index=False)
    return {'retention':metrics(data),'ranking':ranking,
            'predictions_below_zero':int((data.prediction_min<0).sum()),
            'predictions_after_run_end':int((data.prediction_min>data.run_time_min).sum())}


def develop(config, folder):
    selection_path = folder/'selection.json'
    if selection_path.exists():
        raise ValueError('Development selection already frozen; choose a new experiment ID for a new experiment')
    start = time.perf_counter()
    initial = provenance()
    write_json(folder/'protocol_snapshot.json',{'config':config,'hashes':initial,'started_at_utc':datetime.now(timezone.utc).isoformat()})
    data = with_duration(development_data())
    candidates = [{'id':'median','family':'baseline','params':{}},*config['candidates']]
    rows, summaries = [], {}
    for candidate in candidates:
        candidate_start = time.perf_counter()
        predictions = []
        for fold in range(5):
            train = data.loc[data.cv_fold != fold]
            valid = data.loc[data.cv_fold == fold].copy()
            if set(train.compound_group) & set(valid.compound_group):
                raise ValueError('Group leakage')
            if candidate['family'] == 'baseline':
                valid['prediction_min'] = predict_method_medians(train,valid)
            else:
                x_train,schema = feature_frame(train)
                x_valid,_ = feature_frame(valid)
                model = build_model(candidate,schema,config)
                model.fit(x_train,train.rt_min)
                valid['prediction_min'] = model.predict(x_valid)
            predictions.append(valid)
        oof = pd.concat(predictions).sort_values(['compound_id','method_id'])
        name = candidate['id']
        save_predictions(folder,name,oof)
        summaries[name] = save_scores(folder,name,oof,config)
        score = summaries[name]['retention']['mae_min']
        rows.append({'candidate':name,'family':candidate['family'],'mae_min':score,
                     'runtime_seconds':time.perf_counter()-candidate_start})
        pd.DataFrame(rows).to_csv(folder/'candidate_comparison.csv',index=False)
        print(f'{name}: development MAE {score:.4f} min; {rows[-1]["runtime_seconds"]:.1f}s',flush=True)
    # Independent no-personalization comparator, learned only on each training fold.
    fixed_cases=[]
    for fold in range(5):
        train=data.loc[data.cv_fold != fold]
        valid=data.loc[data.cv_fold == fold]
        orders=fixed_method_orders(train,config['windows_min'])
        cases,_=evaluate_ranking(valid,config['windows_min'],orders)
        fixed_cases.append(cases)
    pd.concat(fixed_cases).to_csv(folder/'fixed_ranking_cases.csv',index=False)
    best={}
    for family in ['baseline','random_forest','xgboost']:
        best[family]=min((r for r in rows if r['family']==family),key=lambda r:(r['mae_min'],r['candidate']))['candidate']
    winner=min(rows,key=lambda r:(r['mae_min'],r['candidate']))['candidate']
    if provenance()!=initial:
        raise ValueError('Inputs or code changed during development run')
    selection={'experiment_id':config['experiment_id'],'winner':winner,'best_by_family':best,
               'candidates':rows,'development_scores':summaries,'hashes':initial,
               'runtime_seconds':time.perf_counter()-start,'completed_at_utc':datetime.now(timezone.utc).isoformat(),
               'holdout_evaluated':False}
    write_json(selection_path,selection)
    print(f'Frozen development winner: {winner}. Holdout remains unevaluated.',flush=True)


def paired_mae_interval(baseline,selected,config):
    pair=baseline[['compound_id','method_id','compound_group','rt_min','prediction_min']].merge(
        selected[['compound_id','method_id','prediction_min']],on=['compound_id','method_id'],
        suffixes=('_baseline','_selected'),validate='one_to_one')
    pair['improvement']=abs(pair.prediction_min_baseline-pair.rt_min)-abs(pair.prediction_min_selected-pair.rt_min)
    groups=pair.groupby('compound_group').improvement.agg(['sum','count'])
    rng=np.random.default_rng(config['seed'])
    picks=rng.integers(len(groups),size=(config['bootstrap_samples'],len(groups)))
    boot=groups['sum'].to_numpy()[picks].sum(axis=1)/groups['count'].to_numpy()[picks].sum(axis=1)
    return {'meaning':'median baseline MAE minus selected model MAE; positive favors selected model',
            'estimate_min':float(pair.improvement.mean()),'interval_95_min':[float(v) for v in np.quantile(boot,[.025,.975])],
            'resampling_unit':'compound group','replicates':config['bootstrap_samples']}


def final_evaluation(config,folder):
    selection=json.loads((folder/'selection.json').read_text())
    if provenance()!=selection['hashes']:
        raise ValueError('Code, settings, or inputs changed after model selection')
    output=folder/'holdout'
    if (output/'metrics.json').exists():
        raise ValueError('Final evaluation already exists; it will not be overwritten')
    output.mkdir(exist_ok=True)
    start=time.perf_counter()
    dev=with_duration(development_data())
    splits=pd.read_csv(ROOT/'data/splits/compounds.csv')
    holdout=with_duration(pd.read_csv(ROOT/'data/processed/observations.csv').merge(
        splits.loc[splits.partition=='holdout'],on='compound_id',validate='many_to_one'))
    if set(dev.compound_group)&set(holdout.compound_group):
        raise ValueError('Holdout leakage')
    x_dev,schema=feature_frame(dev)
    x_test,_=feature_frame(holdout)
    definitions={c['id']:c for c in config['candidates']}
    summaries,predictions={},{}
    model_dir=ROOT/'models'/config['experiment_id']
    model_dir.mkdir(parents=True,exist_ok=True)
    for name in selection['best_by_family'].values():
        pred=holdout.copy()
        if name=='median':
            pred['prediction_min']=predict_method_medians(dev,holdout)
            joblib.dump(dev.groupby('method_id').rt_min.median(),model_dir/'median.joblib')
        else:
            model=build_model(definitions[name],schema,config)
            model.fit(x_dev,dev.rt_min)
            pred['prediction_min']=model.predict(x_test)
            joblib.dump(model,model_dir/f'{name}.joblib',compress=3)
        predictions[name]=pred
        save_predictions(output,name,pred)
        summaries[name]=save_scores(output,name,pred,config)
        print(f'{name}: holdout MAE {summaries[name]["retention"]["mae_min"]:.4f} min',flush=True)
    orders=fixed_method_orders(dev,config['windows_min'])
    write_json(model_dir/'fixed_orders.json',orders)
    summaries['fixed']=save_scores(output,'fixed',holdout,config,orders)
    result={'experiment_id':config['experiment_id'],'deployment_model':selection['winner'],
            'models':summaries,'paired_mae_improvement':paired_mae_interval(predictions['median'],predictions[selection['winner']],config),
            'selection_sha256':sha256(folder/'selection.json'),'hashes':selection['hashes'],
            'model_hashes':{p.name:sha256(p) for p in sorted(model_dir.iterdir())},
            'python_version':platform.python_version(),'platform':platform.platform(),
            'versions':{p:importlib.metadata.version(p) for p in ['numpy','pandas','rdkit','scikit-learn','xgboost']},
            'runtime_seconds':time.perf_counter()-start,'evaluated_at_utc':datetime.now(timezone.utc).isoformat(),
            'holdout_evaluated':True}
    write_json(output/'metrics.json',result)
    write_json(model_dir/'metadata.json',{'selected_model':selection['winner'],'feature_schema':schema,
                                         'experiment_id':config['experiment_id'],'training_partition':'development only'})
    print(json.dumps(result['paired_mae_improvement'],indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['development','final'])
    args=parser.parse_args()
    config=json.loads(CONFIG_PATH.read_text())
    folder=ROOT/'reports/experiments'/config['experiment_id']
    folder.mkdir(parents=True,exist_ok=True)
    if args.stage=='development':develop(config,folder)
    else:final_evaluation(config,folder)


if __name__=='__main__':main()

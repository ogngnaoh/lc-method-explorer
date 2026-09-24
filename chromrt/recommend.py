"""Point-prediction ranking and measured complete-panel evaluation."""
import numpy as np
import pandas as pd


def window_distance(values, low, high):
    if not np.isfinite([low, high]).all() or not 0 <= low < high:
        raise ValueError('Window must have finite 0 <= lower < upper')
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('Nonfinite retention time')
    return np.maximum(np.maximum(low-values, values-high), 0.)


def rank_methods(candidates, low, high):
    ranked = candidates.copy()
    ranked['predicted_window_distance'] = window_distance(ranked.prediction_min,low,high)
    ranked['predicted_center_distance'] = abs(ranked.prediction_min-(low+high)/2)
    return ranked.sort_values(['predicted_window_distance','predicted_center_distance','run_time_min','method_id'])


def complete_panels(data, expected_methods=30):
    if data.duplicated(['compound_id','method_id']).any():
        raise ValueError('Duplicate compound/method records')
    counts = data.groupby('compound_id').method_id.nunique()
    return data.loc[data.compound_id.isin(counts[counts == expected_methods].index)].copy()


def fixed_method_orders(train, windows, expected_methods=30):
    data = complete_panels(train,expected_methods)
    if data.empty:
        raise ValueError('No complete training panels for fixed-method comparator')
    result = {}
    for low,high in windows:
        d = data.assign(distance=window_distance(data.rt_min,low,high))
        d['hit'] = d.distance == 0
        scores = d.groupby('method_id').agg(hit_rate=('hit','mean'),distance=('distance','mean'),
                                           run_time_min=('run_time_min','first')).reset_index()
        ordered = scores.sort_values(['hit_rate','distance','run_time_min','method_id'],ascending=[False,True,True,True])
        result[f'{low}-{high}'] = ordered.method_id.tolist()
    return result


def evaluate_ranking(predictions, windows, fixed_orders=None, expected_methods=30):
    complete = complete_panels(predictions,expected_methods)
    records = []
    for cid, panel in complete.groupby('compound_id'):
        for low,high in windows:
            label = f'{low}-{high}'
            if fixed_orders is None:
                ranked = rank_methods(panel,low,high)
            else:
                ranked = panel.set_index('method_id').loc[fixed_orders[label]].reset_index()
            distance = window_distance(ranked.rt_min,low,high)
            records.append({'compound_id':cid,'compound_group':panel.compound_group.iloc[0],
                            'window':label,'selected_method':ranked.method_id.iloc[0],
                            'selected_measured_rt_min':float(ranked.rt_min.iloc[0]),
                            'top1_hit':bool(distance[0]==0),'top3_hit':bool((distance[:3]==0).any()),
                            'feasible':bool((distance==0).any()),
                            'excess_distance_min':float(distance[0]-distance.min())})
    cases = pd.DataFrame(records)
    if cases.empty:
        raise ValueError('No complete evaluation panels')
    def summarize(frame):
        feasible = frame.loc[frame.feasible]
        return {'cases':len(frame),'compounds':frame.compound_id.nunique(),
                'top1_hit_rate':float(frame.top1_hit.mean()),'top3_hit_rate':float(frame.top3_hit.mean()),
                'feasible_rate':float(frame.feasible.mean()),
                'top1_hit_given_feasible':float(feasible.top1_hit.mean()) if len(feasible) else None,
                'mean_excess_distance_min':float(frame.excess_distance_min.mean())}
    summary = {'overall':summarize(cases),'by_window':{w:summarize(g) for w,g in cases.groupby('window')},
               'excluded_incomplete_compounds':int(predictions.compound_id.nunique()-complete.compound_id.nunique())}
    return cases,summary

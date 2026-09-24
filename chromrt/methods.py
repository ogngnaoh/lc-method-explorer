"""MCMRT-specific method parsing. Unknown formats fail rather than guess."""
import re
import numpy as np


def dimensions(text):
    match = re.fullmatch(r'\s*([\d.]+)\s*x\s*([\d.]+)\s*mm,\s*([\d.]+)\s*μm\s*', text)
    if not match:
        raise ValueError(f'Unknown column dimensions: {text}')
    a, b, particle = map(float, match.groups())
    length, diameter = max(a, b), min(a, b)
    if not (20 <= length <= 300 and 1 <= diameter <= 10 and 0 < particle <= 10):
        raise ValueError(f'Ambiguous column dimensions: {text}')
    return {'column_length_mm': length, 'column_id_mm': diameter, 'particle_um': particle}


def mobile_phase(text):
    parts = text.split(' with ')
    if len(parts) > 2:
        raise ValueError(text)
    solvents = {
        'Water': (1., 0., 0.), 'Methanol': (0., 1., 0.),
        'Acetonitrile': (0., 0., 1.), 'Water/methanol=90:10, v/v': (.9, .1, 0.),
    }
    if parts[0] not in solvents:
        raise ValueError(f'Unknown solvent: {text}')
    result = dict(zip(['water_fraction', 'meoh_fraction', 'acn_fraction'], solvents[parts[0]]))
    result.update(formic_acid_percent=0., ammonium_formate_mm=0., ammonium_acetate_mm=0.)
    if len(parts) == 2:
        for additive in parts[1].split(' and '):
            match = re.fullmatch(r'([\d.]+)% formic acid', additive)
            if match:
                result['formic_acid_percent'] = float(match[1])
                continue
            match = re.fullmatch(r'([\d.]+) mM ammonium (formate|acetate)', additive)
            if match:
                result['ammonium_' + match[2] + '_mm'] = float(match[1])
                continue
            raise ValueError(f'Unknown additive: {additive}')
    return result


def encode_method(method_id, settings, gradient):
    g = np.asarray(gradient, dtype=float)
    if g.ndim != 2 or g.shape[1] != 3 or not 2 <= len(g) <= 7 or not np.isfinite(g).all():
        raise ValueError('Invalid gradient shape or values')
    if g[0, 0] != 0 or not (np.diff(g[:, 0]) > 0).all() or not (g[:, 1] > 0).all():
        raise ValueError('Invalid gradient time or flow')
    if not ((g[:, 2] >= 0) & (g[:, 2] <= 100)).all():
        raise ValueError('Invalid %B')
    phases = {key: mobile_phase(settings['Mobile phase ' + key]) for key in ['A', 'B']}
    features = {
        'method_id': method_id, 'column_name': settings['Analytical column'],
        **dimensions(settings['Column dimensions']),
        'column_temperature_c': float(settings['Column temperature (°C)']),
        'sample_temperature_c': float(settings['Sample temperature (°C)']),
        'run_time_min': float(g[-1, 0]), 'gradient_knot_count': len(g),
    }
    for phase, values in phases.items():
        features.update({f'phase_{phase}_{key}': value for key, value in values.items()})
    # Preserve complete schedules. Repeat the final knot for six-knot methods;
    # knot count distinguishes real points from padding. No target-derived values.
    for i in range(7):
        time, flow, percent_b = g[min(i, len(g)-1)]
        features.update({f'knot_{i}_time_min': time, f'knot_{i}_flow_ml_min': flow,
                         f'knot_{i}_percent_b': percent_b})
        b = percent_b / 100
        for solvent in ['water_fraction', 'meoh_fraction', 'acn_fraction']:
            features[f'knot_{i}_{solvent}'] = (1-b)*phases['A'][solvent] + b*phases['B'][solvent]
    return features

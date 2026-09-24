"""Verify originals and build explicit, auditable modeling tables."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import openpyxl
import pandas as pd
from rdkit import Chem, rdBase

from chromrt.chemistry import describe, parse_smiles
from chromrt.methods import encode_method

ROOT = Path(__file__).resolve().parents[1]


def clean(value):
    return ' '.join(value.split()) if isinstance(value, str) else value


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / 'data/source/mcmrt_manifest.json').read_text())
    compounds, methods, observations, gradients, quality = {}, [], [], [], []
    for source in manifest['files']:
        path = ROOT / 'data/raw/mcmrt' / source['name']
        if sha256(path) != source['sha256']:
            raise ValueError(f'Checksum mismatch: {path}')
        method_id = 'M' + path.stem.split()[-1]
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        setups = list(book['LC setups'].values)
        marker = next(i for i, r in enumerate(setups) if clean(r[0]) == 'Gradient elution program')
        settings = {clean(r[0]): clean(r[1]) for r in setups[:marker]}
        gradient = [list(r[1:4]) for r in setups[marker+1:] if any(v is not None for v in r[1:4])]
        methods.append({**encode_method(method_id, settings, gradient),
                        'source_file': path.name, 'column_dimensions_raw': settings['Column dimensions'],
                        'mobile_phase_a_raw': settings['Mobile phase A'], 'mobile_phase_b_raw': settings['Mobile phase B']})
        for i, (time, flow, percent_b) in enumerate(gradient):
            gradients.append({'method_id': method_id, 'knot': i, 'time_min': time,
                              'flow_ml_min': flow, 'percent_b': percent_b})
        for row_number, r in enumerate(book['RT'].iter_rows(min_row=2, values_only=True), start=2):
            if not any(v is not None for v in r):
                continue
            if r[0] is None:
                raise ValueError(f'Unidentified row: {path}:{row_number}')
            cid = int(r[0])
            if cid not in compounds:
                d = describe(r[6])
                source_key = Chem.InchiToInchiKey(r[7].strip())
                generated_key = Chem.MolToInchiKey(parse_smiles(r[6]))
                inchi_matches = bool(source_key and generated_key and source_key[:14] == generated_key[:14])
                if not inchi_matches:
                    quality.append({'compound_id': cid, 'issue': 'SMILES/InChI connectivity mismatch'})
                elif source_key != generated_key:
                    quality.append({'compound_id': cid, 'issue': 'SMILES/InChI secondary-layer difference',
                                    'source_key': source_key, 'generated_key': generated_key})
                if clean(r[3]) != d['rdkit_formula']:
                    quality.append({'compound_id': cid, 'issue': 'formula string mismatch',
                                    'source': clean(r[3]), 'rdkit': d['rdkit_formula']})
                compounds[cid] = {'compound_id': cid, 'name': clean(r[1]), 'source_smiles': r[6],
                                  'source_inchi': r[7], 'source_formula': clean(r[3]),
                                  'inchi_connectivity_matches': inchi_matches,
                                  'source_inchikey': source_key, 'generated_inchikey': generated_key, **d}
            else:
                if r[6].strip() != compounds[cid]['source_smiles'].strip() or r[7] != compounds[cid]['source_inchi']:
                    raise ValueError(f'Inconsistent structure for ID {cid}')
            rt = r[9]
            if not isinstance(rt, (int, float)) or not 0 < rt <= gradient[-1][0]:
                raise ValueError(f'Invalid retention time: {path}:{row_number}')
            observations.append({'compound_id': cid, 'method_id': method_id, 'rt_min': rt,
                                 'rsd_source': r[10], 'retention_factor_source': r[8],
                                 'source_file': path.name, 'source_row': row_number})
        book.close()
    output = ROOT / 'data/processed'
    output.mkdir(parents=True, exist_ok=True)
    tables = {'compounds': pd.DataFrame(compounds.values()).sort_values('compound_id'),
              'methods': pd.DataFrame(methods).sort_values('method_id'),
              'observations': pd.DataFrame(observations).sort_values(['compound_id', 'method_id']),
              'gradients': pd.DataFrame(gradients).sort_values(['method_id', 'knot'])}
    if tables['observations'].duplicated(['compound_id','method_id']).any():
        raise ValueError('Duplicate compound/method observations')
    groups = defaultdict(list)
    for c in compounds.values():
        groups[c['compound_group']].append(c['compound_id'])
    files = {}
    for name, table in tables.items():
        path = output / f'{name}.csv'
        table.to_csv(path, index=False, float_format='%.12g')
        files[name] = {'rows': len(table), 'sha256': sha256(path)}
    excluded = {'method_id','source_file','column_dimensions_raw','mobile_phase_a_raw','mobile_phase_b_raw'}
    schema = {'molecular': [c for c in tables['compounds'] if c.startswith('mol_')],
              'method_numeric': [c for c in tables['methods'] if c not in excluded | {'column_name'}],
              'method_categorical': ['column_name']}
    write_json(output / 'feature_schema.json', schema)
    report = {'rdkit_version': rdBase.rdkitVersion, 'files': files,
              'feature_schema_sha256': sha256(output / 'feature_schema.json'),
              'source_file_hashes': {f['name']:f['sha256'] for f in manifest['files']},
              'compound_groups': len(groups), 'group_collisions': [ids for ids in groups.values() if len(ids)>1],
              'fragmented_structures': [c['compound_id'] for c in compounds.values() if c['fragment_count'] > 1],
              'quality_flags': quality, 'feature_counts': {k:len(v) for k,v in schema.items()}}
    write_json(ROOT / 'reports/preparation.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_file_hashes','files']}, indent=2))
    if any(q['issue'] == 'SMILES/InChI connectivity mismatch' for q in quality):
        raise ValueError('Review structure mismatches before making splits')


if __name__ == '__main__':
    main()

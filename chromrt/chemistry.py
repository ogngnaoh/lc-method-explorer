"""Explicit molecular descriptors and conservative leakage groups."""
import hashlib
import math

from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors, rdMolHash
from rdkit.Chem.MolStandardize import rdMolStandardize

DESCRIPTORS = {
    name: getattr(Descriptors, name) for name in (
        'MolWt', 'MolLogP', 'TPSA', 'NumHDonors', 'NumHAcceptors',
        'NumRotatableBonds', 'RingCount', 'NumAromaticRings', 'NumAliphaticRings',
        'FractionCSP3', 'HeavyAtomCount', 'NHOHCount', 'NOCount', 'LabuteASA',
        'BertzCT', 'BalabanJ', 'Chi0v', 'Chi1v', 'Kappa1', 'Kappa2',
    )
}


def parse_smiles(smiles):
    if not isinstance(smiles, str) or not smiles.strip():
        raise ValueError('A nonempty SMILES string is required')
    # Remove boundary whitespace only; internal whitespace can hide trailing text.
    cleaned = smiles.strip()
    if any(c.isspace() for c in cleaned):
        raise ValueError('Unexpected internal whitespace in SMILES')
    mol = Chem.MolFromSmiles(cleaned)
    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError(f'Invalid SMILES: {cleaned}')
    return mol


def group_parent(mol):
    """Group parent/charge/tautomer/stereo/isotope variants; not a pH model."""
    parent = rdMolStandardize.ChargeParent(Chem.Mol(mol))
    for atom in parent.GetAtoms():
        atom.SetIsotope(0)
        atom.SetAtomMapNum(0)
    Chem.RemoveStereochemistry(parent)
    # v2 tautomer hashing avoids bounded tautomer enumeration, which can stop
    # early for large molecules and produce representation-dependent parents.
    return rdMolHash.MolHash(parent, rdMolHash.HashFunction.HetAtomTautomerv2)


def describe(smiles):
    mol = parse_smiles(smiles)
    parent = group_parent(mol)
    features = {'mol_' + name: float(fn(mol)) for name, fn in DESCRIPTORS.items()}
    features['mol_FormalCharge'] = float(Chem.GetFormalCharge(mol))
    if not all(math.isfinite(x) for x in features.values()):
        raise ValueError('Nonfinite molecular descriptor')
    return {
        'canonical_smiles': Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True),
        'group_parent_key': parent,
        'compound_group': hashlib.sha256(parent.encode()).hexdigest()[:24],
        'rdkit_formula': rdMolDescriptors.CalcMolFormula(mol),
        'fragment_count': len(Chem.GetMolFrags(mol)),
        **features,
    }

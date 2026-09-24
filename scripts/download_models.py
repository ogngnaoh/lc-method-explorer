"""Install the checksum-verified original model bundle, without overwriting changes."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def install(payload, manifest):
    if digest(payload) != manifest['archive_sha256']:
        raise ValueError('Model archive checksum mismatch')
    destination = ROOT / 'models' / manifest['experiment_id']
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if len(archive.namelist()) != len(manifest['files']) or set(archive.namelist()) != set(manifest['files']):
            raise ValueError('Unexpected model archive members')
        verified = {}
        for name, expected in manifest['files'].items():
            if Path(name).name != name:
                raise ValueError('Invalid archive filename')
            data = archive.read(name)
            if digest(data) != expected:
                raise ValueError(f'Model checksum mismatch: {name}')
            target = destination / name
            if target.exists() and digest(target.read_bytes()) != expected:
                raise ValueError(f'Refusing to overwrite different local artifact: {name}')
            verified[name] = data
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in verified.items():
        target = destination / name
        if not target.exists():
            with target.open('xb') as output:
                output.write(data)
    print(f'Installed/verified {len(verified)} original model artifacts in {destination}')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Use an already downloaded archive (checksums still required)')
    args = parser.parse_args()
    manifest = json.loads((ROOT/'data/source/model_release.json').read_text())
    if args.archive:
        payload = args.archive.read_bytes()
    else:
        print('Downloading original models from the project GitHub release...')
        with urllib.request.urlopen(manifest['url'], timeout=120) as response:
            payload = response.read()
    install(payload, manifest)

if __name__ == '__main__':
    main()

"""Download published MCMRT files and verify publisher MD5 + local SHA256.

Uses the saved publisher record, so later website changes cannot silently change
the selected files. Run from any directory with Python 3 and curl available.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def download(item):
    name = item['name']
    if Path(name).name != name:
        raise ValueError(f'Unexpected filename: {name}')
    path = ROOT / 'data/raw/mcmrt' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix('.download')
        subprocess.run(['curl', '-fLsS', '--retry', '2', '--max-time', '60',
                        item['contentUrl'], '-o', str(temporary)], check=True)
        if hashlib.md5(temporary.read_bytes()).hexdigest() != item['md5']:
            raise ValueError(f'Publisher checksum mismatch: {name}')
        temporary.replace(path)
    content = path.read_bytes()
    if hashlib.md5(content).hexdigest() != item['md5']:
        raise ValueError(f'Publisher checksum mismatch: {name}')
    return {'name': name, 'url': item['contentUrl'], 'bytes': len(content),
            'md5': item['md5'], 'sha256': hashlib.sha256(content).hexdigest()}


def main():
    record = json.loads((ROOT / 'data/source/mcmrt_record.json').read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:
        files = list(pool.map(download, sorted(record['distribution'], key=lambda x: x['name'])))
    manifest = {'doi': '10.57760/sciencedb.15823', 'version': 'V3',
                'license': record['license'],
                'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'files': files}
    (ROOT / 'data/source/mcmrt_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Verified {len(files)} files, {sum(f["bytes"] for f in files):,} bytes')


if __name__ == '__main__':
    main()

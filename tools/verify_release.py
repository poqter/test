"""Verify the complete, versioned maintenance bundle without importing the app."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

ROOT=Path(__file__).resolve().parents[1]
MANIFEST='release_manifest.json'
PROTECTED_NAMES={'.git','.venv','venv','__pycache__','.pytest_cache','artifacts'}


def safe_path(root: Path, relative: str) -> Path:
    part=PurePosixPath(relative)
    if part.is_absolute() or not part.parts or '..' in part.parts or '\\' in relative or ':' in relative:
        raise ValueError('Unsafe relative file path: '+relative)
    root=root.resolve()
    path=root.joinpath(*part.parts)
    if not path.resolve().is_relative_to(root):
        raise ValueError('File path leaves release directory: '+relative)
    return path


def file_hash(path: Path) -> str:
    with path.open('rb') as source:
        return hashlib.file_digest(source,'sha256').hexdigest()


def verify(root: Path=ROOT, *, strict=False) -> dict:
    root=root.resolve()
    manifest=json.loads((root/MANIFEST).read_text(encoding='utf-8'))
    expected=manifest['files']; missing=[]; changed=[]
    for relative,info in expected.items():
        path=safe_path(root,relative)
        if not path.is_file():missing.append(relative)
        elif file_hash(path)!=info['sha256']:changed.append(relative)
    extra=[]
    if strict:
        for path in root.rglob('*'):
            if not path.is_file():continue
            rel=path.relative_to(root).as_posix()
            if rel in expected or rel==MANIFEST:continue
            if any(part in PROTECTED_NAMES for part in path.relative_to(root).parts):continue
            if rel=='.streamlit/secrets.toml':continue
            extra.append(rel)
    return {'build_id':manifest['build_id'],'expected':len(expected),'missing':missing,
            'changed':changed,'unexpected':extra,
            'status':'FAIL' if missing or changed or extra else 'PASS'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--strict',action='store_true')
    args=parser.parse_args()
    try:report=verify(args.root,strict=args.strict)
    except (OSError,ValueError,KeyError) as exc:
        print('Release verification failed:',exc,file=sys.stderr);return 1
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())

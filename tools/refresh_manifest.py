"""After reviewing a deliberate source change, refresh file hashes explicitly.

This never updates reference amounts or calculator fixtures. Default is a plan;
--write is required. Do not run this merely to suppress an integrity failure.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from verify_release import ROOT,MANIFEST,file_hash

EXCLUDED_DIRS={'.git','.venv','venv','__pycache__','.pytest_cache','artifacts','.devcontainer'}
EXCLUDED_EXT={'.ttf','.otf','.woff','.woff2','.pyc','.pyo','.log'}


def release_files(root):
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink():continue
        rel=path.relative_to(root).as_posix()
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):continue
        if path.suffix.lower() in EXCLUDED_EXT:continue
        if rel in {MANIFEST,'.streamlit/secrets.toml','.env'} or rel.endswith('_results.json'):continue
        # Academy start guide and launcher are intentional maintenance files.
        if rel in {'ACADEMY_시작하기.md','start_academy_local.bat'}:
            yield rel,path
            continue
        # Restrict top-level files to deliberate operational/package formats.
        if path.suffix.lower() not in {'.py','.json','.toml','.txt','.yml','.yaml','.png','.jpg','.jpeg','.svg','.js','.css','.html'} and path.name not in {'.gitignore','.python-version'}:continue
        yield rel,path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args();root=args.root.resolve()
    manifest=json.loads((root/MANIFEST).read_text(encoding='utf-8'))
    files={rel:{'sha256':file_hash(path),'bytes':path.stat().st_size} for rel,path in release_files(root)}
    before=manifest['files']
    plan={'added':sorted(files.keys()-before.keys()),'removed':sorted(before.keys()-files.keys()),
          'changed':sorted(rel for rel in files.keys()&before.keys() if files[rel]['sha256']!=before[rel]['sha256']),
          'write':args.write}
    if args.write:
        manifest['files']=files
        manifest['validation_state']='NOT_RUN_AFTER_MANIFEST_UPDATE'
        manifest.pop('validated_at_utc',None)
        manifest['manifest_updated_at_utc']=datetime.now(timezone.utc).isoformat()
        (root/MANIFEST).write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(plan,ensure_ascii=False,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())

"""Dry-run by default. Apply the full bundle with backup, preserving local Git/secrets.

Run this script from a SEPARATE extracted release folder, not the target repo:
  python tools/apply_release.py --target "D:/.../insurance_tools_Test"
  python tools/apply_release.py --target "D:/.../insurance_tools_Test" --apply
Rollback also requires an explicit --apply. No Git command or deployment occurs.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from verify_release import ROOT,MANIFEST,safe_path,file_hash,verify
PROTECTED={'.git','.venv','venv','__pycache__','.pytest_cache'}


def check_name(relative):
    parts=Path(relative).parts
    if any(p in PROTECTED for p in parts) or relative in {'.streamlit/secrets.toml','.env'}:
        raise ValueError('Protected local file: '+relative)


def atomic_copy(source: Path,target: Path):
    target.parent.mkdir(parents=True,exist_ok=True)
    handle,tmp=tempfile.mkstemp(prefix='.hw-replace-',dir=target.parent)
    os.close(handle)
    try:
        shutil.copy2(source,tmp)
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def plan(source: Path,target: Path):
    source=source.resolve();target=target.resolve()
    if source==target or source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError('Extract the new ZIP outside the existing repository first.')
    if not (target/'app.py').is_file() or not (target/'calculator_app.py').is_file():
        raise ValueError('Target must be the existing WORKSPACE repository root.')
    report=verify(source,strict=True)
    if report['status']!='PASS':raise ValueError('Source bundle is incomplete or altered: '+str(report))
    manifest=json.loads((source/MANIFEST).read_text(encoding='utf-8'))
    paths=sorted([*manifest['files'],MANIFEST])
    for relative in paths:check_name(relative)
    obsolete=[]
    for relative in manifest.get('remove_from_previous_release',[]):
        check_name(relative)
        if relative in paths:raise ValueError('A file cannot be both kept and removed: '+relative)
        path=safe_path(target,relative)
        if path.exists():
            if not path.is_file():raise ValueError('Removal candidate is not a file: '+relative)
            obsolete.append(relative)
    changed=[]
    for relative in paths:
        src=safe_path(source,relative);dst=safe_path(target,relative)
        if dst.is_symlink() or (dst.exists() and not dst.is_file()):
            raise ValueError('Target path is not a regular file: '+relative)
        if not dst.is_file() or file_hash(dst)!=file_hash(src):changed.append(relative)
    return manifest,changed,obsolete


def restore(backup: Path, *, apply=False):
    record=json.loads((backup/'backup_manifest.json').read_text(encoding='utf-8'))
    target=Path(record['target']).resolve()
    report={'target':str(target),'restore':list(record['previous']), 'remove_added':record['added'],'apply':apply}
    for relative,hash_ in record['previous'].items():
        check_name(relative)
        path=safe_path(backup/'files',relative)
        if not path.is_file() or file_hash(path)!=hash_:raise ValueError('Backup is incomplete: '+relative)
    if apply:
        # Refuse to overwrite work performed after this release was applied.
        for relative,hash_ in record.get('installed',{}).items():
            path=safe_path(target,relative)
            if path.exists() and (not path.is_file() or file_hash(path)!=hash_):
                raise ValueError('Target was edited after installation; preserve it first: '+relative)
        for relative in record['removed']:
            if safe_path(target,relative).exists():raise ValueError('Removed file was recreated; preserve it first: '+relative)
        for relative in record['previous']:
            atomic_copy(safe_path(backup/'files',relative),safe_path(target,relative))
        for relative in record['added']:
            check_name(relative)
            safe_path(target,relative).unlink(missing_ok=True)
    return report


def install(source: Path,target: Path, *, apply=False):
    manifest,changed,obsolete=plan(source,target)
    target=target.resolve()
    report={'build_id':manifest['build_id'],'target':str(target),'replace_or_add':changed,
            'remove_obsolete':obsolete,'preserved':'.git, real Secrets, virtual environment, unrelated files','apply':apply}
    if not apply:return report
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    backup=target.parent/(target.name+'_backup_'+stamp)
    backup.mkdir(parents=True,exist_ok=False)
    previous={};added=[]
    for relative in [*changed,*obsolete]:
        path=safe_path(target,relative)
        if path.is_file():
            destination=safe_path(backup/'files',relative)
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,destination);previous[relative]=file_hash(path)
        elif relative in changed:added.append(relative)
    record={'target':str(target),'build_id':manifest['build_id'],'previous':previous,'added':added,
            'removed':obsolete,'installed':{rel:file_hash(safe_path(source,rel)) for rel in changed}}
    (backup/'backup_manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        for relative in changed:atomic_copy(safe_path(source,relative),safe_path(target,relative))
        for relative in obsolete:safe_path(target,relative).unlink()
        integrity=verify(target)
        if integrity['status']!='PASS':raise RuntimeError('Post-copy verification failed: '+str(integrity))
    except Exception:
        # Best-effort transactional recovery without the post-install edit guard.
        for relative in previous:atomic_copy(safe_path(backup/'files',relative),safe_path(target,relative))
        for relative in added:safe_path(target,relative).unlink(missing_ok=True)
        raise
    report['backup']=str(backup);report['verification']=integrity
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',type=Path)
    parser.add_argument('--source',type=Path,default=ROOT)
    parser.add_argument('--rollback',type=Path,help='Backup folder to restore')
    parser.add_argument('--apply',action='store_true',help='Actually write; without this, only display the plan')
    args=parser.parse_args()
    if not args.target and not args.rollback:parser.error('--target or --rollback is required')
    try:
        report=restore(args.rollback,apply=args.apply) if args.rollback else install(args.source,args.target,apply=args.apply)
    except (ValueError,OSError,RuntimeError,KeyError) as exc:
        print('Operation stopped:',exc,file=sys.stderr);return 1
    print(json.dumps(report,ensure_ascii=False,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())

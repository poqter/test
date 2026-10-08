"""Remove only known obsolete package files and generated project caches.

Run without arguments to preview; use --apply to remove the listed files.
Changed documents, unknown files, credentials and virtual environments are kept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


PROTECTED_DIRS = {'.git', '.venv', 'venv', 'env', 'node_modules', '.openai'}
CACHE_DIRS = {'__pycache__', '.pytest_cache'}


def clean(root: Path, *, apply: bool = False) -> dict:
    root = root.resolve()
    registry = json.loads((root / 'CLEANUP_REMOVED_FILES.json').read_text(encoding='utf-8'))
    result = {'mode': 'apply' if apply else 'preview', 'obsolete_files': [], 'cache_directories': [], 'preserved': []}
    for record in registry.get('explicit_cleanup', []):
        rel = Path(record['path'])
        if rel.is_absolute() or '..' in rel.parts or any(part in PROTECTED_DIRS for part in rel.parts):
            raise ValueError('정리 대상 경로가 프로젝트 범위를 벗어났습니다.')
        target = root / rel
        if target.is_symlink() or not target.resolve().is_relative_to(root):
            result['preserved'].append(rel.as_posix())
            continue
        if not target.is_file():
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != record['sha256']:
            result['preserved'].append(rel.as_posix())
            continue
        result['obsolete_files'].append(rel.as_posix())
        if apply:
            target.unlink()
    for record in registry.get('cleanup_by_hash', []):
        rel = Path(record['directory'])
        if rel.is_absolute() or '..' in rel.parts or any(part in PROTECTED_DIRS for part in rel.parts):
            raise ValueError('정리 대상 경로가 프로젝트 범위를 벗어났습니다.')
        directory = root / rel
        if directory.is_symlink() or not directory.resolve().is_relative_to(root):
            continue
        for target in directory.glob(record['pattern']):
            if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root):
                continue
            if hashlib.sha256(target.read_bytes()).hexdigest() not in record['sha256']:
                continue
            result['obsolete_files'].append(target.relative_to(root).as_posix())
            if apply:
                target.unlink()
    for current, directories, _ in os.walk(root, topdown=True, followlinks=False):
        parent = Path(current)
        kept = []
        for name in directories:
            target = parent / name
            if name in PROTECTED_DIRS or target.is_symlink():
                continue
            if name in CACHE_DIRS:
                result['cache_directories'].append(target.relative_to(root).as_posix())
                if apply:
                    shutil.rmtree(target)
            else:
                kept.append(name)
        directories[:] = kept
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description='예전 패키지의 불필요 파일과 생성 캐시를 정리합니다.')
    parser.add_argument('--apply', action='store_true', help='미리보기 대신 실제로 삭제합니다.')
    args = parser.parse_args()
    result = clean(Path(__file__).resolve().parent, apply=args.apply)
    print('실제 정리 결과' if args.apply else '미리보기 · 파일은 변경되지 않았습니다.')
    for name in result['obsolete_files']:
        print('파일:', name)
    for name in result['cache_directories']:
        print('캐시:', name)
    print(f"대상 파일 {len(result['obsolete_files'])}개 / 캐시 폴더 {len(result['cache_directories'])}개")
    if result['preserved']:
        print('내용 변경 또는 외부 연결 때문에 유지한 파일:', ', '.join(result['preserved']))


if __name__ == '__main__':
    main()

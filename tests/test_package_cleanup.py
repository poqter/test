"""Check deletion boundaries for the full-package cleanup tool."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_cleanup', ROOT / 'cleanup_obsolete_files.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


def registry(root, records):
    (root / 'CLEANUP_REMOVED_FILES.json').write_text(json.dumps({'explicit_cleanup': records}))


def entry(name, content=b'old'):
    return {'path': name, 'sha256': hashlib.sha256(content).hexdigest()}


def test_preview_preserves_every_file(tmp_path):
    old = tmp_path / 'old.txt'; old.write_bytes(b'old')
    cache = tmp_path / '__pycache__'; cache.mkdir(); (cache / 'old.pyc').write_bytes(b'cache')
    registry(tmp_path, [entry('old.txt')])
    result = cleanup.clean(tmp_path)
    assert result['obsolete_files'] == ['old.txt']
    assert result['cache_directories'] == ['__pycache__']
    assert old.exists() and cache.exists()


def test_apply_removes_only_known_files_and_project_caches(tmp_path):
    (tmp_path / 'old.txt').write_bytes(b'old')
    (tmp_path / 'app.py').write_text('application')
    (tmp_path / 'notes.txt').write_text('personal notes')
    settings = tmp_path / '.streamlit'; settings.mkdir(); (settings / 'secrets.toml').write_text('private')
    env = tmp_path / '.venv' / '__pycache__'; env.mkdir(parents=True); (env / 'keep.pyc').write_bytes(b'environment')
    cache = tmp_path / 'modules' / '__pycache__'; cache.mkdir(parents=True); (cache / 'old.pyc').write_bytes(b'cache')
    registry(tmp_path, [entry('old.txt')])
    cleanup.clean(tmp_path, apply=True)
    assert not (tmp_path / 'old.txt').exists() and not cache.exists()
    assert all(p.exists() for p in [tmp_path / 'app.py', tmp_path / 'notes.txt', settings / 'secrets.toml', env / 'keep.pyc'])


def test_modified_old_document_is_preserved(tmp_path):
    old = tmp_path / 'old.txt'; old.write_bytes(b'new user content')
    registry(tmp_path, [entry('old.txt')])
    result = cleanup.clean(tmp_path, apply=True)
    assert old.read_bytes() == b'new user content'
    assert result['preserved'] == ['old.txt']


def test_parent_directory_target_is_rejected(tmp_path):
    registry(tmp_path, [entry('../outside.txt')])
    with pytest.raises(ValueError, match='프로젝트 범위'):
        cleanup.clean(tmp_path, apply=True)


def test_symlink_target_is_preserved(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + '-outside.txt'); outside.write_bytes(b'old')
    link = tmp_path / 'old.txt'; link.symlink_to(outside)
    registry(tmp_path, [entry('old.txt')])
    result = cleanup.clean(tmp_path, apply=True)
    assert link.is_symlink() and outside.read_bytes() == b'old'
    assert result['preserved'] == ['old.txt']


def test_retired_module_is_removed_by_content_without_filename_dependency(tmp_path):
    folder = tmp_path / 'modules' / 'calculators'; folder.mkdir(parents=True)
    old = folder / 'retired.py'; old.write_bytes(b'old')
    active = folder / 'hwarang_calculator_center.py'; active.write_bytes(b'active')
    user = folder / 'custom.py'; user.write_bytes(b'user')
    (tmp_path / 'CLEANUP_REMOVED_FILES.json').write_text(json.dumps({
        'explicit_cleanup': [], 'cleanup_by_hash': [{'directory':'modules/calculators','pattern':'*.py','sha256':[entry('unused')['sha256']]}],
    }))
    cleanup.clean(tmp_path, apply=True)
    assert not old.exists() and active.read_bytes() == b'active' and user.read_bytes() == b'user'

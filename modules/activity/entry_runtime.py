"""Cache only compiled source, never application globals or authenticated state."""
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=2)
def _compiled(path, modified, size):
    return compile(Path(path).read_bytes(), path, 'exec')

def entry_code(path):
    path = Path(path).resolve()
    stat = path.stat()
    return _compiled(str(path), stat.st_mtime_ns, stat.st_size)

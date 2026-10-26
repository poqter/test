"""Daily retention job. Log aggregate counts only; never tokens or credentials."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from modules.briefing.repository import BriefingRepository

if __name__ == '__main__':
    result = BriefingRepository().cleanup_expired_shares()
    print(json.dumps(result, sort_keys=True))
    if result['failed']:
        raise SystemExit('Share retention incomplete; retained rows will be retried.')

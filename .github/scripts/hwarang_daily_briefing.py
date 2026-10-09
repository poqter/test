"""GitHub Actions entrypoint. Never prints credentials or raw database content."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import argparse
import json
from modules.briefing.scheduler import run_scheduled

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--action',choices=['prepare','market','daily','publish','recover'],required=True)
    args=parser.parse_args()
    try: print(json.dumps(run_scheduled(args.action),ensure_ascii=False))
    except Exception:
        print('Daily briefing could not complete. Check administrator diagnostics; automatic retries are limited.',file=sys.stderr)
        sys.exit(1)

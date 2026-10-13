import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from researchflow.release import validate

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('artifacts/verification'))
    parser.add_argument('--existing-results',action='store_true',help='Assemble current CI JUnit results; does not rerun checks')
    args=parser.parse_args()
    result=validate(args.output,args.existing_results)
    print(json.dumps(result,indent=2))
    raise SystemExit(1 if result['status']=='failed' else 0)

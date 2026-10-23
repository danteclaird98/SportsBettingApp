"""Compatible descriptive evaluation CLI; no model fitting or promotion."""
import argparse,hashlib,json
from pathlib import Path
from evaluation import evaluate

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('history');p.add_argument('--train-end',required=True)
    p.add_argument('--validation-end',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();raw=Path(a.history).read_bytes()
    rows=[json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    result=evaluate(rows,a.train_end,a.validation_end)
    result['dataset_sha256']=hashlib.sha256(raw).hexdigest()
    result['code_sha256']={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ['core.py','engine.py','evaluation.py','evaluate.py','storage.py']}
    with open(a.output,'x') as f: json.dump(result,f,indent=2,allow_nan=False)
if __name__=='__main__': main()

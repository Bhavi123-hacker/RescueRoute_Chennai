"""SageMaker training entrypoint. Uploads exported RF artifacts to the model channel."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    # SageMaker mounts /opt/ml. Local runs use the repo root.
    root = Path(os.environ.get('SM_MODULE_DIR', Path(__file__).resolve().parents[1]))
    if (root / 'code').exists():
        root = root  # unused; keep path flexible
    project = Path(__file__).resolve().parents[1]
    model_dir = Path(os.environ.get('SM_MODEL_DIR', project / 'backend' / 'models'))
    output_dir = Path(os.environ.get('SM_OUTPUT_DATA_DIR', project / 'ml' / 'sagemaker-output'))
    model_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project)
    subprocess.check_call([sys.executable, str(project / 'ml' / 'train.py')], cwd=str(project), env=env)
    for name in ('traffic_forest.json', 'model_report.json', 'inference_checks.json', 'dataset_preview.json'):
        src = project / 'backend' / 'models' / name
        if src.exists():
            shutil.copy2(src, model_dir / name)
            shutil.copy2(src, output_dir / name)
    csv = project / 'ml' / 'synthetic_traffic.csv'
    if csv.exists():
        shutil.copy2(csv, output_dir / 'synthetic_traffic.csv')
    report = json.loads((model_dir / 'model_report.json').read_text())
    print(json.dumps({'status': 'TRAINING_COMPLETE', 'observations': report['observations'],
                      'mae': report['random_forest']['mae_minutes']}, indent=2))

if __name__ == '__main__':
    main()

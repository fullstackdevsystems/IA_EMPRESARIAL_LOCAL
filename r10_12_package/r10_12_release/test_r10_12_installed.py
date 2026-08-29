from pathlib import Path
import py_compile,sys
root=Path(sys.argv[1]).resolve(); files=[root/'scripts'/'enterprise_ai'/'fine_tuning_dataset.py',root/'scripts'/'enterprise_ai'/'api.py']
for f in files: py_compile.compile(str(f),doraise=True)
checks={'installed_compile':all(f.exists() for f in files),'installed_dataset_module':'FineTuningDatasetManager' in files[0].read_text(encoding='utf-8'),'installed_api':'/api/enterprise/fine-tuning/runs' in files[1].read_text(encoding='utf-8'),'installed_version':(root/'VERSION.txt').read_text(encoding='utf-8').strip()=='8.5.5-r10.12-controlled-finetune-dataset'}
for k,v in checks.items(): assert v,k; print('PASS',k)
print(f'{len(checks)}/{len(checks)} PASS R10.12 INSTALLED')

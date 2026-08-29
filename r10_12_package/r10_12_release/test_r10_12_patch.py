from pathlib import Path
s=(Path(__file__).parent/'apply_r10_12.py').read_text(encoding='utf-8')
checks={'api_runs':'/api/enterprise/fine-tuning/runs' in s,'api_decision':'examples/{example_id}/decision' in s,'api_export':'runs/{run_id}/export' in s,'admin_dependency':'Depends(admin_dependency)' in s,'version':'r10.12-controlled-finetune-dataset' in s}
for k,v in checks.items(): assert v,k; print('PASS',k)
print(f'{len(checks)}/{len(checks)} PASS R10.12 PATCH')

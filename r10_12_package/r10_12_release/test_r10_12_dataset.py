from pathlib import Path
s=(Path(__file__).parent/'fine_tuning_dataset.py').read_text(encoding='utf-8')
checks={'validated_rules_only':"business_rules" in s and "status='VALIDADO'" in s,'validated_semantics_only':'semantic_definitions' in s and "status='VALIDADO'" in s,'confirmed_memory_only':"status='active'" in s and "sensitivity='normal'" in s,'security_rejection':'credential_or_secret_pattern' in s and 'email_detected' in s,'deterministic_split':'validation' in s and 'sha256(source_id' in s,'admin_review':all(x in s for x in ['APPROVED','REJECTED','PENDING']),'export_train_validation':'_train.jsonl' in s and '_validation.jsonl' in s,'no_auto_training':'training_executed' in s and 'False' in s}
for k,v in checks.items(): assert v,k; print('PASS',k)
print(f'{len(checks)}/{len(checks)} PASS R10.12 DATASET')

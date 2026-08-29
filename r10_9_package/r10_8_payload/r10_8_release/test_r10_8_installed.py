from pathlib import Path
import argparse, subprocess, sys
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();root=Path(a.root)
checks={
 'feedback_module': root/'scripts'/'enterprise_ai'/'feedback.py',
 'factory': root/'scripts'/'enterprise_ai'/'factory.py',
 'api': root/'scripts'/'enterprise_ai'/'api.py',
}
for n,p in checks.items():
    assert p.exists(),f'falta {p}'
    print('PASS installed_'+n)
api=(checks['api']).read_text(encoding='utf-8');fac=checks['factory'].read_text(encoding='utf-8')
assert '/api/enterprise/feedback' in api and 'feedbackButtons' in api
print('PASS installed_feedback_api_ui')
assert 'FeedbackManager' in fac and 'feedback = FeedbackManager' in fac
print('PASS installed_feedback_factory')
print('5/5 PASS R10.8 INSTALLED')

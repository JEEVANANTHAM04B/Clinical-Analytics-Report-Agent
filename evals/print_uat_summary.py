import json

with open('evals/CLINICAL_UAT_REPORT.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

failures = [r for r in data['reports'] if not r['passed']]
print(f"TOTAL FAILURES: {len(failures)}")
for i, f in enumerate(failures, 1):
    print(f"#{i:02d} | ID={f['id']:<11} | Cat={f['category']:<12} | Class={f['failure_category']:<26} | Q: {f['question']}")
    print(f"     Reason : {f['failure_reason']}")
    print(f"     SQL    : {f.get('generated_sql')}")
    print()

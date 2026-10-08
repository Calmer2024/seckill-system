"""Production gate fails closed. Local evidence can never approve production."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

REQUIRED=('same_topology_performance_budget','service_business_consistency','collector_failure_recovery',
          'node_failure_recovery','backend_replica_failure_recovery','external_alert_firing_and_resolved',
          'authentication_and_tenant_isolation','tls_and_secret_rotation','retention_and_restore',
          'cardinality_and_storage_budget','rollback_rehearsal')

def evaluate(data, now=None):
    blockers=[]
    if not isinstance(data,dict): return {'production_ready':False,'blockers':['acceptance must be a JSON object']}
    checks=data.get('checks') if isinstance(data.get('checks'),dict) else {}
    references=data.get('evidence') if isinstance(data.get('evidence'),dict) else {}
    if data.get('environment')!='production': blockers.append('environment is not production')
    try:
        checked=datetime.fromisoformat(data['checked_at'].replace('Z','+00:00'))
        if checked.utcoffset() is None or checked.utcoffset().total_seconds()!=0:
            raise ValueError('UTC required')
        age=((now or datetime.now(timezone.utc))-checked).total_seconds()
        if not 0<=age<=7*86400: blockers.append('evidence is stale or future-dated')
    except (KeyError,TypeError,ValueError): blockers.append('valid UTC checked_at is required')
    for name in REQUIRED:
        if checks.get(name) is not True: blockers.append(name+': not passed')
        evidence=references.get(name)
        if not isinstance(evidence,str) or not evidence.strip(): blockers.append(name+': missing evidence reference')
    return {'production_ready':not blockers,'blockers':blockers}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--acceptance',required=True)
    args=parser.parse_args(); result=evaluate(json.loads(Path(args.acceptance).read_text(encoding='utf-8')))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['production_ready'] else 2)

if __name__=='__main__': main()

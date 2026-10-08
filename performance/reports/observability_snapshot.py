"""Bounded, read-only run evidence. Endpoint failures remain explicit missing data."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
ENDPOINTS={'prometheus':'http://127.0.0.1:9090/-/ready','tempo':'http://127.0.0.1:3200/ready',
           'loki':'http://127.0.0.1:3100/ready','collector':'http://127.0.0.1:13133/',
           'alertmanager':'http://127.0.0.1:9093/-/ready','alert_receiver':'http://127.0.0.1:9122/health'}
CONTAINERS=('seckill_user','seckill_product_1','seckill_product_2','seckill_order_service',
            'seckill_inventory_service','seckill_order_worker','seckill_inventory_worker')
SAFE_SETTINGS={'SECKILL_OBSERVABILITY_ENABLED','SECKILL_TRACING_ENABLED','SECKILL_TRACE_SAMPLE_RATIO','SECKILL_ACCESS_LOG_SAMPLE_RATIO',
               'OBSERVABILITY_ENVIRONMENT','SERVICE_VERSION','LOG_LEVEL'}

def source_fingerprint(root=ROOT):
    digest=hashlib.sha256()
    paths=[]
    for directory in ['packages/seckill-observability/src','performance/monitoring','performance/reports','performance/scenarios',
                      'user_service','product_service/app','order_service/app','inventory_service/app']:
        for folder,subdirectories,files in os.walk(root/directory):
            subdirectories[:]=[name for name in subdirectories if name not in {'runs','__pycache__','.venv','venv','node_modules','build'}]
            paths.extend(Path(folder)/name for name in files if Path(name).suffix in {'.py','.yml','.yaml','.js','.alloy','.json'})
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode()); digest.update(b'\0'); digest.update(path.read_bytes()); digest.update(b'\0')
    return digest.hexdigest()

def deployments():
    result=[]
    for name in CONTAINERS:
        try:
            process=subprocess.run(['docker','inspect',name],cwd=ROOT,capture_output=True,text=True,timeout=3)
            if process.returncode: raise ValueError('container unavailable')
            item=json.loads(process.stdout)[0]
            settings={}
            for value in item['Config'].get('Env',[]):
                key,_,value=value.partition('=')
                if key in SAFE_SETTINGS: settings[key]=value[:128]
            result.append({'container':name,'image_id':item['Image'],'started_at':item['State']['StartedAt'],
                           'running':item['State']['Running'],'telemetry_settings':settings})
        except (OSError,ValueError,KeyError,subprocess.SubprocessError):
            result.append({'container':name,'available':False})
    return result

def probe(item):
    name,url=item
    try:
        with urllib.request.urlopen(url,timeout=2) as response:
            response.read(1024)
            return name,{'available':response.status==200,'http_status':response.status}
    except Exception as exc:
        return name,{'available':False,'error_type':type(exc).__name__}

def capture():
    with ThreadPoolExecutor(max_workers=6) as pool:
        endpoints=dict(pool.map(probe,ENDPOINTS.items()))
    try:
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,timeout=3).strip()
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,timeout=3))
    except (OSError,subprocess.SubprocessError):
        revision='unknown'; dirty=None
    return {'captured_at':datetime.now(timezone.utc).isoformat(),'git_revision':revision,'working_tree_dirty':dirty,
            'telemetry_source_sha256':source_fingerprint(),'backends':endpoints,'scope':'local',
            'deployments':deployments(),
            'sampling_policy':'ParentBased TraceIdRatioBased; deployment settings must be checked separately',
            'production_ready':False}

def correlation_samples(path):
    if not path.exists(): return []
    with path.open('r',encoding='utf-8',errors='replace') as handle:
        text=handle.read(512*1024)
    pairs=re.findall(r'OBSERVABILITY_SAMPLE trace_id=([a-f0-9]{32}) request_id=([A-Za-z0-9_-]{1,128})(?![A-Za-z0-9_-])',text)
    return [{'trace_id':trace,'request_id':request,'recording_status':'unknown; ID does not guarantee sampled storage'} for trace,request in dict.fromkeys(pairs)][:4]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True); parser.add_argument('--phase',choices=['start','end'],required=True)
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args(); path=Path(args.output)
    evidence=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema_version':1,'run_id':args.run_id}
    if evidence.get('run_id')!=args.run_id: raise ValueError('evidence belongs to a different run')
    if args.phase in evidence: raise ValueError('evidence phase already captured; refusing overwrite')
    evidence[args.phase]=capture()
    if args.phase=='end': evidence['correlation_samples']=correlation_samples(path.parent/'k6.log')
    path.parent.mkdir(parents=True,exist_ok=True)
    # Atomic replacement prevents readers observing a partial snapshot.
    temporary=path.with_suffix('.json.tmp'); temporary.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8'); temporary.replace(path)
    print(json.dumps({'phase':args.phase,'output':str(path)}))

if __name__=='__main__': main()

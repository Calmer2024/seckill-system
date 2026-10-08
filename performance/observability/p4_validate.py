"""Repeatable local validation; all mutations are confined to Compose project seckill-p4.

Start the standalone Compose file first. This tool never operates the business project.
Raw k6 evidence is retained even when an overhead gate fails.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import statistics
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/observability/p4-evidence'
COMPOSE = ['docker', 'compose', '-p', 'seckill-p4', '-f', str(ROOT/'performance/config/docker-compose.p4.yml')]
PREFIX=''

def command(args, timeout=120, check=True):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    return result

def remote(service, code):
    if service not in {'product-on', 'product-off'}:
        raise ValueError('invalid isolation service')
    return command(COMPOSE+['exec','-T',service,'python','-c',code], timeout=15).stdout.strip()

def ready(service):
    deadline = time.monotonic()+90
    while time.monotonic()<deadline:
        try:
            if remote(service,"import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/products',timeout=2).status)") == '200':
                return
        except (RuntimeError, subprocess.TimeoutExpired):
            pass
        time.sleep(2)
    raise RuntimeError(service+' readiness timeout')

def resources(service):
    return json.loads(remote(service,"import json,pathlib; p=pathlib.Path('/sys/fs/cgroup'); print(json.dumps({'cpu_usec':int(dict(x.split() for x in (p/'cpu.stat').read_text().splitlines())['usage_usec']),'memory_bytes':int((p/'memory.current').read_text()),'memory_peak_bytes':int((p/'memory.peak').read_text())}))"))

def deployment_evidence():
    evidence=[]
    for target in ['on','off']:
        service='product-'+target
        container=command(COMPOSE+['ps','-q',service]).stdout.strip()
        item=json.loads(command(['docker','inspect',container]).stdout)[0]
        allowed={'SECKILL_OBSERVABILITY_ENABLED','SECKILL_TRACING_ENABLED','SECKILL_TRACE_SAMPLE_RATIO','SECKILL_ACCESS_LOG_SAMPLE_RATIO','OBSERVABILITY_ENVIRONMENT'}
        settings=dict(value.split('=',1) for value in item['Config']['Env'] if value.partition('=')[0] in allowed)
        evidence.append({'service':service,'image_id':item['Image'],'memory_limit_bytes':item['HostConfig']['Memory'],
                         'nano_cpus':item['HostConfig']['NanoCpus'],'telemetry_settings':settings})
    return evidence

def benchmark(name, target, seconds):
    service = 'product-'+target
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    before = resources(service)
    clock = time.monotonic()
    result = command(COMPOSE+['run','--rm','--no-deps','-e','TARGET='+target,'-e','DURATION='+str(seconds)+'s','-e','RESULT='+PREFIX+name,'k6','run','/scripts/p4.js'],timeout=seconds+90,check=False)
    elapsed = time.monotonic()-clock
    after = resources(service)
    data = json.loads((OUT/(PREFIX+name+'.json')).read_text(encoding='utf-8'))
    metrics = data['metrics']
    logs = command(COMPOSE+['logs','--no-color','--since',started,service],timeout=20).stdout
    samples = re.findall(r'P4_TRACE_SAMPLE (\{[^\n]+?\})', result.stdout+result.stderr)
    samples = [json.loads(s.replace('\\"','"')) for s in samples]
    return {'name':name,'target':target,'started_at':started,'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'exit_code':result.returncode,'requests':metrics['http_reqs']['values']['count'],
            'rps':metrics['http_reqs']['values']['rate'], 'p95_ms':metrics['http_req_duration']['values']['p(95)'],
            'p99_ms':metrics['http_req_duration']['values']['p(99)'], 'error_rate':metrics['http_req_failed']['values']['rate'],
            'cpu_cores_mean':(after['cpu_usec']-before['cpu_usec'])/1e6/elapsed,
            'memory_bytes':after['memory_bytes'],'memory_peak_bytes':after['memory_peak_bytes'],
            'docker_log_utf8_bytes':len(logs.encode('utf-8')), 'sdk_queue_overflow_messages':logs.count('Queue full, dropping Span'),
            'trace_samples':samples[:4],'raw_file':PREFIX+name+'.json'}

def gates(runs, fault, contracts=None):
    pairs = []
    for index in range(3):
        off = next((r for r in runs if r['name']==f'pair-{index}-off'),None)
        on = next((r for r in runs if r['name']==f'pair-{index}-on'),None)
        if off and on and off['rps']>0 and off['p95_ms']>0:
            pairs.append({'rps_loss':1-on['rps']/off['rps'],'p95_increase':on['p95_ms']/off['p95_ms']-1})
    measured = len(pairs)==3
    loss = statistics.median(p['rps_loss'] for p in pairs) if measured else None
    latency = statistics.median(p['p95_increase'] for p in pairs) if measured else None
    return {'measurement_complete':measured,
            'zero_http_errors':bool(runs) and all(r['exit_code']==0 and r['error_rate']==0 and r['requests']>=100 for r in runs),
            'median_rps_loss':loss,'median_p95_increase':latency,
            'overhead_within_5_percent':measured and loss<=.05 and latency<=.05,
            'fault_isolation':bool(fault.get('business_available') and fault.get('trace_recovered')),
            'cardinality_and_restart':bool(contracts and contracts.get('bounded_route_cardinality') and contracts.get('restart_clears_old_multiprocess_counters')),
            'database_fault_and_recovery':bool(contracts and contracts.get('database_fault_visible') and contracts.get('database_recovered')),
            'production_ready':False,'production_blockers':['No production cluster validation','No real external alert delivery validation','Local shared-host performance is not a production capacity result']}

def main():
    global PREFIX
    parser=argparse.ArgumentParser()
    parser.add_argument('--seconds',type=int,default=20)
    parser.add_argument('--label',default='initial')
    args=parser.parse_args()
    if not 10<=args.seconds<=120:
        parser.error('seconds must be 10..120')
    if not re.fullmatch('[a-z0-9-]{1,32}',args.label): parser.error('invalid label')
    PREFIX=args.label+'-'
    report_path=OUT/(PREFIX+'validation.json')
    if report_path.exists() or any(OUT.glob(PREFIX+'*.json')): parser.error('label already exists; refusing to overwrite evidence')
    OUT.mkdir(parents=True,exist_ok=True)
    runs=[]
    fault={}
    report={'scope':'local isolated read-only catalog; 4 VUs; cache disabled; same image and limits',
            'duration_seconds':args.seconds,
            'sampling_ratio':.1,'sdk_queue_spans_per_process':2048,'sdk_export_timeout_seconds':1,
            'runs':runs,'fault':fault,'production_ready':False}
    try:
        for service in ['product-off','product-on']:
            ready(service)
            command(COMPOSE+['restart',service]); ready(service)
            runs.append(benchmark('cold-'+service.removeprefix('product-'),service.removeprefix('product-'),args.seconds))
        report['deployments']=deployment_evidence()
        for index in range(3):
            for target in (['off','on'] if index%2==0 else ['on','off']):
                runs.append(benchmark(f'pair-{index}-{target}',target,args.seconds))
        command(COMPOSE+['stop','collector','tempo'])
        try:
            run=benchmark('collector-unavailable','on',args.seconds)
            runs.append(run)
            fault['business_available']=run['exit_code']==0 and run['error_rate']==0
        finally:
            command(COMPOSE+['start','tempo','collector'])
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            try:
                status=remote('product-on',"import urllib.request; print(urllib.request.urlopen('http://tempo:3200/ready',timeout=2).status)")
                if status=='200': break
            except RuntimeError: pass
            time.sleep(2)
        # Explicitly sampled validation parent; do not rely on random 10% sampling.
        trace=uuid.uuid4().hex
        remote('product-on',"import urllib.request; r=urllib.request.Request('http://localhost:8000/api/products',headers={'traceparent':'00-"+trace+"-1234567890abcdef-01'}); print(urllib.request.urlopen(r,timeout=3).status)")
        deadline=time.monotonic()+45
        fault['trace_recovered']=False
        while time.monotonic()<deadline:
            try:
                data=remote('product-on',"import urllib.request; print(urllib.request.urlopen('http://tempo:3200/api/traces/"+trace+"',timeout=3).status)")
                if data=='200': fault['trace_recovered']=True; break
            except RuntimeError: pass
            time.sleep(2)
        fault['recovered_trace_id']=trace
        report['contracts']=contracts()
        report['gates']=gates(runs,fault,report['contracts'])
    finally:
        report['generated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report['gates'],indent=2))

def contracts():
    # Unique URLs must collapse to a single unmatched route across all four workers.
    remote('product-on',"import urllib.request,urllib.error;\nfor i in range(100):\n try: urllib.request.urlopen('http://localhost:8000/p4-unmatched/'+str(i),timeout=3)\n except urllib.error.HTTPError as e: assert e.code==404")
    raw=remote('product-on',"import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode())")
    rows=[line for line in raw.splitlines() if line.startswith('http_requests_total{') and 'status="404"' in line]
    unmatched=len(rows)==1 and 'path="__unmatched__"' in rows[0] and float(rows[0].rsplit(' ',1)[1])==100
    before=sum(float(line.rsplit(' ',1)[1]) for line in raw.splitlines() if line.startswith('http_requests_total{'))
    command(COMPOSE+['restart','product-on']); ready('product-on')
    raw=remote('product-on',"import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode())")
    after=sum(float(line.rsplit(' ',1)[1]) for line in raw.splitlines() if line.startswith('http_requests_total{'))
    command(COMPOSE+['stop','database'])
    try:
        unavailable=remote('product-on',"import urllib.request,urllib.error;\ntry: print(urllib.request.urlopen('http://localhost:8000/api/products',timeout=5).status)\nexcept urllib.error.HTTPError as e: print(e.code)")
    finally:
        command(COMPOSE+['start','database'])
    ready('product-on')
    return {'random_404_paths':100,'unmatched_metric_series':len(rows),'bounded_route_cardinality':unmatched,
            'restart_clears_old_multiprocess_counters':0<after<before,'requests_before_restart':before,'requests_after_restart':after,
            'database_unavailable_http_status':unavailable,'database_fault_visible':unavailable in {'500','503'},'database_recovered':True}

if __name__=='__main__': main()

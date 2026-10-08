from __future__ import annotations
import asyncio
import contextlib
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[2]

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    result=importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result

gate=module('p4_gate','performance/observability/go_live_gate.py')
validator=module('p4_validate','performance/observability/p4_validate.py')
snapshot=module('p4_snapshot','performance/reports/observability_snapshot.py')
reports=module('p4_reports','performance/reports/generate_report.py')

class P4Tests(unittest.TestCase):
    def test_complete_fresh_production_checklist_can_pass(self):
        data={'environment':'production','checked_at':'2026-10-03T00:00:00Z',
              'checks':{key:True for key in gate.REQUIRED},'evidence':{key:'approved-report.json' for key in gate.REQUIRED}}
        self.assertTrue(gate.evaluate(data,datetime(2026,10,3,tzinfo=timezone.utc))['production_ready'])

    def test_snapshot_refuses_duplicate_phase_and_other_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'telemetry.json'
            argv=['snapshot','--output',str(path),'--phase','start','--run-id','unit-validation']
            with patch('sys.argv',argv),patch.object(snapshot,'capture',return_value={'captured_at':'original'}),contextlib.redirect_stdout(io.StringIO()):
                snapshot.main()
                with self.assertRaises(ValueError): snapshot.main()
            argv[-1]='different-run'
            with patch('sys.argv',argv):
                with self.assertRaises(ValueError): snapshot.main()
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['start']['captured_at'],'original')

    def test_generated_report_preserves_unavailable_evidence_and_rejects_wrong_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'k6.json').write_text('{"metrics":{}}')
            (root/'validation.json').write_text('{"passed":false,"checks":[]}')
            evidence={'run_id':'unit-validation','start':{'captured_at':'2026-10-03T00:00:00Z','telemetry_source_sha256':'abc','backends':{'tempo':{'available':False}}}}
            path=root/'telemetry.json'; path.write_text(json.dumps(evidence))
            argv=['report','--k6-summary',str(root/'k6.json'),'--validation',str(root/'validation.json'),
                  '--telemetry',str(path),'--output-dir',str(root/'output'),'--run-id','unit-validation','--scenario','product-read','--mode','baseline']
            with patch('sys.argv',argv),contextlib.redirect_stdout(io.StringIO()): reports.main()
            result=json.loads((root/'output/report.json').read_text(encoding='utf-8'))
            self.assertEqual(result['telemetry_evidence'],evidence)
            self.assertFalse(result['validation']['passed'])
            self.assertIn('tempo',(root/'output/report.html').read_text(encoding='utf-8'))
            evidence['run_id']='different-run'; path.write_text(json.dumps(evidence))
            with patch('sys.argv',argv):
                with self.assertRaises(ValueError): reports.main()
    def test_access_sampling_keeps_metrics_errors_and_sampled_trace_logs(self):
        from seckill_observability.http import RequestContextMiddleware
        from opentelemetry import trace
        from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
        for status,sampled,expected_logs in [(200,False,0),(409,False,1),(503,False,1),(200,True,1)]:
            records=Mock(); logger=Mock()
            async def app(scope,receive,send):
                await send({'type':'http.response.start','status':status,'headers':[]})
            async def send(message): pass
            with patch.dict('os.environ',{'SECKILL_OBSERVABILITY_ENABLED':'true','SECKILL_ACCESS_LOG_SAMPLE_RATIO':'0'}):
                middleware=RequestContextMiddleware(app,records,logger)
            span=NonRecordingSpan(SpanContext(1,2,False,TraceFlags(1 if sampled else 0)))
            with trace.use_span(span):
                asyncio.run(middleware({'type':'http','path':'/x','method':'GET','headers':[]},None,send))
            records.assert_called_once(); self.assertEqual(logger.info.call_count,expected_logs)

    def test_invalid_access_sampling_fails_configuration(self):
        from seckill_observability.http import RequestContextMiddleware
        for ratio in ['nan','inf','-1','1.1','invalid']:
            with patch.dict('os.environ',{'SECKILL_ACCESS_LOG_SAMPLE_RATIO':ratio}):
                with self.assertRaises(ValueError): RequestContextMiddleware(Mock(),Mock())
    def test_samples_are_bounded_validated_and_use_actual_response_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'k6.log'
            path.write_text('\n'.join('OBSERVABILITY_SAMPLE trace_id='+f'{i:032x}'+' request_id=gateway-'+str(i) for i in range(10)))
            samples=snapshot.correlation_samples(path)
            self.assertEqual(len(samples),4); self.assertEqual(samples[0]['request_id'],'gateway-0')
            path.write_text('OBSERVABILITY_SAMPLE trace_id=invalid request_id=x')
            self.assertEqual(snapshot.correlation_samples(path),[])
    def test_production_gate_rejects_local_even_all_checks_pass(self):
        data={'environment':'local','checked_at':'2026-10-03T00:00:00Z',
              'checks':{k:True for k in gate.REQUIRED},'evidence':{k:'local-result.json' for k in gate.REQUIRED}}
        self.assertFalse(gate.evaluate(data,datetime(2026,10,3,tzinfo=timezone.utc))['production_ready'])

    def test_missing_stale_and_false_evidence_fail_closed(self):
        data={'environment':'production','checked_at':'2020-01-01T00:00:00Z','checks':{k:True for k in gate.REQUIRED}}
        result=gate.evaluate(data)
        self.assertFalse(result['production_ready']); self.assertTrue(any('stale' in v for v in result['blockers']))
        self.assertTrue(any('missing evidence' in v for v in result['blockers']))
        self.assertFalse(gate.evaluate({})['production_ready'])

    def test_budget_gate_does_not_hide_regression_or_missing_pairs(self):
        runs=[{'name':f'pair-{i}-{target}','rps':100 if target=='off' else 80,'p95_ms':10 if target=='off' else 12,
               'exit_code':0,'error_rate':0,'requests':1000} for i in range(3) for target in ['off','on']]
        result=validator.gates(runs,{'business_available':True,'trace_recovered':True})
        self.assertTrue(result['zero_http_errors']); self.assertFalse(result['overhead_within_5_percent'])
        self.assertFalse(result['production_ready']); self.assertFalse(validator.gates([], {})['measurement_complete'])

    def test_fingerprint_changes_with_source_but_excludes_secrets_and_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'performance/reports/x.py'; source.parent.mkdir(parents=True); source.write_text('a')
            first=snapshot.source_fingerprint(root)
            (root/'.env').write_text('password=secret'); (source.parent/'results.txt').write_text('noise')
            runs=source.parent/'runs'; runs.mkdir(); (runs/'telemetry.json').write_text('{"generated":"dynamic"}')
            self.assertEqual(first,snapshot.source_fingerprint(root))
            source.write_text('b'); self.assertNotEqual(first,snapshot.source_fingerprint(root))

    def test_disabled_http_telemetry_preserves_request_context(self):
        from seckill_observability.http import RequestContextMiddleware
        from seckill_observability.context import current_context
        records=Mock(); messages=[]
        async def app(scope, receive, send):
            self.assertEqual(current_context()['request_id'],'p4-test')
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'ok'})
        async def send(message): messages.append(message)
        with patch.dict('os.environ',{'SECKILL_OBSERVABILITY_ENABLED':'false'}):
            middleware=RequestContextMiddleware(app,records)
        asyncio.run(middleware({'type':'http','path':'/x','method':'GET','headers':[(b'x-request-id',b'p4-test')]},None,send))
        records.assert_not_called(); self.assertIn((b'x-request-id',b'p4-test'),messages[0]['headers'])
        self.assertEqual(current_context(),{})

if __name__=='__main__': unittest.main()

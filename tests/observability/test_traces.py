import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from performance.web import traces


class TracesTests(unittest.TestCase):
    def test_protocol_queries_support_both_semantic_conventions(self):
        self.assertEqual(traces.query_clauses('method:GET', 'root'),
                         ['(span.http.request.method = "GET" || span.http.method = "GET")'])
        self.assertEqual(traces.query_clauses('-method:GET', 'root'),
                         ['((span.http.request.method != "GET" && span.http.request.method != nil) || (span.http.method != "GET" && span.http.method != nil))'])
        self.assertEqual(traces.query_clauses('db_system:mysql', 'all'),
                         ['(span.db.system = "mysql" || span.db.system.name = "mysql")'])
    def test_summary_distinguishes_http_success_rejection_error_and_unknown(self):
        root = {'span_id': '1', 'parent_span_id': '', 'name': 'POST /orders', 'status': 'ok',
                'attributes': {'http.method': 'POST', 'http.route': '/orders', 'http.status_code': '201'}}
        child = {'span_id': '2', 'parent_span_id': '1', 'name': 'order.submit', 'status': 'ok',
                 'attributes': {'seckill.outcome': 'success'}}
        summary = traces.summarize_trace([root, child])
        self.assertEqual(summary['status'], 'ok')
        self.assertEqual(summary['input'], 'POST /orders')
        self.assertIn('HTTP 201', summary['output'])
        root['attributes']['http.status_code'] = '404'
        child['attributes'] = {'seckill.outcome': 'rejected', 'seckill.error_code': 'PRODUCT_NOT_FOUND'}
        summary = traces.summarize_trace([root, child])
        self.assertEqual(summary['status'], 'rejected')
        self.assertIn('PRODUCT_NOT_FOUND', summary['output'])
        child['status'] = 'error'
        self.assertEqual(traces.summarize_trace([root, child])['status'], 'error')
        root['attributes'] = {'db.operation': 'SELECT'}
        self.assertEqual(traces.summarize_trace([root])['status'], 'unknown')
        self.assertEqual(traces.summarize_trace([root])['input'], 'SELECT')

    def test_summary_cache_is_bounded_and_does_not_cache_failure(self):
        traces._summary_cache.clear()
        summary = {'status': 'ok', 'input': 'GET /products', 'output': 'HTTP 200', 'error': ''}
        with patch.object(traces, 'trace_detail', return_value={'summary': summary}) as read:
            for i in range(101):
                traces.trace_summary(f'{i:032x}')
            self.assertEqual(len(traces._summary_cache), 100)
            traces.trace_summary(f'{100:032x}')
            self.assertEqual(read.call_count, 101)
        traces._summary_cache.clear()
        with patch.object(traces, 'trace_detail', return_value=None) as read:
            traces.trace_summary('a' * 32)
            traces.trace_summary('a' * 32)
            self.assertEqual(read.call_count, 2)

    def test_saturated_queue_drops_telemetry_without_blocking(self):
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
        from seckill_observability.tracing import SafeExporter
        class SlowExporter(SpanExporter):
            calls = 0
            def export(self, spans):
                self.calls += len(spans)
                time.sleep(.1)
                return SpanExportResult.FAILURE
            def shutdown(self):
                pass
        exporter = SlowExporter()
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(SafeExporter(exporter), max_queue_size=2,
            max_export_batch_size=1, schedule_delay_millis=10000))
        tracer = provider.get_tracer('queue-test')
        started = time.monotonic()
        for _ in range(100):
            with tracer.start_as_current_span('work'):
                pass
        self.assertLess(time.monotonic() - started, .2)
        provider.shutdown()
        self.assertLess(exporter.calls, 100)

    def test_real_http_sql_redis_trace_and_exporter_outage(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, str(root / 'tests/observability/tracing_harness.py')], cwd=root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"http_parent_link": true', result.stdout)

    def test_query_is_bounded_and_injection_rejected(self):
        for params in ({'service': ['" } | count()']}, {'window': ['10000']}, {'min_duration_ms': ['nan']}, {'url': ['http://attacker']}, {'errors': ['yes']}):
            with self.assertRaises(ValueError):
                traces.search_traces(params)
        with patch.object(traces, 'read_tempo', return_value={'traces': []}) as read:
            result = traces.search_traces({'service': ['order-api'], 'errors': ['true']})
            self.assertEqual(result['limit'], 50)
            self.assertIn('limit=50', read.call_args.args[0])
            self.assertIn('deployment.environment.name', read.call_args.args[0])

    def test_detail_allowlists_and_ignores_foreign_environment(self):
        resource = lambda env: {'attributes': [{'key': k, 'value': {'stringValue': v}} for k, v in {
            'service.namespace': 'seckill', 'service.name': 'order-api', 'deployment.environment.name': env}.items()]}
        span = {'spanId': 'aa' * 8, 'name': 'order.submit', 'startTimeUnixNano': '1000', 'endTimeUnixNano': '2000',
                'attributes': [{'key': 'db.statement', 'value': {'stringValue': 'secret'}}]}
        data = {'batches': [{'resource': resource(env), 'scopeSpans': [{'spans': [span]}]} for env in ('local', 'production')]}
        with patch.object(traces, 'read_tempo', return_value=data):
            detail = traces.trace_detail('ab' * 16)
        self.assertEqual(len(detail['spans']), 1)
        self.assertNotIn('secret', json.dumps(detail))
        with self.assertRaises(ValueError):
            traces.trace_detail('../../admin')

    def test_search_status_does_not_invent_success(self):
        item = {'traceID': 'ab' * 16, 'startTimeUnixNano': '1000', 'durationMs': 8}
        with patch.object(traces, 'read_tempo', return_value={'traces': [item]}):
            self.assertEqual(traces.search_traces({})['traces'][0]['status'], 'unknown')
            self.assertEqual(traces.search_traces({'errors': ['true']})['traces'][0]['status'], 'error')

    def test_detail_exposes_safe_dependency_context_only(self):
        data = {'resourceSpans': [{'resource': {'attributes': [
            {'key': k, 'value': {'stringValue': v}} for k, v in {
                'service.namespace': 'seckill', 'deployment.environment.name': 'local'}.items()]},
            'scopeSpans': [{'spans': [{'spanId': 'aa' * 8, 'attributes': [
                {'key': k, 'value': {'stringValue': v}} for k, v in {
                    'server.address': 'redis', 'db.namespace': 'inventory',
                    'db.statement': 'private query', 'http.request.body': 'private body'}.items()]}]}]}]}
        with patch.object(traces, 'read_tempo', return_value=data):
            attrs = traces.trace_detail('ab' * 16)['spans'][0]['attributes']
        self.assertEqual(attrs, {'server.address': 'redis', 'db.namespace': 'inventory'})

    def test_backend_unavailable_is_not_empty_or_connected(self):
        with patch.object(traces, 'read_tempo', side_effect=traces.TraceUnavailable()):
            self.assertEqual(traces.trace_status(), 'unavailable')
            with self.assertRaises(traces.TraceUnavailable):
                traces.search_traces({})

    def test_all_screenshot_time_ranges_and_relative_time(self):
        now = 1791446400
        for window, seconds in [('1h', 3600), ('3h', 10800), ('6h', 21600), ('12h', 43200),
                                ('1d', 86400), ('2d', 172800), ('7d', 604800), ('14d', 1209600),
                                ('30d', 2592000), ('15h', 54000), ('90m', 5400)]:
            with self.subTest(window=window), patch.object(traces.time, 'time', return_value=now), patch.object(traces, 'read_tempo', return_value={'traces': []}) as read:
                result = traces.search_traces({'window': [window]})
                query = parse_qs(urlparse(read.call_args.args[0]).query)
                self.assertEqual(int(query['start'][0]), now - seconds)
                self.assertEqual(int(parse_qs(urlparse(read.call_args_list[0].args[0]).query)['end'][0]), now)
                self.assertEqual(result['window'], window)
        with patch.object(traces.time, 'time', return_value=now), patch.object(traces, 'tempo_retention_seconds', return_value=86400), patch.object(traces, 'read_tempo', return_value={'traces': []}) as read:
            result = traces.search_traces({'window': ['all']})
            self.assertEqual(int(parse_qs(urlparse(read.call_args.args[0]).query)['start'][0]), now - 86400)
            self.assertEqual(result['retention_seconds'], 86400)

    def test_explicit_dates_are_not_shortened_and_invalid_dates_rejected(self):
        with patch.object(traces.time, 'time', return_value=200000), patch.object(traces, 'read_tempo', return_value={}) as read:
            result = traces.search_traces({'window': ['custom'], 'start': ['1000'], 'end': ['100000']})
            query = parse_qs(urlparse(read.call_args.args[0]).query)
            self.assertEqual(query['start'], ['1000'])
            self.assertEqual(query['end'], ['100000'])
            self.assertEqual(result['start'], 1000)
        for params in [{'window': ['31d']}, {'window': ['0h']}, {'window': ['custom'], 'start': ['100'], 'end': ['1']},
                       {'window': ['custom'], 'start': ['-1'], 'end': ['100']}, {'window': ['custom'], 'start': ['100'], 'end': ['999999999999']}, {'start': ['1']}]:
            with self.assertRaises(ValueError):
                traces.search_traces(params)

    def test_field_query_scopes_quotes_negation_and_injection(self):
        self.assertEqual(traces.query_clauses('name:"POST /api/orders" -service:user status:error', 'root'),
                         ['trace:rootName = "POST /api/orders"', 'trace:rootService != "user"', 'status = error'])
        self.assertEqual(traces.query_clauses('name:订单', 'all'), ['name = "订单"'])
        self.assertEqual(traces.query_clauses('trace_id:' + 'a' * 32, 'root'), ['trace:id = "' + 'a' * 32 + '"'])
        for query in ['url:http://attacker', 'name:', 'status:success', 'name:"unfinished', 'trace_id:bad', 'service:other', 'order_id:9999999999999999999', 'event_id:bad', 'name:foo\nbar']:
            with self.subTest(query=query), self.assertRaises(ValueError):
                traces.query_clauses(query, 'root')
        clauses = traces.query_clauses('name:"x\\\" } | count()"', 'root')
        self.assertEqual(clauses, ['trace:rootName = "x\\\" } | count()"'])
        with patch.object(traces, 'read_tempo', return_value={}) as read:
            traces.search_traces({'services': ['user', 'order-api'], 'names': ['POST /api/orders']})
            query = parse_qs(urlparse(read.call_args.args[0]).query)['q'][0]
            self.assertIn('resource.service.name = "user" || resource.service.name = "order-api"', query)
            self.assertIn('trace:rootName = "POST /api/orders"', query)
            self.assertIn('deployment.environment.name = "local"', query)

    def test_long_range_chunks_merge_duplicates_and_fail_as_a_whole(self):
        first = {'traceID': 'a' * 32, 'startTimeUnixNano': '1000'}
        second = {'traceID': 'b' * 32, 'startTimeUnixNano': '2000'}
        with patch.object(traces, 'read_tempo', side_effect=[{'traces': [first]}, {'traces': [first, second]}]) as read:
            result = traces.search_traces({'window': ['14d']})
            self.assertEqual([r['trace_id'] for r in result['traces']], ['b' * 32, 'a' * 32])
            self.assertEqual(read.call_count, 2)
            chunks = [parse_qs(urlparse(call.args[0]).query) for call in read.call_args_list]
            self.assertEqual(chunks[0]['start'], chunks[1]['end'])
            self.assertTrue(all(int(c['end'][0]) - int(c['start'][0]) <= 7 * 86400 for c in chunks))
        with patch.object(traces, 'read_tempo', side_effect=[{'traces': [first]}, traces.TraceUnavailable()]):
            with self.assertRaises(traces.TraceUnavailable):
                traces.search_traces({'window': ['14d']})

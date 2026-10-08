import unittest
from unittest.mock import patch
from performance.web import traces
from performance.web.trace_insights import analyze


def span(sid, parent='', start=0, duration=100, attrs=None):
    return dict(span_id=sid, parent_span_id=parent, start_time_ns=str(start * 1000000),
                duration_ms=duration, kind='SPAN_KIND_SERVER', service='order-api', name=sid,
                status='unset', attributes=attrs or {}, resource={}, events=[], links=[])


class TraceInsightsTests(unittest.TestCase):
    def test_duplicate_fragments_preserve_complementary_fields(self):
        rich = span('same', attrs={'db.query.fingerprint': 'abcd', 'db.system': 'mysql'})
        rich['resource'] = {'service.version': 'release-42'}
        rich['events'] = [{'name': 'business.completed', 'time_ns': '10', 'attributes': {'seckill.order_id': '12'}}]
        partial = span('same', attrs={'db.system': 'mysql', 'db.operation': 'SELECT'})
        partial['resource'] = {'service.version': 'unknown', 'service.instance.id': 'pod-1'}
        partial['status'] = 'error'
        for nodes in ([rich, partial], [partial, rich]):
            result = traces.merge_spans(nodes)
            self.assertEqual(len(result), 1)
            node = result[0]
            self.assertEqual(node['attributes']['db.query.fingerprint'], 'abcd')
            self.assertEqual(node['attributes']['db.operation'], 'SELECT')
            self.assertEqual(node['resource']['service.version'], 'release-42')
            self.assertEqual(node['status'], 'error')
            self.assertEqual(len(node['events']), 1)

    def test_parallel_children_use_interval_union(self):
        nodes = [span('root'), span('a', 'root', 10, 60), span('b', 'root', 40, 50),
                 span('orphan', 'missing', 120, 50)]
        result = analyze(nodes)
        self.assertEqual(nodes[0]['self_duration_ms'], 20)
        self.assertEqual(result['response_ms'], 100)
        self.assertEqual(result['observed_span_ms'], 170)
        self.assertEqual(result['quality']['missing_parent_nodes'], ['orphan'])
        self.assertEqual(result['quality']['completeness'], 'not_proven')

    def test_children_outside_parent_are_clipped(self):
        nodes = [span('root', start=10), span('child', 'root', 0, 200)]
        result = analyze(nodes, True)
        self.assertEqual(nodes[0]['self_duration_ms'], 0)
        self.assertEqual(result['quality']['clock_order_nodes'], ['child'])
        self.assertTrue(result['quality']['truncated'])

    def test_accepted_is_not_final_business_success(self):
        nodes = [span('root', attrs={'http.status_code': 202}),
                 span('business', 'root', attrs={'seckill.outcome': 'success',
                      'seckill.entity': 'order', 'seckill.business_state': 'PENDING_INVENTORY'})]
        summary = traces.summarize_trace(nodes)
        self.assertEqual(summary['status'], 'accepted')
        self.assertEqual(summary['api_result'], 'accepted')
        self.assertEqual(summary['business']['business_state'], 'PENDING_INVENTORY')
        self.assertEqual(nodes[0]['status'], 'unset')

    def test_consumer_completion_and_failure_are_explicit_evidence(self):
        node = span('consumer', attrs={'seckill.outcome': 'processed'})
        self.assertEqual(traces.summarize_trace([node])['status'], 'ok')
        self.assertEqual(traces.summarize_trace([node])['api_result'], 'unknown')
        node['attributes']['seckill.outcome'] = 'failed'
        self.assertEqual(traces.summarize_trace([node])['status'], 'error')

    def test_lifecycle_is_bounded_and_reports_partial_evidence(self):
        rows = [{'trace_id': f'{i:032x}'} for i in range(21)]
        nodes = [span(str(i), attrs={'seckill.order_id': '12'}) for i in range(30)]
        with patch.object(traces, 'search_traces', return_value={'traces': rows, 'truncated': False, 'sampling_note': 'sampled'}), patch.object(traces, 'trace_detail', return_value={'spans': nodes}):
            result = traces.trace_lifecycle({'order_id': ['12']})
        self.assertEqual(result['trace_count'], 20)
        self.assertEqual(len(result['timeline']), 300)
        self.assertTrue(result['truncated'])
        self.assertFalse(result['authoritative_order_state'])
        with self.assertRaises(ValueError):
            traces.trace_lifecycle({'order_id': ['12'], 'event_id': ['x']})
        with self.assertRaises(ValueError):
            traces.trace_lifecycle({'url': ['http://private']})

    def test_order_execution_keeps_parent_and_dependency_context(self):
        parent = span('root', start=1)
        order = span('order', parent='root', start=2, attrs={'seckill.order_id': '12'})
        dependency = span('sql', parent='order', start=3, attrs={'db.system': 'mysql'})
        other = span('other-order', parent='root', start=4, attrs={'seckill.order_id': '13'})
        later = span('payment', start=8, attrs={'seckill.order_id': '12'})
        rows = [{'trace_id': 'b'*32}, {'trace_id': 'a'*32}]
        details = {'a'*32: {'spans': [dependency, parent, order, other]}, 'b'*32: {'spans': [later]}}
        with patch.object(traces, 'order_evidence', return_value={'availability':'unavailable'}), patch.object(traces, 'search_traces', return_value={'traces':rows,'truncated':False,'sampling_note':'sampled'}), patch.object(traces, 'trace_detail', side_effect=lambda id: details[id]):
            result = traces.trace_lifecycle({'order_id':['12']})
        self.assertEqual([e['trace_id'] for e in result['executions']], ['a'*32, 'b'*32])
        tree = result['executions'][0]['spans']
        self.assertEqual([s['span_id'] for s in tree], ['root','order','sql','other-order'])
        self.assertEqual([s['identifier_match'] for s in tree], [False,True,False,False])
        self.assertEqual(tree[2]['parent_span_id'], 'order')
        self.assertEqual(len(result['timeline']), 2)

    def test_execution_tree_budget_is_explicit(self):
        nodes = [span(str(i), start=i, attrs={'seckill.order_id':'12'}) for i in range(205)]
        with patch.object(traces, 'order_evidence', return_value={}), patch.object(traces, 'search_traces', return_value={'traces':[{'trace_id':'a'*32}], 'truncated':False,'sampling_note':'sampled'}), patch.object(traces, 'trace_detail', return_value={'spans':nodes}):
            result=traces.trace_lifecycle({'order_id':['12']})
        self.assertEqual(len(result['executions'][0]['spans']), 200)
        self.assertTrue(result['executions'][0]['spans_truncated'])
        self.assertTrue(result['truncated'])

    def test_detail_preserves_only_safe_events_and_raw_unset(self):
        attrs = lambda values: [{'key': k, 'value': {'stringValue': v}} for k, v in values.items()]
        raw = {'spanId': 'ab' * 8, 'events': [
            {'name': 'business.completed', 'attributes': attrs({'seckill.order_id': '12', 'password': 'secret'})},
            {'name': 'exception', 'attributes': attrs({'exception.message': 'private'})}]}
        data = {'resourceSpans': [{'resource': {'attributes': attrs({'service.namespace': 'seckill',
            'deployment.environment.name': 'local', 'service.version': 'v1', 'service.instance.id': 'pod-1'})},
            'scopeSpans': [{'spans': [raw]}]}]}
        with patch.object(traces, 'read_tempo', return_value=data):
            result = traces.trace_detail('cd' * 16)
        node = result['spans'][0]
        self.assertEqual(node['status'], 'unset')
        self.assertEqual(node['resource']['service.version'], 'v1')
        self.assertEqual(node['events'][0]['attributes'], {'seckill.order_id': '12'})
        self.assertEqual(len(node['events']), 1)

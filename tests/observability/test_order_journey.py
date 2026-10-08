import unittest
import time
from datetime import datetime
from unittest.mock import MagicMock, patch
from performance.web import traces
from performance.monitoring.runtime.order_snapshot import read_order, recent_orders


class OrderJourneyTests(unittest.TestCase):
    def test_recent_orders_merge_shards_and_use_cursor_without_duplicates(self):
        connection=MagicMock()
        cursor=connection.cursor.return_value.__enter__.return_value
        def row(i):
            return (i,4,1,'PAID',datetime(2026,10,8),datetime(2026,10,8))
        cursor.fetchall.side_effect=[[row(i) for i in range(100,151)],[],[],[]]
        result=recent_orders(connection,1,int(time.time()),status='PAID',before='200')
        self.assertEqual(len(result['orders']),50)
        self.assertEqual(result['orders'][0]['order_id'],'150')
        self.assertEqual(result['next_cursor'],'101')
        self.assertTrue(result['has_more'])
        for call in cursor.execute.call_args_list:
            if call.args[0].startswith('SELECT'):
                self.assertIn('order_id < %s',call.args[0])
                self.assertEqual(call.args[1][-2:],('PAID',200))
        connection.rollback.assert_called_once()

    def test_order_filters_reject_arbitrary_values_before_backend_read(self):
        with patch.object(traces,'urlopen') as backend:
            for params in ({'status':['BAD']},{'order_id':['1 OR 1=1']},{'url':['http://private']},{'before':['-1']}):
                with self.assertRaises(ValueError):
                    traces.search_orders(params)
            backend.assert_not_called()

    def test_database_evidence_is_read_only_parameterized_and_does_not_read_payload(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect = [[(12, 4, 1, 'PAID', datetime(2026, 10, 8), datetime(2026, 10, 8))], [], [], [],
                                     [(3, 'PAYMENT_REQUESTED', 'payment', 'PUBLISHED', 0, datetime(2026, 10, 8), None)], [], [], []]
        result = read_order(connection, '12')
        self.assertEqual(result['order']['status'], 'PAID')
        self.assertEqual(result['order']['order_id'], '12')
        self.assertFalse(result['history_complete'])
        calls = cursor.execute.call_args_list
        self.assertTrue(any('READ ONLY' in call.args[0] for call in calls))
        for call in calls:
            sql = call.args[0].lower()
            self.assertNotIn('payload', sql)
            self.assertNotIn('user_id', sql)
            if sql.startswith('select'):
                self.assertEqual(call.args[1], (12,))
        connection.rollback.assert_called_once()

    def test_invalid_identifier_never_opens_cursor(self):
        connection = MagicMock()
        for identifier in ('0', '-1', '12 OR 1=1', str(2**63)):
            with self.assertRaises(ValueError):
                read_order(connection, identifier)
        connection.cursor.assert_not_called()

    def test_tempo_outage_preserves_authoritative_state(self):
        evidence = {'availability': 'available', 'found': True, 'order': {'status': 'PAID'}}
        with patch.object(traces, 'order_evidence', return_value=evidence), patch.object(traces, 'search_traces', side_effect=traces.TraceUnavailable):
            result = traces.trace_lifecycle({'order_id': ['12'], 'window': ['1h']})
        self.assertEqual(result['business_evidence']['order']['status'], 'PAID')
        self.assertEqual(result['trace_availability'], 'unavailable')
        self.assertTrue(result['authoritative_order_state'])
        self.assertEqual(result['timeline'], [])

    def test_root_execution_types_and_service_union(self):
        def node(kind, service, parent='', attrs=None):
            return {'span_id': service, 'parent_span_id': parent, 'kind': kind, 'service': service,
                    'name': service, 'status': 'unset', 'attributes': attrs or {}}
        root = node('SPAN_KIND_SERVER', 'order-api', attrs={'http.method': 'POST'})
        child = node('SPAN_KIND_SERVER', 'inventory-api', 'order-api')
        summary = traces.summarize_trace([root, child])
        self.assertEqual(summary['services'], ['inventory-api', 'order-api'])
        self.assertEqual(summary['execution_type'], 'api')
        self.assertEqual(summary['span_count'], 2)
        self.assertEqual(traces.summarize_trace([node('SPAN_KIND_CONSUMER', 'order-worker')])['execution_type'], 'message')
        self.assertEqual(traces.summarize_trace([node('SPAN_KIND_INTERNAL', 'order-worker')])['execution_type'], 'task')
        self.assertEqual(traces.summarize_trace([node('SPAN_KIND_CLIENT', 'order-api')])['execution_type'], 'unknown')

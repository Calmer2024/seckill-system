import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry import trace
from seckill_observability.tracing import business_attributes, safe_span, service_version


class TraceCollectionTests(unittest.TestCase):
    def test_structured_context_excludes_identity_and_body(self):
        span = Mock()
        business_attributes(span, SimpleNamespace(product_id=12, quantity=1, status='CREATED',
            user_id=123, password='private', page=2, size=20))
        collected = {call.args[0]: call.args[1] for call in span.set_attribute.call_args_list}
        self.assertEqual(collected, {'seckill.product_id': '12', 'seckill.quantity': 1,
            'seckill.business_state': 'CREATED', 'seckill.page': 2, 'seckill.page_size': 20})
        business_attributes(span, [])
        span.set_attribute.assert_called_with('seckill.result_count', 0)

    def test_sql_fingerprint_does_not_export_statement_or_literals(self):
        provider = TracerProvider()
        fingerprints = []
        for value in ('secret-one', 'secret-two'):
            with provider.get_tracer('test').start_as_current_span('SELECT', attributes={
                'db.system': 'mysql', 'db.statement': f"SELECT * FROM orders WHERE token = '{value}' AND id = 12"}) as span:
                pass
            safe = safe_span(span)
            self.assertNotIn('db.statement', safe.attributes)
            fingerprints.append(safe.attributes['db.query.fingerprint'])
        self.assertEqual(fingerprints[0], fingerprints[1])
        self.assertEqual(len(fingerprints[0]), 16)
        provider.shutdown()

    def test_version_prefers_release_id_then_build_identity(self):
        with patch.dict('os.environ', {'SERVICE_VERSION': 'release-42'}):
            self.assertEqual(service_version(), 'release-42')
        with patch.dict('os.environ', {}, clear=True), patch('pathlib.Path.read_text', return_value='source-sha256:abcd'):
            self.assertEqual(service_version(), 'source-sha256:abcd')
        with patch.dict('os.environ', {'SERVICE_VERSION': 'unknown'}), patch('pathlib.Path.read_text', return_value='source-sha256:abcd'):
            self.assertEqual(service_version(), 'source-sha256:abcd')

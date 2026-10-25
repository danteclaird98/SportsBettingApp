"""Offline component/transport tests: never use credentials or live inference."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import MagicMock, patch

from edgeodds.integrations.decisions import (
    DecisionAdvisor, DecisionTransportError, EvidencePacket, OpenAIDecisionsTransport,
)
from edgeodds.integrations.edgeboard import edgeboard_contract
from edgeodds.models import MarketKey, MarketStatus, MarketType, NormalizedQuote
from edgeodds.tests.test_edgeboard_integration import board

NOW = datetime(2026, 10, 25, 20, tzinfo=timezone.utc)
CHOICES = ('SUFFICIENT', 'INSUFFICIENT', 'UNCERTAIN')


def packet(**changes):
    quote = NormalizedQuote(
        provider='fixture-provider', bookmaker='fixture-book',
        source_event_id='native-event', source_market_id='native-market',
        key=MarketKey('event-1', MarketType.TOTAL, 'over', 44.5,
                      settlement_rules_hash='a' * 64),
        decimal_price=1.91, retrieved_at=NOW - timedelta(seconds=1),
        source_updated_at=NOW - timedelta(seconds=2), status=MarketStatus.OPEN,
        source_payload_hash='b' * 64,
    )
    values = dict(quote=quote, decision_at=NOW, identity_verified=True, rules_verified=True)
    values.update(changes)
    return EvidencePacket(**values)


def response(payload, choice='SUFFICIENT'):
    return {
        'model': 'gpt-6-luna',
        'answers': [{
            'type': 'choice', 'name': payload['questions'][0]['name'],
            'choice': choice, 'confidence': 0.9,
            'probabilities': [
                {'value': value, 'probability': 0.9 if value == choice else 0.05}
                for value in CHOICES
            ],
        }],
        'usage': {'input_tokens': 100},
    }


class DecisionsIntegrationTests(unittest.TestCase):
    def advisor(self, transport, **options):
        return DecisionAdvisor(enabled=True, transport=transport, clock=lambda: NOW, **options)

    def test_default_disabled_never_calls_transport_or_changes_existing_output(self):
        transport = MagicMock(side_effect=AssertionError('Disabled network call'))
        before = edgeboard_contract(board())
        result = DecisionAdvisor(transport=transport).evaluate(packet(), request_id='req-1')
        self.assertEqual(result.status, 'DISABLED')
        self.assertIsNone(result.choice)
        transport.assert_not_called()
        self.assertEqual(edgeboard_contract(board()), before)

    def test_wire_contract_and_local_packet_binding(self):
        seen = []
        def transport(payload, timeout):
            seen.append(deepcopy(payload))
            self.assertGreater(timeout, 0)
            return response(payload)
        source = packet()
        before = source.to_payload()
        result = self.advisor(transport).evaluate(source, request_id='req-1')
        self.assertEqual(result.status, 'ADVISORY')
        self.assertEqual(result.choice, 'SUFFICIENT')
        self.assertTrue(result.deterministic_ready)
        self.assertEqual(result.packet_hash, source.packet_hash)
        self.assertEqual(result.request_id, 'req-1')
        self.assertEqual(result.input_tokens, 100)
        self.assertEqual(result.model, 'gpt-6-luna')
        self.assertTrue(result.adapter_version)
        self.assertEqual(result.schema_version, 'edgeodds.decisions.v1')
        self.assertEqual(source.to_payload(), before)
        self.assertEqual(set(seen[0]), {'model', 'input', 'questions'})
        self.assertIsInstance(seen[0]['input'], str)
        json.loads(seen[0]['input'])
        self.assertEqual(seen[0]['questions'][0]['type'], 'choice')
        self.assertNotIn('evidence_paths', seen[0]['questions'][0])

    def test_api_agreement_cannot_override_local_identity_or_rules_failures(self):
        for flags in [dict(identity_verified=False), dict(rules_verified=False)]:
            with self.subTest(flags=flags):
                result = self.advisor(lambda p, t: response(p)).evaluate(packet(**flags), request_id='req-1')
                self.assertFalse(result.deterministic_ready)
                self.assertTrue(result.reasons)
                self.assertEqual(edgeboard_contract(board())['execution'], 'DISABLED')

    def test_missing_stale_future_or_suspended_quote_never_looks_ready(self):
        original = packet()
        variants = [
            replace(original.quote, source_updated_at=None),
            replace(original.quote, source_updated_at=NOW - timedelta(seconds=91)),
            replace(original.quote, source_updated_at=NOW + timedelta(seconds=30)),
            replace(original.quote, status=MarketStatus.SUSPENDED),
        ]
        for quote in variants:
            with self.subTest(quote=quote):
                result = self.advisor(lambda p, t: response(p)).evaluate(packet(quote=quote), request_id='req-1')
                self.assertFalse(result.deterministic_ready)
                self.assertTrue(result.reasons)

    def test_wrong_question_name_and_refusal_are_unavailable(self):
        for answer in [dict(type='refusal'), dict(type='choice', choice='SUFFICIENT', name='wrong')]:
            def transport(payload, timeout):
                value = response(payload)
                value['answers'][0].update(answer)
                return value
            with self.subTest(answer=answer):
                result = self.advisor(transport).evaluate(packet(), request_id='req-1')
                self.assertEqual(result.status, 'UNAVAILABLE')
                self.assertIsNone(result.choice)

    def test_malformed_responses_fail_without_replacing_existing_workflow(self):
        mutations = [
            lambda v: v.update(model='unsupported-model'),
            lambda v: v.update(answers=[]),
            lambda v: v['answers'].append(deepcopy(v['answers'][0])),
            lambda v: v['answers'][0].update(choice='PLACE_BET'),
            lambda v: v['answers'][0].update(confidence=float('nan')),
            lambda v: v['answers'][0].update(confidence=True),
            lambda v: v['answers'][0].update(probabilities=[]),
            lambda v: v['answers'][0]['probabilities'][0].update(probability=2),
            lambda v: v['answers'][0]['probabilities'][1].update(value='SUFFICIENT'),
            lambda v: v['usage'].update(input_tokens=True),
            lambda v: v['usage'].update(input_tokens=-1),
            lambda v: v.pop('usage'),
        ]
        baseline = edgeboard_contract(board())
        for mutate in mutations:
            def transport(payload, timeout):
                value = response(payload)
                mutate(value)
                return value
            with self.subTest(mutation=mutate):
                result = self.advisor(transport).evaluate(packet(), request_id='req-1')
                self.assertEqual(result.status, 'UNAVAILABLE')
                self.assertIsNone(result.choice)
                self.assertEqual(edgeboard_contract(board()), baseline)

    def test_timeout_auth_rate_limit_and_unknown_errors_are_sanitized_without_retries(self):
        for error in [TimeoutError('SECRET'), DecisionTransportError('AUTH'),
                      DecisionTransportError('RATE_LIMIT'), RuntimeError('SECRET')]:
            transport = MagicMock(side_effect=error)
            advisor = self.advisor(transport)
            with self.subTest(error=type(error).__name__):
                first = advisor.evaluate(packet(), request_id='req-1')
                second = advisor.evaluate(packet(), request_id='req-1')
                self.assertEqual(first.status, 'UNAVAILABLE')
                self.assertEqual(first, second)
                self.assertNotIn('SECRET', repr(first))
                self.assertEqual(transport.call_count, 1)

    def test_duplicate_concurrent_requests_submit_once_and_rebind_is_rejected(self):
        transport = MagicMock(side_effect=lambda p, t: response(p))
        advisor = self.advisor(transport)
        source = packet()
        with ThreadPoolExecutor(max_workers=4) as workers:
            results = list(workers.map(lambda _: advisor.evaluate(source, request_id='same-id'), range(4)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(transport.call_count, 1)
        changed = packet(quote=replace(source.quote, decimal_price=2.1))
        conflict = advisor.evaluate(changed, request_id='same-id')
        self.assertEqual(conflict.status, 'UNAVAILABLE')
        self.assertEqual(transport.call_count, 1)

    def test_call_budget_stops_new_requests(self):
        transport = MagicMock(side_effect=lambda p, t: response(p))
        advisor = self.advisor(transport, max_calls=1)
        advisor.evaluate(packet(), request_id='first')
        result = advisor.evaluate(packet(), request_id='second')
        self.assertEqual(result.status, 'UNAVAILABLE')
        self.assertEqual(transport.call_count, 1)

    def test_quote_expiring_during_request_and_cached_replay_are_not_current_readiness(self):
        current = [NOW]
        def transport(payload, timeout):
            current[0] = NOW + timedelta(seconds=91)
            return response(payload)
        advisor = DecisionAdvisor(enabled=True, transport=transport, clock=lambda: current[0])
        result = advisor.evaluate(packet(), request_id='expires')
        self.assertEqual(result.status, 'UNAVAILABLE')
        self.assertFalse(result.deterministic_ready)
        current[0] = NOW
        calls = MagicMock(side_effect=lambda p, t: response(p))
        advisor = DecisionAdvisor(enabled=True, transport=calls, clock=lambda: current[0])
        self.assertEqual(advisor.evaluate(packet(), request_id='cached').status, 'ADVISORY')
        current[0] += timedelta(seconds=91)
        self.assertEqual(advisor.evaluate(packet(), request_id='cached').status, 'UNAVAILABLE')
        self.assertEqual(calls.call_count, 1)

    def test_clock_failure_is_unavailable_without_transport_or_exception_text(self):
        transport = MagicMock(side_effect=AssertionError('Unexpected API request'))
        def broken_clock():
            raise RuntimeError('SECRET_CLOCK_ERROR')
        advisor = DecisionAdvisor(enabled=True, transport=transport, clock=broken_clock)
        result = advisor.evaluate(packet(), request_id='bad-clock')
        self.assertEqual(result.status, 'UNAVAILABLE')
        self.assertIn('INVALID_CLOCK', result.reasons)
        self.assertNotIn('SECRET_CLOCK_ERROR', repr(result))
        transport.assert_not_called()

    def test_post_decision_evidence_is_rejected_without_inference(self):
        transport = MagicMock(side_effect=AssertionError('Lookahead request'))
        source = packet(decision_at=NOW - timedelta(seconds=10))
        result = self.advisor(transport).evaluate(source, request_id='lookahead')
        self.assertEqual(result.status, 'UNAVAILABLE')
        self.assertIn('EVIDENCE_AFTER_DECISION', result.reasons)
        transport.assert_not_called()

    def test_blocking_transport_completion_after_deadline_is_not_accepted(self):
        transport = MagicMock(side_effect=lambda p, t: response(p))
        with patch('edgeodds.integrations.decisions.monotonic', side_effect=[1.0, 7.0]):
            result = self.advisor(transport, timeout_seconds=5).evaluate(packet(), request_id='late')
        self.assertEqual(result.status, 'UNAVAILABLE')
        self.assertIn('TIMEOUT', result.reasons)

    def test_invalid_request_ids_fail_before_transport(self):
        transport = MagicMock()
        advisor = self.advisor(transport)
        for request_id in ['', '../escape', 'a' * 81, True]:
            with self.subTest(request_id=request_id), self.assertRaises(ValueError):
                advisor.evaluate(packet(), request_id=request_id)
        transport.assert_not_called()

    def test_packet_rejects_missing_provenance_coercions_and_ambiguous_time(self):
        original = packet()
        factories = [
            lambda: packet(identity_verified='true'),
            lambda: packet(rules_verified=1),
            lambda: packet(decision_at=NOW.replace(tzinfo=None)),
            lambda: packet(quote=replace(original.quote, source_payload_hash='not-a-sha')),
            lambda: packet(quote=replace(original.quote, decimal_price=True)),
        ]
        for factory in factories:
            with self.subTest(factory=factory), self.assertRaises((ValueError, TypeError)):
                factory()

    def test_http_transport_maps_status_without_following_redirects_or_leaking_key(self):
        for status, code in [(401, 'AUTH'), (403, 'AUTH'), (429, 'RATE_LIMIT'), (302, 'HTTP_ERROR'), (500, 'HTTP_ERROR')]:
            with self.subTest(status=status), patch('http.client.HTTPSConnection') as connection:
                reply = connection.return_value.getresponse.return_value
                reply.status = status
                reply.read.return_value = b'{"error":"SECRET_PROVIDER_BODY"}'
                transport = OpenAIDecisionsTransport('test-not-a-real-key')
                with self.assertRaises(DecisionTransportError) as raised:
                    transport({'model': 'gpt-6-luna'}, 1.0)
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn('SECRET_PROVIDER_BODY', str(raised.exception))
                self.assertNotIn('test-not-a-real-key', repr(transport))
                self.assertEqual(connection.call_count, 1)
                connection.return_value.close.assert_called_once()

    def test_http_success_body_and_payload_bounds(self):
        with patch('http.client.HTTPSConnection') as connection:
            reply = connection.return_value.getresponse.return_value
            reply.status = 200
            reply.read.return_value = b'{"answers": []}'
            transport = OpenAIDecisionsTransport('test-not-a-real-key')
            self.assertEqual(transport({'input': 'fixture'}, 2.0), {'answers': []})
            args, kwargs = connection.return_value.request.call_args
            self.assertEqual(args[:2], ('POST', '/v1/decisions'))
            self.assertEqual(json.loads(kwargs['body']), {'input': 'fixture'})
            connection.assert_called_once_with('api.openai.com', timeout=2.0)
        with patch('http.client.HTTPSConnection') as connection:
            with self.assertRaises(DecisionTransportError) as raised:
                transport({'input': 'x' * 16385}, 2.0)
            self.assertEqual(raised.exception.code, 'REQUEST_TOO_LARGE')
            connection.assert_not_called()

    def test_http_malformed_and_oversized_responses_fail_closed(self):
        for raw, code in [(b'not-json', 'INVALID_RESPONSE'), (b'[]', 'INVALID_RESPONSE'),
                          (b'x' * 65537, 'RESPONSE_TOO_LARGE')]:
            with self.subTest(code=code), patch('http.client.HTTPSConnection') as connection:
                reply = connection.return_value.getresponse.return_value
                reply.status = 200
                reply.read.return_value = raw
                with self.assertRaises(DecisionTransportError) as raised:
                    OpenAIDecisionsTransport('test-not-a-real-key')({'input': 'fixture'}, 2)
                self.assertEqual(raised.exception.code, code)


if __name__ == '__main__':
    unittest.main()

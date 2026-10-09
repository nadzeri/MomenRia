import threading

from django.db import connection, connections, close_old_connections
from django.test import TransactionTestCase

from momenria.http import ApiError
from .models import Refund
from .services import request_refund
from . import tests as commerce_test_helpers


class ConcurrentRefundTests(TransactionTestCase):
    make_order = commerce_test_helpers.MidtransSignatureTests.make_order

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Concurrency proof requires PostgreSQL")

    def race(self, requests):
        barrier = threading.Barrier(len(requests))
        outcomes = []

        def submit(order, key):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                refund, created = request_refund(None, order.id, "Verified full refund remedy", key)
                outcomes.append(("refund", refund.id, created))
            except Exception as error:
                outcomes.append(("error", type(error), getattr(error, "code", None)))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=submit, args=request) for request in requests]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
        return outcomes

    def test_different_keys_for_one_order_create_one_full_refund(self):
        _, order = self.make_order("MR-REFUND-ONE", state="paid")
        outcomes = self.race([(order, f"different-{number}") for number in range(5)])
        self.assertEqual({item[0] for item in outcomes}, {"refund"})
        self.assertEqual(Refund.objects.filter(order=order).count(), 1)
        self.assertEqual(sum(item[2] for item in outcomes), 1)

    def test_same_key_for_different_orders_returns_conflict_without_server_error(self):
        _, first = self.make_order("MR-REFUND-FIRST", state="paid")
        _, second = self.make_order("MR-REFUND-SECOND", state="paid")
        outcomes = self.race([(first, "shared-key"), (second, "shared-key")])
        self.assertEqual(sum(item[0] == "refund" for item in outcomes), 1)
        self.assertIn(("error", ApiError, "idempotency_conflict"), outcomes)

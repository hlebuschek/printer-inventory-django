from decimal import Decimal

from django.test import TestCase

from contracts.api_views_import import _resolve_contract
from contracts.models import Contract, ServiceProvider


class ResolveContractTests(TestCase):
    """Договор сессии импорта: выбор существующего или создание из формы."""

    def setUp(self):
        self.amb = ServiceProvider.objects.get(code="amb")
        self.tonex = ServiceProvider.objects.get(code="tonex")

    def test_existing_contract_is_returned(self):
        contract = Contract.objects.create(number="1/2026", provider=self.amb)

        resolved, error = _resolve_contract({"contract_id": contract.id}, self.amb)

        self.assertIsNone(error)
        self.assertEqual(resolved, contract)

    def test_contract_of_another_provider_is_rejected(self):
        contract = Contract.objects.create(number="1/2026", provider=self.amb)

        resolved, error = _resolve_contract({"contract_id": contract.id}, self.tonex)

        self.assertIsNone(resolved)
        self.assertIn("не найден", error)

    def test_missing_contract_is_rejected(self):
        resolved, error = _resolve_contract({}, self.amb)

        self.assertIsNone(resolved)
        self.assertIn("Не выбран договор", error)

    def test_new_contract_is_created_with_comma_prices(self):
        payload = {
            "new_contract": {
                "number": " 7/2026 ",
                "name": "Покопийная печать",
                "price_a4_bw": "0,95",
                "price_a4_color": "5.5",
            }
        }

        resolved, error = _resolve_contract(payload, self.tonex)

        self.assertIsNone(error)
        self.assertEqual(resolved.number, "7/2026")
        self.assertEqual(resolved.provider, self.tonex)
        self.assertEqual(resolved.price_a4_bw, Decimal("0.95"))
        self.assertEqual(resolved.price_a4_color, Decimal("5.5"))
        self.assertEqual(resolved.price_a3_bw, Decimal("0"))
        self.assertTrue(Contract.objects.filter(number="7/2026").exists())

    def test_garbage_price_is_rejected_without_saving(self):
        payload = {"new_contract": {"number": "8/2026", "price_a4_bw": "дорого"}}

        resolved, error = _resolve_contract(payload, self.tonex)

        self.assertIsNone(resolved)
        self.assertIn("не число", error)
        self.assertFalse(Contract.objects.filter(number="8/2026").exists())

    def test_negative_price_is_rejected(self):
        payload = {"new_contract": {"number": "9/2026", "price_a4_bw": "-1"}}

        resolved, error = _resolve_contract(payload, self.tonex)

        self.assertIsNone(resolved)
        self.assertFalse(Contract.objects.filter(number="9/2026").exists())

    def test_duplicate_number_is_rejected(self):
        Contract.objects.create(number="1/2026", provider=self.amb)

        resolved, error = _resolve_contract({"new_contract": {"number": "1/2026"}}, self.tonex)

        self.assertIsNone(resolved)
        self.assertEqual(Contract.objects.filter(number="1/2026").count(), 1)

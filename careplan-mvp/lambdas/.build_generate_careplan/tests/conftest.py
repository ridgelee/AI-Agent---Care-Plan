"""
Shared fixtures for all tests.

factory-boy factories live here so both unit/ and integration/ can import them.
"""
import pytest
from datetime import date
from django.test import Client

import factory
from careplan.models import Patient, Provider, Order, CarePlan


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

class PatientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Patient

    mrn = factory.Sequence(lambda n: f'{100000 + n}')
    first_name = 'John'
    last_name = 'Doe'
    dob = date(1990, 1, 15)


class ProviderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Provider

    npi = factory.Sequence(lambda n: f'{1000000000 + n}')
    name = 'Dr. Smith'


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    patient = factory.SubFactory(PatientFactory)
    provider = factory.SubFactory(ProviderFactory)
    medication_name = 'Humira'
    primary_diagnosis = 'L40.0'
    status = 'pending'


class CarePlanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CarePlan

    order = factory.SubFactory(OrderFactory)
    content = 'Test care plan content.'
    llm_model = 'claude-sonnet-4-20250514'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    """Django test client for integration tests."""
    return Client()


@pytest.fixture
def sample_order_payload():
    """Minimal valid payload for POST /api/orders/."""
    return {
        'patient': {
            'mrn': '999001',
            'first_name': 'Alice',
            'last_name': 'Wang',
            'dob': '1985-03-20',
        },
        'provider': {
            'npi': '9999900001',
            'name': 'Dr. Test',
        },
        'medication': {
            'name': 'Humira',
            'primary_diagnosis': 'L40.0',
        },
    }

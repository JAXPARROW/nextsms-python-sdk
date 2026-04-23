"""
Tests for reseller functionality — recharge_customer, deduct_customer.
"""

import pytest
from unittest.mock import Mock, patch

from nextsms import NextSMS, NextSMSResponse
from nextsms.exceptions import NextSMSValidationError

PATCH_TARGET = "nextsms.client.PooledHTTPClient"


def _make_client():
    with patch(PATCH_TARGET) as cls:
        http_mock = Mock()
        cls.return_value = http_mock
        client = NextSMS(username="u", password="p")

    client._handle_response = Mock(
        return_value=NextSMSResponse(success=True, status_code=200, message="OK", data={})
    )
    return client


class TestRechargeCustomer:
    def setup_method(self):
        self.client = _make_client()

    def test_calls_recharge_endpoint(self):
        self.client.recharge_customer(email="customer@example.com", smscount=5000)
        self.client.http.request.assert_called_once_with(
            "POST",
            "api/reseller/v1/sub_customer/recharge",
            json={"email": "customer@example.com", "smscount": 5000},
        )

    def test_returns_response(self):
        result = self.client.recharge_customer(email="customer@example.com", smscount=1000)
        assert result.success is True
        assert result.status_code == 200

    def test_empty_email_raises(self):
        with pytest.raises(NextSMSValidationError, match="email"):
            self.client.recharge_customer(email="", smscount=1000)

    def test_whitespace_email_raises(self):
        with pytest.raises(NextSMSValidationError, match="email"):
            self.client.recharge_customer(email="   ", smscount=1000)

    def test_zero_smscount_raises(self):
        with pytest.raises(NextSMSValidationError, match="positive"):
            self.client.recharge_customer(email="customer@example.com", smscount=0)

    def test_negative_smscount_raises(self):
        with pytest.raises(NextSMSValidationError, match="positive"):
            self.client.recharge_customer(email="customer@example.com", smscount=-100)

    def test_non_integer_smscount_raises(self):
        with pytest.raises(NextSMSValidationError, match="positive"):
            self.client.recharge_customer(email="customer@example.com", smscount=500.5)

    def test_no_api_call_on_validation_failure(self):
        with pytest.raises(NextSMSValidationError):
            self.client.recharge_customer(email="", smscount=1000)
        self.client.http.request.assert_not_called()


class TestDeductCustomer:
    def setup_method(self):
        self.client = _make_client()

    def test_calls_deduct_endpoint(self):
        self.client.deduct_customer(email="customer@example.com", smscount=2000)
        self.client.http.request.assert_called_once_with(
            "POST",
            "api/reseller/v1/sub_customer/deduct",
            json={"email": "customer@example.com", "smscount": 2000},
        )

    def test_returns_response(self):
        result = self.client.deduct_customer(email="customer@example.com", smscount=500)
        assert result.success is True

    def test_empty_email_raises(self):
        with pytest.raises(NextSMSValidationError, match="email"):
            self.client.deduct_customer(email="", smscount=500)

    def test_zero_smscount_raises(self):
        with pytest.raises(NextSMSValidationError, match="positive"):
            self.client.deduct_customer(email="customer@example.com", smscount=0)

    def test_negative_smscount_raises(self):
        with pytest.raises(NextSMSValidationError, match="positive"):
            self.client.deduct_customer(email="customer@example.com", smscount=-1)

    def test_no_api_call_on_validation_failure(self):
        with pytest.raises(NextSMSValidationError):
            self.client.deduct_customer(email="customer@example.com", smscount=0)
        self.client.http.request.assert_not_called()

"""
Tests for PhoneNumberValidator.
"""

import pytest
from nextsms.utils.validators import PhoneNumberValidator


class TestValidate:
    def test_valid_international_format(self):
        assert PhoneNumberValidator.validate("255712345678") is True

    def test_valid_local_format(self):
        assert PhoneNumberValidator.validate("0712345678") is True

    def test_invalid_short_number(self):
        assert PhoneNumberValidator.validate("123") is False

    def test_invalid_wrong_country_code(self):
        assert PhoneNumberValidator.validate("254712345678") is False

    def test_empty_string(self):
        assert PhoneNumberValidator.validate("") is False

    def test_none(self):
        assert PhoneNumberValidator.validate(None) is False  # type: ignore

    def test_with_spaces(self):
        assert PhoneNumberValidator.validate("255 712 345 678") is True

    def test_with_dashes(self):
        assert PhoneNumberValidator.validate("255-712-345-678") is True


class TestClean:
    def test_international_format_unchanged(self):
        assert PhoneNumberValidator.clean("255712345678") == "255712345678"

    def test_local_to_international(self):
        assert PhoneNumberValidator.clean("0712345678") == "255712345678"

    def test_strips_non_digits(self):
        assert PhoneNumberValidator.clean("+255 712 345 678") == "255712345678"

    def test_invalid_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid"):
            PhoneNumberValidator.clean("123")

    def test_empty_raises_value_error(self):
        with pytest.raises(ValueError, match="empty"):
            PhoneNumberValidator.clean("")


class TestValidateBatch:
    def test_mixed_batch(self):
        results = PhoneNumberValidator.validate_batch(["255712345678", "bad"])
        assert results[0] == ("255712345678", True)
        assert results[1] == ("bad", False)


class TestCleanBatch:
    def test_all_valid(self):
        result = PhoneNumberValidator.clean_batch(["0712345678", "255712345679"])
        assert result == ["255712345678", "255712345679"]

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            PhoneNumberValidator.clean_batch(["255712345678", "invalid"])

"""
Phone number validation utilities for Tanzanian numbers (255XXXXXXXXX format).
"""

import re
from typing import List, Tuple


class PhoneNumberValidator:
    """Validator for Tanzanian phone numbers — expected format: 255XXXXXXXXX"""

    COUNTRY_CODE = "255"
    VALID_LENGTH = 12  # 3 (country code) + 9 digits

    @classmethod
    def validate(cls, phone: str) -> bool:
        if not phone or not isinstance(phone, str):
            return False
        cleaned = re.sub(r"\D", "", phone)
        if cleaned.startswith("0") and len(cleaned) == 10:
            cleaned = cls.COUNTRY_CODE + cleaned[1:]
        return (
            len(cleaned) == cls.VALID_LENGTH
            and cleaned.startswith(cls.COUNTRY_CODE)
            and cleaned.isdigit()
        )

    @classmethod
    def clean(cls, phone: str) -> str:
        """Return phone in 255XXXXXXXXX format or raise ValueError."""
        if not phone:
            raise ValueError("Phone number cannot be empty")
        cleaned = re.sub(r"\D", "", phone)
        if cleaned.startswith("0") and len(cleaned) == 10:
            cleaned = cls.COUNTRY_CODE + cleaned[1:]
        if not cls.validate(cleaned):
            raise ValueError(
                f"Invalid Tanzanian phone number: '{phone}'. "
                f"Expected format: {cls.COUNTRY_CODE}XXXXXXXXX (12 digits)"
            )
        return cleaned

    @classmethod
    def validate_batch(cls, phones: List[str]) -> List[Tuple[str, bool]]:
        return [(p, cls.validate(p)) for p in phones]

    @classmethod
    def clean_batch(cls, phones: List[str]) -> List[str]:
        return [cls.clean(p) for p in phones]

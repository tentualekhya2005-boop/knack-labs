import pytest
from pydantic import ValidationError
from app.config import Settings


def test_valid_port():
    s = Settings(port=8000)
    assert s.port == 8000


def test_invalid_port_non_integer():
    with pytest.raises(ValidationError):
        Settings(port="not_a_number")


def test_invalid_port_boundary_low():
    with pytest.raises(ValidationError):
        Settings(port=0)


def test_invalid_port_boundary_high():
    with pytest.raises(ValidationError):
        Settings(port=70000)


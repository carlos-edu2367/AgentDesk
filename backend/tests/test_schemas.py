import pytest
from pydantic import ValidationError
from app.domain.schemas import ProviderCreate
from app.domain.enums import ProviderType

def test_schema_rejects_invalid_enum():
    with pytest.raises(ValidationError):
        ProviderCreate(
            type="invalid_provider", # type: ignore
            name="Test"
        )
        
    # Valid enum works
    p = ProviderCreate(type=ProviderType.OLLAMA, name="Test")
    assert p.type == ProviderType.OLLAMA

import pytest

from macro_engine.reference import load_reference


@pytest.fixture(scope="session")
def reference():
    return load_reference()

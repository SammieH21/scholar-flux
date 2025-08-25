import pytest
import importlib.util

@pytest.fixture
def redis_dependency():
    if importlib.util.find_spec('redis'):
        return True
    return False

@pytest.fixture
def mongodb_dependency():
    if importlib.util.find_spec('pymongo'):
        return True
    return False

@pytest.fixture
def sqlalchemy_dependency():
    if importlib.util.find_spec('sqlalchemy'):
        return True
    return False

import pytest
import importlib.util

@pytest.fixture
def redis_dependency():
    return bool(importlib.util.find_spec('redis'))

@pytest.fixture
def mongodb_dependency():
    return bool(importlib.util.find_spec('pymongo'))

@pytest.fixture
def sqlalchemy_dependency():
    return bool(importlib.util.find_spec('sqlalchemy'))

@pytest.fixture
def db_dependency_unavailable(redis_dependency, mongodb_dependency, sqlalchemy_dependency):
    def dependency_match(storage):
            match storage.lower():
                case 'sql' | 'sqlalchemy':
                    return not sqlalchemy_dependency
                case 'mongo' | 'mongodb' | 'pymongo':
                    return not mongodb_dependency
                case 'redis':
                    return not redis_dependency
                case _:
                    # for all other dependencies, return False if not explicitly defined
                    return False
    return dependency_match


@pytest.fixture
def session_encryption_dependency():
    return all(importlib.util.find_spec(pkg) for pkg in ['cryptography', 'itsdangerous'])

__all__ = ['redis_dependency', 'mongodb_dependency', 'sqlalchemy_dependency', 'db_dependency_unavailable']

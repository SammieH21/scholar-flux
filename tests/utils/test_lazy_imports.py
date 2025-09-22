import pytest

import scholar_flux.utils as utils


def test_lazy_import_provider_utils():
    """Testing whether ProviderUtils can be accessed by lazy importing"""
    ProviderUtils = utils.ProviderUtils
    assert ProviderUtils is not None
    # Optionally, check type or module
    assert ProviderUtils.__module__ == "scholar_flux.utils.provider_utils"
    assert "ProviderUtils" in dir(utils)


def test_lazy_import_caching():
    """The same object should be cached after a single import"""
    from scholar_flux.utils import ProviderUtils
    from scholar_flux.utils import ProviderUtils as ProviderUtils2

    assert ProviderUtils is ProviderUtils2


def test_nonexistent_import():
    with pytest.raises(ImportError):
        from scholar_flux.utils import ProvUtilities  # noqa: F401

    with pytest.raises(AttributeError):
        _ = getattr(utils, "ProvUtilities")

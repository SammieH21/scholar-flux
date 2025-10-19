import pytest

import scholar_flux.utils as utils


def test_lazy_import_provider_utils():
    """Testing whether ProviderUtils can be accessed by lazy importing.

    This utility was lazy loaded to account for issues with potential
    partial initialization of the `scholar_flux` module, and the method
    of lazy loading ensures that the module is only loaded when needed
    for when provider default configs re dynamically loaded at runtime.
    """
    ProviderUtils = utils.ProviderUtils
    assert ProviderUtils is not None
    # Optionally, check type or module
    assert ProviderUtils.__module__ == "scholar_flux.utils.provider_utils"
    assert "ProviderUtils" in dir(utils)


def test_lazy_import_caching():
    """Tests the `ProviderUtils` module to determine whether lazy loading the ProviderUtils module once more will load
    the same exact object, even if aliased."""
    from scholar_flux.utils import ProviderUtils
    from scholar_flux.utils import ProviderUtils as ProviderUtils2

    assert ProviderUtils is ProviderUtils2


def test_nonexistent_import():
    """Tests the behavior of the dynamically retrieved lazy imports when attempting to load a non-existent module.

    Validates whether attempting to load a non-existent `ProvUtilities`
    module will raise the expected AttributeError.
    """
    with pytest.raises(ImportError):
        from scholar_flux.utils import ProvUtilities  # noqa: F401

    with pytest.raises(AttributeError):
        _ = getattr(utils, "ProvUtilities")

import pytest
def test_import_scholar_flux():
    import scholar_flux
    assert hasattr(scholar_flux, '__version__')



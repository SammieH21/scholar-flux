def test_import_scholar_flux():
    """Verifies that the scholar-flux package can be imported without error."""
    import scholar_flux

    assert hasattr(scholar_flux, "__version__")

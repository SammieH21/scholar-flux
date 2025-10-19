# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
sys.path.insert(0, os.path.abspath('../../src'))

project = 'scholar-flux'
copyright = '2025, Sammie L. Haskin'
author = 'Sammie L. Haskin'
release = '0.1.0b.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',      # extracts docstrings
    'sphinx.ext.napoleon',     # Understands Google/NumPy style docstrings
    'sphinx.ext.viewcode',     # Adds [source] links to code
    'sphinx.ext.intersphinx',  # Links to Python docs, etc.
    'sphinx.ext.doctest',      # Add this!
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = 'alabaster'
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

html_css_files = [
    'custom.css',
]

suppress_warnings = [
    'ref.python',  # Suppress "more than one target found" warnings
    'toc.duplicate_entry', # suppress duplicate object warnings: convenience imports of objects into public modules
]

# prefer the original module for cross-references
autodoc_typehints_format = 'short'

autodoc_default_options = {
    'members': True,           # Document all members
    'undoc-members': False,     # Include only items with docstrings - note: all items should be documented in production
    'imported-members': False,  # Don't document imported members in submodules
    'private-members': False,
    'special-members': '__init__',
    'show-inheritance': True,  # Show parent classes
}


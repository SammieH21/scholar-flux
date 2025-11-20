# scholar_flux.api.normalization.pubmed_efetch_field_map.py
"""The scholar_flux.api.normalization.pubmed_efetch_field_map.py module defines Pubmed eFetch normalization mappings."""
from scholar_flux.api.normalization import AcademicFieldMap
from scholar_flux.api.normalization.pubmed_field_map import field_map


field_map = AcademicFieldMap.model_validate(field_map.model_dump() | {"provider_name": "pubmed_efetch"})

__all__ = ["field_map"]

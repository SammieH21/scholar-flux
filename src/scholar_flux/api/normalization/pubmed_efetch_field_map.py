# scholar_flux.api.normalization.pubmed_efetch_field_map.py
"""The scholar_flux.api.normalization.pubmed_efetch_field_map.py module defines PubMed eFetch normalization mappings."""
from scholar_flux.api.normalization.pubmed_field_map import PubMedFieldMap, field_map


field_map = PubMedFieldMap.model_validate(field_map.model_dump() | {"provider_name": "pubmed_efetch"})

__all__ = ["field_map"]

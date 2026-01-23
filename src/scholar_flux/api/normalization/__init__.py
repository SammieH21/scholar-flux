# api/normalization
"""The scholar_flux.api.normalization module implements API-specific record normalization for downstream analyses.

Because the range of fields retrieved after successful data processing can greatly vary based on API-specific semantics,
extensive post-processing is usually required to reliably extract insights from API-derived data.

To solve this issue, this module implements record normalization based on heuristics and provider-specific logic for
all default APIs while also supporting the application and extension of normalization logic to new APIs.

Classes:
    BaseFieldMap:
        Base class for mapping API-specific fields from non-nested dictionary records to common field names.
    NormalizingFieldMap:
        Extends the `BaseFieldMap`, adding support for nested field extraction with fallback resolution.
    AcademicFieldMap:
        Subclasses the `NormalizingFieldMap` to tailor its scope to academic field extraction and normalization.
        Implements several helpers to post-process fields such as DOI, authors, abstract, and publication metadata.
    ArXivFieldMap:
        `AcademicFieldMap` subclass implementing arXiv-specific normalization post-processing steps with PDF URL
        extraction, ISO date parsing, and record ID formatting.
    CoreFieldMap:
        Subclasses the `AcademicFieldMap` to implement CORE-specific normalization post-processing steps for full-text
        and repository metadata handling.
    CrossrefFieldMap:
        A Crossref-specific `AcademicFieldMap` subclass that implements normalization with author affiliation and
        reference parsing. The `abstract` post-processing step will remove HTML tags from abstracts if the
        `beautifulsoup4` optional dependency is available.
    OpenAlexFieldMap:
        Subclasses the `AcademicFieldMap` to implement OpenAlex-specific normalization post-processing steps for
        institution and concept extraction. Post-processing also reconstructs abstracts using abstract-inverted indexes
        when available.
    PLOSFieldMap:
        An `AcademicFieldMap` subclass that implements PLOS-specific normalization post-processing steps involving URL
        reconstruction, date extraction, and abstract cleanup.
    PubMedFieldMap:
        PubMed-specific `AcademicFieldMap` subclass that implements normalization post-processing steps, including MeSH
        term extraction, author list formatting, the reconstruction of PubMed URLs from PubMed IDs, etc.
    SpringerNatureFieldMap:
        Subclasses the `AcademicFieldMap` to define Springer Nature-specific normalization post-processing steps to
        extract the publication date, author list, open access status, and primary URL for each record.

"""


from scholar_flux.api.normalization.base_field_map import BaseFieldMap
from scholar_flux.api.normalization.normalizing_field_map import NormalizingFieldMap
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap
from scholar_flux.api.normalization.arxiv_field_map import ArXivFieldMap
from scholar_flux.api.normalization.core_field_map import CoreFieldMap
from scholar_flux.api.normalization.crossref_field_map import CrossrefFieldMap
from scholar_flux.api.normalization.open_alex_field_map import OpenAlexFieldMap
from scholar_flux.api.normalization.plos_field_map import PLOSFieldMap
from scholar_flux.api.normalization.pubmed_field_map import PubMedFieldMap
from scholar_flux.api.normalization.springer_nature_field_map import SpringerNatureFieldMap


__all__ = [
    "BaseFieldMap",
    "NormalizingFieldMap",
    "AcademicFieldMap",
    "ArXivFieldMap",
    "CoreFieldMap",
    "CrossrefFieldMap",
    "OpenAlexFieldMap",
    "PLOSFieldMap",
    "PubMedFieldMap",
    "SpringerNatureFieldMap",
]

# api/normalization
"""The scholar_flux.api.normalization module implements API-specific record normalization for downstream analyses.

Because the range of fields retrieved after successful data processing can greatly vary based on API-specific semantics,
extensive post-processing is usually required to successfully retrieve insights from API-derived data.

To solve this issue, this module implements optional record normalization based on heuristics specific to supported APIs
while also supporting the application of processed response record normalization to new APIs.

"""


from scholar_flux.api.normalization.base_field_map import BaseFieldMap
from scholar_flux.api.normalization.normalizing_field_map import NormalizingFieldMap
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap


__all__ = ["BaseFieldMap", "NormalizingFieldMap", "AcademicFieldMap"]

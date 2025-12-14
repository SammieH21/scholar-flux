"""Tests for API-specific parameter validators across all ScholarFlux providers.

Coverage:
    Core Validators: validate_str, validate_int, validate_date, validate_and_process_email
    Wrapper: validate_api_specific_field, api_validator decorator

    Provider Integration:
        arXiv         - sortBy, sortOrder (constrained choices)
        Crossref      - mailto, sort, order
        Springer      - sort, datefrom, dateto (date validation)
        PLOS          - sort, fq
        CORE          - sort, entityType
        PubMed        - db, sort, mindate, maxdate
        PubMed eFetch - db, cmd, query_key
        OpenAlex      - mailto, sort, filter

"""

from functools import partial

import pytest

from scholar_flux.api.providers import provider_registry
from pydantic import SecretStr
from scholar_flux.utils import config_settings
from typing import Callable
from scholar_flux.api.validators import (
    api_validator,
    validate_and_process_email,
    validate_api_specific_field,
    validate_date,
    validate_int,
    validate_str,
)


# =============================================================================
# UNIT TESTS: Core Validators
# =============================================================================


class TestValidateStr:
    """Tests for string validation."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("test", "test"),
            ("publication_date desc", "publication_date desc"),
            ("  spaced  ", "  spaced  "),  # whitespace preserved
            ("", ""),  # empty string allowed
            (None, None),  # None passthrough
        ],
    )
    def test_valid_inputs(self, value, expected):
        """Accepts strings, empty strings, and None."""
        assert validate_str(value) == expected

    @pytest.mark.parametrize("invalid", [123, ["list"], {"dict": 1}])
    def test_non_string_raises(self, invalid):
        """Rejects non-string types."""
        with pytest.raises(ValueError, match="Expected str"):
            validate_str(invalid)

    def test_allowed_values_constraint(self):
        """Enforces allowed values when specified."""
        assert validate_str("asc", allowed=["asc", "desc"]) == "asc"
        assert validate_str("desc", allowed=["asc", "desc"]) == "desc"

        with pytest.raises(ValueError, match="not in allowed"):
            validate_str("invalid", allowed=["asc", "desc"])


class TestValidateInt:
    """Tests for integer validation."""

    @pytest.mark.parametrize(
        "value,min_,max_",
        [
            (23, None, None),
            (23, 1, None),
            (23, 1, 24),
            (23, None, 25),
        ],
    )
    def test_valid_ranges(self, value, min_, max_):
        """Accepts integers within optional bounds."""
        assert validate_int(value, min=min_, max=max_) == value

    def test_none_passthrough(self):
        """None returns None."""
        assert validate_int(None) is None

    def test_non_integer_raises(self):
        """Rejects non-integer types."""
        with pytest.raises(ValueError, match="Expected int"):
            validate_int("non-integer", min=1, max=2)  # type: ignore

    def test_below_minimum_raises(self):
        """Rejects values below minimum."""
        with pytest.raises(ValueError, match="less than minimum"):
            validate_int(50, min=51)

    def test_above_maximum_raises(self):
        """Rejects values above maximum."""
        with pytest.raises(ValueError, match="greater than maximum"):
            validate_int(50, max=49)


class TestValidateDate:
    """Tests for date validation."""

    @pytest.mark.parametrize(
        "date",
        [
            "2023-01-15",
            "2024-12-31",
            "2020-02-29",  # leap year
        ],
    )
    def test_valid_iso_dates(self, date):
        """Accepts valid YYYY-MM-DD dates."""
        assert validate_date(date) == date

    def test_none_passthrough(self):
        """None returns None."""
        assert validate_date(None) is None

    @pytest.mark.parametrize(
        "invalid",
        [
            "01-15-2023",  # wrong order
            "2023/01/15",  # wrong separator
            "Jan 15, 2023",  # text format
        ],
    )
    def test_wrong_format_raises(self, invalid):
        """Rejects wrong date formats."""
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            validate_date(invalid)

    @pytest.mark.parametrize("invalid", ["2023-02-30", "2023-13-01"])
    def test_invalid_calendar_date_raises(self, invalid):
        """Rejects impossible calendar dates."""
        with pytest.raises(ValueError):
            validate_date(invalid)

    @pytest.mark.parametrize("invalid", [20230115, ["2023-01-15"]])
    def test_non_string_raises(self, invalid):
        """Rejects non-string input."""
        with pytest.raises(ValueError, match="Expected str"):
            validate_date(invalid)

    @pytest.mark.parametrize(
        "date,fmt,desc",
        [
            ("2023/01/15", "%Y/%m/%d", "YYYY/MM/DD"),  # PubMed style
            ("2023", "%Y", "YYYY"),  # year only
        ],
    )
    def test_custom_formats(self, date, fmt, desc):
        """Supports custom date formats."""
        assert validate_date(date, format=fmt, format_description=desc) == date


class TestValidateEmail:
    """Tests for email validation."""

    def test_valid_email(self):
        """Accepts valid email addresses."""
        result = validate_and_process_email("user@example.com")
        assert result is not None

    def test_none_passthrough(self):
        """None returns None."""
        assert validate_and_process_email(None) is None

    def test_invalid_email_raises(self):
        """Rejects invalid email formats."""
        with pytest.raises(ValueError):
            validate_and_process_email("not-an-email")

    def test_invalid_env_email_raises(self, monkeypatch):
        """Rejects invalid email formats from the environment and warns the users of the issue."""
        invalid_env_email = "not a valid email"
        invalid_email = "another invalid email"

        with monkeypatch.context():
            monkeypatch.setenv("SCHOLAR_FLUX_DEFAULT_MAILTO", invalid_env_email)
            env_email_from_config = config_settings.get("SCHOLAR_FLUX_DEFAULT_MAILTO")

            err = (
                "The environment variable, SCHOLAR_FLUX_DEFAULT_MAILTO contains an invalid email: "
                f"'{env_email_from_config}'. Provide a valid email or unset the environment variable."
            )

            with pytest.raises(ValueError, match=err):
                validate_and_process_email(None)

            with pytest.raises(ValueError, match=f"The provided email is invalid, received {invalid_email}"):
                validate_and_process_email(invalid_email)

    @pytest.mark.parametrize("env_email", ("not a valid email", "a.relatively.valid@email.com"))
    def test_valid_email_overrides_env(self, env_email, monkeypatch):
        """Verifies that `validate_and_process_email` prefers explicitly specified emails over environment variables."""
        valid_email = "a.valid@yet.fake.email.com"

        with monkeypatch.context():
            monkeypatch.setenv("SCHOLAR_FLUX_DEFAULT_MAILTO", env_email)
            assert validate_and_process_email(valid_email) == SecretStr(valid_email)


# =============================================================================
# UNIT TESTS: API-Specific Field Wrapper
# =============================================================================


class TestApiSpecificFieldWrapper:
    """Tests for validate_api_specific_field context wrapper."""

    def test_passthrough_on_valid_input(self):
        """Valid input passes through unchanged."""
        wrapped = validate_api_specific_field(validate_str, provider_name="test_provider", field="test_field")
        assert wrapped("valid") == "valid"

    def test_error_includes_provider_and_field(self):
        """Errors include provider and field context."""
        wrapped = validate_api_specific_field(
            partial(validate_str, allowed=["a", "b"]),
            provider_name="crossref",
            field="order",
        )
        with pytest.raises(ValueError) as exc_info:
            wrapped("invalid")

        assert "crossref" in str(exc_info.value)
        assert "order" in str(exc_info.value)

    def test_decorator_form(self):
        """api_validator decorator wraps with context."""

        @api_validator(provider_name="test_provider", field="test_date")
        def api_date_validator(value):
            return validate_date(value)

        assert api_date_validator("2023-03-23") == "2023-03-23"

        with pytest.raises(
            ValueError, match=".*Validation failed for parameter 'test_date' in provider 'test_provider'.*"
        ):
            api_date_validator("not-a-date")

    def test_non_callable_raises(self):
        """Non-callable validator raises TypeError."""
        with pytest.raises(TypeError, match="Expected callable"):
            validate_api_specific_field("not_a_function", "provider", "field")  # type: ignore


# =============================================================================
# INTEGRATION TESTS: Provider-Configured Validators
# =============================================================================


class TestProviderValidators:
    """Integration tests using actual provider configurations.

    Tests validators as configured in each provider module to ensure the full validation chain works correctly.

    """

    # -------------------------------------------------------------------------
    # arXiv: sortBy (constrained), sortOrder (constrained)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("value", ["relevance", "lastUpdatedDate", "submittedDate"])
    def test_arxiv_sortby_valid(self, value):
        """arXiv sortBy accepts valid sort fields."""
        validator = self._get_validator("arXiv", "sortBy")
        assert validator(value) == value

    @pytest.mark.parametrize("value", ["ascending", "descending"])
    def test_arxiv_sortorder_valid(self, value):
        """arXiv sortOrder accepts valid directions."""
        validator = self._get_validator("arXiv", "sortOrder")
        assert validator(value) == value

    # -------------------------------------------------------------------------
    # Crossref: mailto (email), sort (str), order (str)
    # -------------------------------------------------------------------------

    def test_crossref_mailto_valid(self):
        """Crossref mailto validates email format."""
        validator = self._get_validator("crossref", "mailto")
        assert validator("user@example.com") is not None

    def test_crossref_mailto_invalid(self):
        """Crossref mailto rejects invalid email."""
        validator = self._get_validator("crossref", "mailto")
        with pytest.raises(ValueError, match=".*Validation failed for parameter 'mailto' in provider 'crossref'.*"):
            validator("not-an-email")  # type: ignore

    @pytest.mark.parametrize(
        "field,values",
        [
            ("sort", ["published", "is-referenced-by-count"]),
            ("order", ["asc", "desc"]),
        ],
    )
    def test_crossref_string_params(self, field, values):
        """Crossref sort/order accept strings."""
        validator = self._get_validator("crossref", field)
        for value in values:
            assert validator(value) == value

    # -------------------------------------------------------------------------
    # Springer Nature: sort (str), datefrom/dateto (date)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("value", ["date", "relevance:desc"])
    def test_springer_sort_valid(self, value):
        """Springer sort accepts strings."""
        validator = self._get_validator("springernature", "sort")
        assert validator(value) == value

    @pytest.mark.parametrize(
        "field,date",
        [
            ("datefrom", "2023-01-01"),
            ("dateto", "2024-12-31"),
        ],
    )
    def test_springer_dates_valid(self, field, date):
        """Springer date fields validate YYYY-MM-DD format."""
        validator = self._get_validator("springernature", field)
        assert validator(date) == date

    def test_springer_date_invalid(self):
        """Springer date fields reject invalid formats."""
        validator = self._get_validator("springernature", "datefrom")
        with pytest.raises(
            ValueError, match=".*Validation failed for parameter 'datefrom' in provider 'springernature'.*"
        ):
            validator("01/01/2023")  # type: ignore

    # -------------------------------------------------------------------------
    # PLOS: sort (str)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("value", ["publication_date desc", "score desc"])
    def test_plos_sort_valid(self, value):
        """PLOS sort accepts strings."""
        validator = self._get_validator("plos", "sort")
        assert validator(value) == value

    # -------------------------------------------------------------------------
    # PLOS: fq (str)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("value", ["journal:PLoS ONE", "article_type:Research Article"])
    def test_plos_fq_valid(self, value):
        """PLOS fq (filter query) accepts strings."""
        validator = self._get_validator("plos", "fq")
        assert validator(value) == value

    # -------------------------------------------------------------------------
    # CORE: sort (str)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("value", ["publishedDate:desc", "citationCount:desc"])
    def test_core_sort_valid(self, value):
        """CORE sort accepts strings."""
        validator = self._get_validator("core", "sort")
        assert validator(value) == value

    # -------------------------------------------------------------------------
    # CORE: entityType (str)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("value", ["works", "journal"])
    def test_core_entityType_valid(self, value):
        """CORE sort accepts strings."""
        validator = self._get_validator("core", "entityType")
        assert validator(value) == value

    # -------------------------------------------------------------------------
    # PubMed: db (str), sort (str), mindate/maxdate (flexible str)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "field,values",
        [
            ("db", ["pubmed", "pmc"]),
            ("sort", ["relevance", "pub_date"]),
        ],
    )
    def test_pubmed_string_params(self, field, values):
        """PubMed string parameters accept valid inputs."""
        validator = self._get_validator("pubmed", field)
        for value in values:
            assert validator(value) == value

    @pytest.mark.parametrize(
        "field,values",
        [
            ("mindate", ["2023/01/01", "2023/01", "2023"]),
            ("maxdate", ["2024/12/31"]),
        ],
    )
    def test_pubmed_dates_flexible(self, field, values):
        """PubMed date params accept flexible formats (API validates)."""
        validator = self._get_validator("pubmed", field)
        for value in values:
            assert validator(value) == value

    # -------------------------------------------------------------------------
    # OpenAlex: mailto (email), sort (str), filter (str)
    # -------------------------------------------------------------------------

    def test_openalex_mailto_valid(self):
        """OpenAlex mailto validates email format."""
        validator = self._get_validator("openalex", "mailto")
        assert validator("researcher@university.edu") is not None

    def test_openalex_mailto_invalid(self):
        """OpenAlex mailto rejects invalid email."""
        validator = self._get_validator("openalex", "mailto")
        with pytest.raises(ValueError, match=".*Validation failed for parameter 'mailto' in provider 'openalex'.*"):
            validator("invalid")  # type: ignore

    @pytest.mark.parametrize(
        "field,values",
        [
            ("sort", ["cited_by_count:desc", "publication_date:desc"]),
            ("filter", ["publication_year:2024", "is_oa:true,cited_by_count:>100"]),
        ],
    )
    def test_openalex_string_params(self, field, values):
        """OpenAlex sort/filter accept strings."""
        validator = self._get_validator("openalex", field)
        for value in values:
            assert validator(value) == value

    # -------------------------------------------------------------------------
    # PubMed eFetch: db (str), cmd (str), query_key (str)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "field,values",
        [
            ("db", ["pubmed", "pmc", "nucleotide"]),
            ("cmd", ["neighbor_history", "neighbor_score"]),
            ("query_key", ["1", "2"]),
        ],
    )
    def test_pubmed_efetch_string_params(self, field, values):
        """PubMed eFetch string parameters accept valid inputs."""
        validator = self._get_validator("pubmed_efetch", field)
        for value in values:
            assert validator(value) == value

    # -------------------------------------------------------------------------
    # None passthrough (all providers)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "provider,field",
        [
            ("openalex", "sort"),
            ("openalex", "filter"),
            ("openalex", "mailto"),
            ("crossref", "sort"),
            ("crossref", "mailto"),
            ("springernature", "datefrom"),
            ("plos", "fq"),
            ("core", "entityType"),
            ("pubmed_efetch", "db"),
            ("pubmed_efetch", "cmd"),
            ("pubmed_efetch", "query_key"),
        ],
    )
    def test_none_passthrough(self, provider, field):
        """All validators pass None through."""
        validator = self._get_validator(provider, field)
        assert validator(None) is None

    # -------------------------------------------------------------------------
    # Helper
    # -------------------------------------------------------------------------

    def _get_validator(self, provider: str, field: str) -> Callable:
        """Get a validator from provider config."""
        config = provider_registry[provider]
        param = config.parameter_map.api_specific_parameters[field]
        if not param.validator:
            raise ValueError(f"Provider {provider} doesn't have a validator for the field {field}..")
        return param.validator

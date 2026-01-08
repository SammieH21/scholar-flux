# scholar_flux.api.normalization.pubmed_field_map.py
"""The scholar_flux.api.normalization.pubmed_field_map.py module defines the normalization mappings used for PubMed."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap
from scholar_flux.utils.record_types import NormalizedRecordType
from scholar_flux.utils.helpers import (
    get_nested_data,
    unlist_1d,
    as_tuple,
)
from typing import Optional


class PubMedFieldMap(AcademicFieldMap):
    """PubMed specific field mapping with custom transformations.

    The `PubMedFieldMap` builds on the original `AcademicFieldMap` to add a minimal PubMed-specific array of
    post-processing steps that produces final, consistent, normalized record structures across several record types.

    Post-Processed Fields:
        -  `PMCID`, 'PMID', and 'PII' identifiers
        - The date and year of creation or publication
        - The base URL for the record
        - Authors (After formatting nested authorship fields)
        - The DOI for the record
        - Open Access status
        - Abstract Retrieval

    Note:
        PubMed's XML structure varies between Articles and BookDocuments, which is handled via
        fallback paths in the field_map configuration (e.g., multiple paths for 'year' and 'abstract').

        Article identifiers (DOI, PMCID, PII) are extracted from the ArticleIdList by filtering on
        the '@IdType' attribute, with additional fallback logic for DOI via ELocationID.

        Open access status is determined by the presence of a PMCID, indicating the article is
        available in PubMed Central.

    """

    def _post_process(self, record: NormalizedRecordType) -> NormalizedRecordType:
        """Applies PubMed-specific transformations to an individual normalized record.

        Args:
            record (NormalizedRecordType): The Normalized PubMed record dictionary further process.

        Returns:
            NormalizedRecordType: The normalized, post-processed PubMed record with transformations applied

        """
        record = super()._post_process(record)
        # Extract year from date strings if present
        record["year"] = self.extract_year(record)

        # Reconstruct URL from PMID if PMID exists
        record["url"] = self.reconstruct_pubmed_url(record)

        record["doi"] = self.extract_doi(record)

        # Extract and override PMCID (filters by IdType='pmc')
        pmcid = self.extract_pmcid(record)
        record["pmcid"] = pmcid  # Override generic extraction, can be None

        # Extract and override PII (filters by IdType='pii')
        pii = self.extract_pii(record)
        record["pii"] = pii  # Override generic extraction, can be None

        # Extract formatted author names (overrides basic LastName extraction)
        record["authors"] = self.extract_authors(record)

        # Extract formatted publication date
        record["date_published"] = self.extract_iso_date(record, "date_published")

        # Extract formatted creation date
        record["date_created"] = self.extract_date_created(record)

        # Extract open access status based on PMC ID presence
        record["open_access"] = self.extract_open_access(record)

        record["abstract"] = self.extract_abstract(record)

        return record

    @classmethod
    def _extract_article_id(
        cls,
        record: NormalizedRecordType,
        id_type: str,
        strip_prefix: str = "",
    ) -> Optional[str]:
        """Extracts the article identifier from `ArticleIdList` by the `IdType` attribute.

        This is a helper for extracting DOI, PMCID, PII, and other identifiers
        from PubMed's ArticleIdList structure, which contains multiple identifier types
        distinguished by the '@IdType' attribute.

        Args:
            record (NormalizedRecordType): Normalized record with 'article_id_list' already extracted
            id_type (str): The IdType to filter for (e.g., 'doi', 'pmc', 'pii')
            strip_prefix (str): An optional prefix to remove from the identifier (e.g., 'PMC' for PMC IDs)

        Returns:
            Optional[str]: Extracted identifier string, or None if not found or results in empty string

        Examples:
            >>> from scholar_flux.api.normalization.pubmed_field_map import PubMedFieldMap
            >>> record = {'article_id_list': {'ArticleId': [{'@IdType': 'pmc', '#text': 'PMC123456'}]}}
            >>> PubMedFieldMap._extract_article_id(record, 'pmc', strip_prefix='PMC')
            # OUTPUT: '123456'
            >>> PubMedFieldMap._extract_article_id(record, 'doi')
            # OUTPUT: None

        """
        article_ids = as_tuple(get_nested_data(record, "article_id_list.ArticleId", verbose=False))

        for article_id in article_ids:
            if isinstance(article_id, dict) and article_id.get("@IdType") == id_type:
                value = unlist_1d(article_id.get("#text"))
                if isinstance(value, str) and strip_prefix:
                    value = value.replace(strip_prefix, "")
                # Return None if stripping results in empty string
                return value if value else None

        return None

    @classmethod
    def extract_doi(cls, record: NormalizedRecordType) -> Optional[str]:
        """Extracts the DOI from the ArticleIdList based on the IdType attribute.

        Attempts to extract DOI from two sources:
        1. ArticleIdList with IdType='doi' (primary)
        2. ELocationID with EIdType='doi' (fallback)

        Args:
            record (NormalizedRecordType): Normalized record with 'article_id_list' and 'elocation_id' already extracted

        Returns:
            Optional[str]: DOI string or None if not found

        """
        # Primary: Check PubmedData.ArticleIdList.ArticleId
        if doi := cls._extract_article_id(record, "doi"):
            return doi

        # Fallback: Check MedlineCitation.Article.ELocationID
        elocation_ids = as_tuple(get_nested_data(record, "elocation_id", verbose=False))
        for elocation_id in elocation_ids:
            if isinstance(elocation_id, dict) and elocation_id.get("@EIdType") == "doi":
                return unlist_1d(elocation_id.get("#text"))

        return None

    @classmethod
    def extract_pmcid(cls, record: NormalizedRecordType) -> Optional[str]:
        """Extracts the PMC ID for full-text access from the normalized record.

        Returns the PMCID without the 'PMC' prefix for consistency. Handles edge cases
        where stripping the prefix results in an empty string.

        Args:
            record (NormalizedRecordType): Normalized record with 'article_id_list' already extracted

        Returns:
            Optional[str]: PMC ID without 'PMC' prefix, or None if not found or invalid

        Examples:
            >>> from scholar_flux.api.normalization.pubmed_field_map import PubMedFieldMap
            >>> record = {'article_id_list': {'ArticleId': [{'@IdType': 'pmc', '#text': 'PMC123456'}]}}
            >>> PubMedFieldMap.extract_pmcid(record)
            # OUTPUT: '123456'

        """
        return cls._extract_article_id(record, "pmc", strip_prefix="PMC")

    @classmethod
    def extract_pii(cls, record: NormalizedRecordType) -> Optional[str]:
        """Extracts the Publisher Item Identifier (PII) from the ArticleIdList.

        Args:
            record (NormalizedRecordType): Normalized record with 'article_id_list' already extracted

        Returns:
            Optional[str]: PII string or None if not found

        """
        return PubMedFieldMap._extract_article_id(record, "pii")

    @classmethod
    def extract_open_access(cls, record: NormalizedRecordType) -> Optional[bool]:
        """Determines if an article is open access based on PMC ID presence.

        The presence of a PMCID indicates the article is available in PubMed Central, which means it is accessible as
        open access. This is a reliable indicator for PubMed records, though it may not capture all open access
        articles (e.g., those available only on publisher websites).

        Args:
            record (NormalizedRecordType): Normalized record with 'article_id_list' already extracted

        Returns:
            Optional[bool]: True if PMCID present (open access), False if no PMCID, None if indeterminate

        Examples:
            >>> from scholar_flux.api.normalization.pubmed_field_map import PubMedFieldMap
            >>> record = {'article_id_list': {'ArticleId': [{'@IdType': 'pmc', '#text': 'PMC123456'}]}}
            >>> PubMedFieldMap.extract_open_access(record)
            # OUTPUT: True
            >>> record = {'article_id_list': {'ArticleId': [{'@IdType': 'doi', '#text': '10.1234/example'}]}}
            >>> PubMedFieldMap.extract_open_access(record)
            # OUTPUT: False

        """
        # Check if article_id_list is present in the record
        if get_nested_data(record, "article_id_list.ArticleId", verbose=False) is None:
            return None
        # Return True if PMCID exists, False if article_id_list exists but no PMCID, None otherwise
        return bool(PubMedFieldMap.extract_pmcid(record))

    @classmethod
    def extract_authors(cls, record: NormalizedRecordType, field: str = "authors") -> Optional[list[str]]:
        """Extract formatted author names combining ForeName and LastName.

        Args:
            record (NormalizedRecordType): Raw PubMed record dictionary
            field (str): The location to extract the nested list of authors from.

        Returns:
            Optional[list[str]]: List of author names in 'ForeName LastName' format, or None if no authors

        Notes:
            For an author with LastName='Smith', ForeName='John':
            Returns ['John Smith']

            For an author with only LastName='Smith':
            Returns ['Smith']

        """
        authors = as_tuple(record.get(field))
        formatted_authors = [
            (
                f"{given} {author['LastName']}"
                if (given := author.get("ForeName", author.get("Initials", "")))
                else f"{author['LastName']}"
            )
            for author in authors
            if isinstance(author, dict) and author.get("LastName")
        ]

        return formatted_authors or None

    @classmethod
    def extract_date_created(cls, record: NormalizedRecordType) -> Optional[str]:
        """Extract date created or article date.

        Args:
            record (NormalizedRecordType): Raw PubMed record dictionary

        Returns:
            Optional[str]: ISO formatted date string (YYYY-MM-DD) or None

        Notes:
            Tries date created (MedlineCitation.DateCompleted) first, then falls back to article_date
            (ArticleDate.DateCompleted)

        """
        if date_created := cls.extract_iso_date(record, "date_created"):
            return date_created
        return cls.extract_iso_date(record, "article_date")

    @classmethod
    def reconstruct_pubmed_url(cls, record: NormalizedRecordType) -> Optional[str]:
        """Reconstruct PubMed article URL from the PMID.

        Args:
            record (NormalizedRecordType): The record containing the 'pmid' field

        Returns:
            A Reconstructed URL if PMID is valid, None otherwise.

        Examples:
            >>> from scholar_flux.api.normalization.pubmed_field_map import PubMedFieldMap
            >>> PubMedFieldMap.reconstruct_pubmed_url({"pmid": "41418093"})
            # OUTPUT: 'https://pubmed.ncbi.nlm.nih.gov/41418093/'
            >>> PubMedFieldMap.reconstruct_pubmed_url({"pmid": None})
            # OUTPUT: None

        """
        url = cls.reconstruct_url(record.get("pmid"), url="https://pubmed.ncbi.nlm.nih.gov/{}/")
        return url or None


field_map = PubMedFieldMap(
    provider_name="pubmed",
    # Identifiers
    doi=None,  # Extracted from the ArticleIDList or ElocationID where @IdType = doi
    url=None,  # is reconstructed from PMID
    record_id=["MedlineCitation.PMID.#text", "BookDocument.PMID.#text"],
    # Bibliographic
    title=["MedlineCitation.Article.ArticleTitle.#text", "MedlineCitation.Article.ArticleTitle"],
    abstract=[
        "MedlineCitation.Article.Abstract.AbstractText.#text",
        "MedlineCitation.Article.Abstract.AbstractText",
        "BookDocument.Abstract.AbstractText.#text",
    ],
    # Intermediates Dictionary
    authors=[
        "MedlineCitation.Article.AuthorList.Author",
        "BookDocument.AuthorList.Author",
    ],  # Auto-traverses Author list
    # Publication metadata
    journal="MedlineCitation.Article.Journal.Title",
    publisher=None,  # Not typically in PubMed
    year=[
        "MedlineCitation.Article.Journal.JournalIssue.PubDate.Year",
        "BookDocument.Book.PubDate.Year",
        "MedlineCitation.Article.ArticleDate.Year",
        "MedlineCitation.DateCompleted.Year",
        "MedlineCitation.DateRevised.Year",
    ],
    date_published=[
        "MedlineCitation.Article.Journal.JournalIssue.PubDate",
        "BookDocument.Book.PubDate",
    ],
    date_created="MedlineCitation.DateCompleted",
    # Content
    keywords=[
        "MedlineCitation.KeywordList.Keyword.#text",
        "MedlineCitation.KeywordList.Keyword",
    ],  # Auto-traverses Keyword list
    subjects="MedlineCitation.MeshHeadingList.MeshHeading.DescriptorName.#text",  # MeSH terms!
    full_text=None,
    # Metrics
    citation_count=None,
    # Access
    open_access=None,  # Extracted via PMCID presence in _post_process
    license="MedlineCitation.Article.Abstract.CopyrightInformation",
    # Metadata
    record_type="MedlineCitation.Article.PublicationTypeList.PublicationType.#text",
    language="MedlineCitation.Article.Language",
    # API-specific fields
    api_specific_fields={
        "article_date": "MedlineCitation.Article.ArticleDate",
        "article_id_list": "PubmedData.ArticleIdList",
        "elocation_id": "MedlineCitation.Article.ELocationID",
        "pmid": ["MedlineCitation.PMID.#text", "BookDocument.PMID.#text"],
        "pmcid": "PubmedData.ArticleIdList.ArticleId.#text",
        "pii": "PubmedData.ArticleIdList.ArticleId.#text",
        # MeSH terms with qualifiers
        "mesh_terms": "MedlineCitation.MeshHeadingList.MeshHeading.DescriptorName.#text",
        "mesh_qualifiers": "MedlineCitation.MeshHeadingList.MeshHeading.QualifierName.#text",
        "mesh_ui": "MedlineCitation.MeshHeadingList.MeshHeading.DescriptorName.@UI",
        # Journal details
        "issn": "MedlineCitation.Article.Journal.ISSN.#text",
        "iso_abbreviation": "MedlineCitation.Article.Journal.ISOAbbreviation",
        "volume": "MedlineCitation.Article.Journal.JournalIssue.Volume",
        "issue": "MedlineCitation.Article.Journal.JournalIssue.Issue",
        "pages": "MedlineCitation.Article.Pagination.MedlinePgn",
        "start_page": "MedlineCitation.Article.Pagination.StartPage",
        "end_page": "MedlineCitation.Article.Pagination.EndPage",
    },
)

__all__ = ["PubMedFieldMap", "field_map"]

# scholar_flux.api.normalization.pubmed_field_map.py
"""The scholar_flux.api.normalization.pubmed_field_map.py module defines the normalization mappings used for Pubmed."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap


field_map = AcademicFieldMap(
    provider_name="pubmed",
    # Identifiers
    doi="MedlineCitation.Article.ELocationID.#text",  # Note: May need filtering where @EIdType="doi"
    url=None,  # Construct from PMID if needed
    record_id="MedlineCitation.PMID.#text",
    # Bibliographic
    title=["MedlineCitation.Article.ArticleTitle.#text", "MedlineCitation.Article.ArticleTitle"],
    abstract=["MedlineCitation.Article.Abstract.AbstractText.#text", "MedlineCitation.Article.Abstract.AbstractText"],
    authors="MedlineCitation.Article.AuthorList.Author.LastName",  # Auto-traverses Author list
    # Publication metadata
    journal="MedlineCitation.Article.Journal.Title",
    publisher=None,  # Not typically in PubMed
    year="MedlineCitation.Article.Journal.JournalIssue.PubDate.Year",
    date_published="MedlineCitation.Article.Journal.JournalIssue.PubDate.Year",  # Could combine Year/Month/Day
    date_created="MedlineCitation.DateCompleted.Year",  # Or use ArticleDate
    # Content
    keywords="MedlineCitation.KeywordList.Keyword.#text",  # Auto-traverses Keyword list
    subjects="MedlineCitation.MeshHeadingList.MeshHeading.DescriptorName.#text",  # MeSH terms!
    full_text=None,
    # Metrics
    citation_count=None,
    # Access
    open_access=None,  # Check for PMC ID in ArticleIdList
    license="MedlineCitation.Article.Abstract.CopyrightInformation",
    # Metadata
    record_type="MedlineCitation.Article.PublicationTypeList.PublicationType.#text",
    language="MedlineCitation.Article.Language",
    # API-specific fields
    api_specific_fields={
        "pmid": "MedlineCitation.PMID.#text",
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

__all__ = ["field_map"]

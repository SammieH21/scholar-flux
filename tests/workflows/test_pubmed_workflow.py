from scholar_flux.api.workflows import PubMedSearchStep, PubMedFetchStep, SearchWorkflow, WorkflowResult, StepContext
from scholar_flux.api import (
    SearchAPI,
    SearchCoordinator,
    ProcessedResponse,
    ErrorResponse,
    NonResponse,
    ReconstructedResponse,
)
from scholar_flux.exceptions import XMLToDictImportError, NoRecordsAvailableException
from requests import Response
from unittest.mock import MagicMock
import requests_mock
import pytest
import uuid
from scholar_flux.utils import config_settings


@pytest.fixture(autouse=True)
def mock_pubmed_api_key():
    """Registers a mock API key for tests involving the creation of new SearchCoordinators for the PubMed API."""
    config_settings.set("PUBMED_API_KEY", str(uuid.uuid4()))
    yield


def test_pubmed_workflow_context_without_records():
    """Validates whether the use of a pubmed workflow with missing IDs will correctly be flagged.

    When a received response is valid and contains a valid formatted metadata field, the metadata dictionary will
    contain {'IdList':{'Id': [...]} ...}. If unavailable, a type error should be raised.

    """
    response = Response()
    response.status_code = 200

    metadata = MagicMock(spec=dict)
    metadata.result = {}

    search_step = PubMedSearchStep()
    fetch_step = PubMedFetchStep()
    ctx = StepContext(step_number=1, step=search_step, result=ProcessedResponse(response=response, metadata=metadata))

    with pytest.raises(NoRecordsAvailableException) as excinfo:
        _ = fetch_step.pre_transform(ctx)

    assert "The metadata from the PubMed eSearch step returned no record IDs." in str(excinfo.value)


def test_successful_pubmed_workflow_search_without_records(monkeypatch, caplog):
    """Verifies that the original eSearch response returned when the previous step is successful but contains no
    records."""
    coordinator = SearchCoordinator(provider_name="pubmed", query="Cardiovascular Endurance")
    prepared_search = coordinator.api.prepare_search(page=1)
    processed_response = ProcessedResponse(
        response=ReconstructedResponse.build(
            url=prepared_search.url, status_code=200, json={"status": "ok", "data": []}
        ),
        metadata={},
        processed_records=None,
    )
    monkeypatch.setattr(coordinator, "_search", lambda *args, **kwargs: processed_response)

    with requests_mock.Mocker() as _:
        mock_response = coordinator.search(page=1, use_workflow=True)
        assert processed_response is mock_response
    assert (
        "The metadata from the PubMed eSearch step returned no record IDs. Halting the PubMed eFetch step and returning the processed eSearch response..."
        in caplog.text
    )


def test_pubmed_missing_step_ctx():
    """Verifies that the `PubMedFetchStep` halts as needed when encountering a context with a missing result."""
    search_step = PubMedSearchStep()
    fetch_step = PubMedFetchStep()

    ctx = StepContext(step_number=1, step=search_step, result=None)

    with requests_mock.Mocker() as _, pytest.raises(RuntimeError) as excinfo:

        _ = fetch_step.pre_transform(ctx)
    nonresponse_error_message = (
        "The `PubMedFetchStep` of the current workflow cannot continue, because the "
        "previous step did not execute successfully. The result from the previous step is `None`."
    )

    assert nonresponse_error_message in str(excinfo.value)


def test_direct_pubmed_workflow(
    mock_pubmed_search_endpoint,
    mock_pubmed_fetch_endpoint,
    mock_pubmed_search_data,
    mock_pubmed_fetch_data,
    xml_parsing_dependency,
):
    """Tests whether mock pubmed search and fetch XML data can be directly parsed and processed in that order.

    The use of the PubMed API requires that xml2dict is available. If available, the retrieval steps occur in order:
     1. Fetch a response containing IDs matching the query
     2. Process and retrieve a list of metadata fields in a post_transform step
     3. Use the list of metadata responses to retrieve their corresponding abstracts

    """
    if not xml_parsing_dependency:
        pytest.skip("Cannot test the direct pubmed workflow without the xmltodict library. Skipping...")

    with requests_mock.Mocker() as m:
        m.get(
            mock_pubmed_search_endpoint,
            content=mock_pubmed_search_data["_content"].encode(),
            headers={"Content-Type": "text/xml; charset=UTF-8"},
            status_code=200,
        )

        m.get(
            mock_pubmed_fetch_endpoint,
            content=mock_pubmed_fetch_data["_content"].encode(),
            headers={"Content-Type": "text/xml; charset=UTF-8"},
            status_code=200,
        )

        pubmed_workflow = SearchWorkflow(
            steps=[PubMedSearchStep(), PubMedFetchStep(search_parameters=dict(from_process_cache=False))]
        )
        api = SearchAPI.from_defaults("anxiety", "pubmed", user_agent="scholar_flux", use_cache=True)

        pubmed_coordinator = SearchCoordinator(api)
        result = pubmed_workflow(pubmed_coordinator, page=3)

    assert isinstance(result, WorkflowResult)
    for step_context in result.history:
        assert isinstance(step_context, StepContext)
        assert isinstance(step_context.result, ProcessedResponse) is not None
        assert step_context.result is not None
    assert result.result == result.history[-1].result
    assert result.result.data is not None


def test_workflow_default(
    mock_pubmed_search_endpoint,
    mock_pubmed_fetch_endpoint,
    mock_pubmed_search_data,
    mock_pubmed_fetch_data,
    xml_parsing_dependency,
):
    """Verifies with default settings that a simple `SearchCoordinator.search will automatically retrieve The expected
    results using the workflow automatically when using the `pubmed` provider_name.

    Also verifies that when `use_workflow` is False, the SearchCoordinator will only perform the `esearch` step that
    retrieves a list of metadata IDs for articles relating to the query.

    """
    if not xml_parsing_dependency:
        pytest.skip("Cannot test the direct pubmed workflow without the xmltodict library. Skipping...")

    with requests_mock.Mocker() as m:
        m.get(
            mock_pubmed_search_endpoint,
            content=mock_pubmed_search_data["_content"].encode(),
            headers={"Content-Type": "text/xml; charset=UTF-8"},
            status_code=200,
        )

        m.get(
            mock_pubmed_fetch_endpoint,
            content=mock_pubmed_fetch_data["_content"].encode(),
            headers={"Content-Type": "text/xml; charset=UTF-8"},
            status_code=200,
        )

        api = SearchAPI.from_defaults(
            "anxiety", "pubmed", user_agent="scholar_flux", request_delay=0.01, use_cache=True
        )
        pubmed_coordinator = SearchCoordinator(api)
        search_result = pubmed_coordinator.search_page(page=3, use_workflow=False)
        fetch_result = pubmed_coordinator.search_page(page=3)

    assert isinstance(search_result.response_result, ProcessedResponse)
    # originates from the eSearch Step while records originate from the eFetch Step
    assert search_result.metadata and search_result.metadata == pubmed_coordinator.workflow._history[0].result.metadata  # type: ignore
    assert search_result.response and search_result.response.content == mock_pubmed_search_data["_content"].encode(
        "utf-8"
    )

    assert isinstance(fetch_result.response_result, ProcessedResponse)
    assert fetch_result.response and fetch_result.response.content == mock_pubmed_fetch_data["_content"].encode("utf-8")
    assert search_result.response.content != fetch_result.response.content

    assert search_result.provider_name == "pubmed"  # original URL - indicates that workflow was not used (only eSearch)
    assert fetch_result.provider_name == "pubmedefetch"  # indicates that the workflow was used (eFetch is step 2)


def test_dependency_error(mock_pubmed_search_endpoint, mock_pubmed_search_data, monkeypatch, caplog):
    """Verifies that the workflow halts with the expected message when encountering missing xml dependencies."""

    monkeypatch.setattr("scholar_flux.data.base_parser.xmltodict", None)
    with requests_mock.Mocker() as m:
        m.get(
            mock_pubmed_search_endpoint,
            content=mock_pubmed_search_data["_content"].encode(),
            headers={"Content-Type": "text/xml; charset=UTF-8"},
            status_code=200,
        )

        api = SearchAPI.from_defaults(
            "anxiety", "pubmed", user_agent="scholar_flux", request_delay=0.01, use_cache=True
        )
        pubmed_coordinator = SearchCoordinator(api)
        assert pubmed_coordinator.workflow
        search_result = pubmed_coordinator.search(page=3, use_workflow=True)
        assert isinstance(search_result, ErrorResponse)
        assert search_result.status_code == 200 and "DataParsingException" in (search_result.error or "")

        error_message = str(XMLToDictImportError())
        assert "Halting the current workflow and returning the result from step 0: PubMedSearchStep..." in caplog.text
        assert search_result.error and error_message in (search_result.message or "")

        pubmed_coordinator.workflow.stop_on_error = False
        nonresponse_search_result = pubmed_coordinator.search(page=3, use_workflow=True)
        assert isinstance(nonresponse_search_result, NonResponse) and nonresponse_search_result.message

        nonresponse_error_message = (
            "The `PubMedFetchStep` of the current workflow cannot continue, because the "
            f"previous step did not execute successfully. Error: {search_result.message}"
        )

        assert nonresponse_error_message in nonresponse_search_result.message


def test_pubmed_workflow_no_initial_esearch_result(monkeypatch):
    """Covers the failure case where `NoRecordsAvailableException` is raised and no initial eSearch result exists."""

    coordinator = SearchCoordinator(provider_name="pubmed", query="Cardiovascular Endurance")
    assert coordinator.workflow

    # Patch super()._run to raise NoRecordsAvailableException
    def raise_no_records(*args, **kwargs):
        """Temporary function used to patch the `SearchWorkflow._run` method to raise a `NoRecordsAvailableException`"""
        raise NoRecordsAvailableException("No records found.")

    monkeypatch.setattr(SearchWorkflow, "_run", raise_no_records)

    # Ensures no actual requests are sent
    with requests_mock.Mocker() as _:
        response = coordinator.search(page=1)

    assert isinstance(response, NonResponse) and response.message and response.error
    assert "RuntimeError" in response.error
    assert "The PubMed Workflow failed without the retrieval of an initial eSearch response" in response.message

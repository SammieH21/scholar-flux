from scholar_flux.api.workflows import PubMedSearchStep, PubMedFetchStep, SearchWorkflow, WorkflowResult, StepContext
from scholar_flux.api import SearchAPI, SearchCoordinator, ProcessedResponse, ErrorResponse, NonResponse
from scholar_flux.exceptions import XMLToDictImportError
from requests import Response
from unittest.mock import MagicMock
import requests_mock
import pytest


def test_pubmed_workflow_context(caplog):
    """Validates whether the use of a pubmed workflow with missing IDs will correctly be flagged.

    When a received response is valid and contains a valid formatted
    metadata field, the metadata dictionary will contain
    {'IdList':{'Id': [...]}. If unavailable, a type error should be
    raised.

    """
    response = Response()
    response.status_code = 200

    metadata = MagicMock()
    metadata.result = {}

    search_step = PubMedSearchStep()
    fetch_step = PubMedFetchStep()
    ctx = StepContext(step_number=1, step=search_step, result=ProcessedResponse(response=response, metadata=metadata))

    with pytest.raises(TypeError):
        _ = fetch_step.pre_transform(ctx)

    assert "The metadata from the pubmed search is not in the expected format" in caplog.text


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
    1) Fetch a response containing IDs matching the query     2) Process and retrieve a list of metadata fields in a
    post_transform step     3) Use the list of metadata responses to retrieve their corresponding abstracts

    """
    if not xml_parsing_dependency:
        pytest.skip("Cannot test the direct pubmed workflow without the xmltodict library. Skipping...")

    pubmed_api_key = "this_is_a_mocked_api_key"
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
        api = SearchAPI.from_defaults(
            "anxiety", "pubmed", user_agent="scholar_flux", api_key=pubmed_api_key, use_cache=True
        )

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

    pubmed_api_key = "this_is_a_mocked_api_key"
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
            "anxiety", "pubmed", user_agent="scholar_flux", api_key=pubmed_api_key, request_delay=0.01, use_cache=True
        )
        pubmed_coordinator = SearchCoordinator(api)
        search_result = pubmed_coordinator.search(page=3, use_workflow=False)
        fetch_result = pubmed_coordinator.search(page=3)

    assert isinstance(search_result, ProcessedResponse)
    assert search_result.response and search_result.response.content == mock_pubmed_search_data["_content"].encode(
        "utf-8"
    )

    assert isinstance(fetch_result, ProcessedResponse)
    assert fetch_result.response and fetch_result.response.content == mock_pubmed_fetch_data["_content"].encode("utf-8")
    assert search_result.response.content != fetch_result.response.content


def test_dependency_error(mock_pubmed_search_endpoint, mock_pubmed_search_data, monkeypatch, caplog):
    """Verifies that the workflow halts with the expected message when encountering missing xml dependencies."""

    monkeypatch.setattr("scholar_flux.data.base_parser.xmltodict", None)
    pubmed_api_key = "this_is_a_mocked_api_key"
    with requests_mock.Mocker() as m:
        m.get(
            mock_pubmed_search_endpoint,
            content=mock_pubmed_search_data["_content"].encode(),
            headers={"Content-Type": "text/xml; charset=UTF-8"},
            status_code=200,
        )

        api = SearchAPI.from_defaults(
            "anxiety", "pubmed", user_agent="scholar_flux", api_key=pubmed_api_key, request_delay=0.01, use_cache=True
        )
        pubmed_coordinator = SearchCoordinator(api)
        assert pubmed_coordinator.workflow
        search_result = pubmed_coordinator.search(page=3, use_workflow=True)
        assert isinstance(search_result, ErrorResponse)
        assert search_result.status_code == 200 and "DataParsingException" in (search_result.error or "")

        error_message = str(XMLToDictImportError())
        assert "Halting the current workflow and returning the result from step 0..." in caplog.text
        assert search_result.error and error_message in (search_result.message or "")

        pubmed_coordinator.workflow.stop_on_error = False
        nonresponse_search_result = pubmed_coordinator.search(page=3, use_workflow=True)
        assert isinstance(nonresponse_search_result, NonResponse) and nonresponse_search_result.message

        nonresponse_error_message = (
            "The `PubMedFetchStep` of the current workflow cannot continue, because the "
            f"previous step did not execute successfully. Error: {search_result.message}"
        )

        assert nonresponse_error_message in nonresponse_search_result.message

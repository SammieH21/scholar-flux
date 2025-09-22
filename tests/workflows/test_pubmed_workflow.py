from scholar_flux.api.workflows import PubMedSearchStep, PubMedFetchStep, SearchWorkflow, WorkflowResult, StepContext
from scholar_flux.api import SearchAPI, SearchCoordinator, ProcessedResponse
from requests import Response
from unittest.mock import MagicMock
import requests_mock
import pytest


def test_pubmed_workflow_context(caplog):
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


def test_direct_pubmed_workflow(
    mock_pubmed_search_endpoint,
    mock_pubmed_fetch_endpoint,
    mock_pubmed_search_data,
    mock_pubmed_fetch_data,
    xml_parsing_dependency,
):
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
            "anxiety", "pubmed", user_agent="SammieH", api_key=pubmed_api_key, request_delay=0.01, use_cache=True
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

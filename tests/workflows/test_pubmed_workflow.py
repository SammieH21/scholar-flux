from scholar_flux.api.workflows import PubMedSearchStep, PubMedFetchStep, SearchWorkflow, WorkflowResult, StepContext
from scholar_flux.api import SearchAPI, SearchCoordinator, ProcessedResponse
import requests_mock


def test_direct_pubmed_workflow(
                              mock_pubmed_search_endpoint,
                              mock_pubmed_fetch_endpoint,
                              mock_pubmed_search_data,
                              mock_pubmed_fetch_data,
                              pubmed_api_key):

    assert pubmed_api_key
    with requests_mock.Mocker() as m:
        m.get(mock_pubmed_search_endpoint,
              content = mock_pubmed_search_data['_content'].encode(),
              headers = {"Content-Type": "text/xml; charset=UTF-8"},
              status_code = 200,
             )

        m.get(mock_pubmed_fetch_endpoint,
              content = mock_pubmed_fetch_data['_content'].encode(),
              headers = {"Content-Type": "text/xml; charset=UTF-8"},
              status_code = 200,
             )

        pubmed_workflow = SearchWorkflow(steps=[PubMedSearchStep(),
                                                PubMedFetchStep(search_parameters=dict(from_process_cache=False))
                                               ]
                                        )
        api = SearchAPI.from_defaults('anxiety', 'pubmed', user_agent = 'SammieH', api_key=pubmed_api_key, use_cache=True)

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
                              pubmed_api_key):

    assert pubmed_api_key
    with requests_mock.Mocker() as m:
        m.get(mock_pubmed_search_endpoint,
              content = mock_pubmed_search_data['_content'].encode(),
              headers = {"Content-Type": "text/xml; charset=UTF-8"},
              status_code = 200,
             )

        m.get(mock_pubmed_fetch_endpoint,
              content = mock_pubmed_fetch_data['_content'].encode(),
              headers = {"Content-Type": "text/xml; charset=UTF-8"},
              status_code = 200,
             )

        api = SearchAPI.from_defaults('anxiety', 'pubmed',
                                      user_agent = 'SammieH',
                                      api_key=pubmed_api_key,
                                      request_delay = 0.01,
                                      use_cache=True)
        pubmed_coordinator = SearchCoordinator(api)
        search_result = pubmed_coordinator.search(page=3, use_workflow = False)
        fetch_result = pubmed_coordinator.search(page=3)

    assert isinstance(search_result, ProcessedResponse)
    assert search_result.response and search_result.response.content == mock_pubmed_search_data['_content'].encode('utf-8')

    assert isinstance(fetch_result, ProcessedResponse)
    assert fetch_result.response and fetch_result.response.content == mock_pubmed_fetch_data['_content'].encode('utf-8')
    assert search_result.response.content != fetch_result.response.content



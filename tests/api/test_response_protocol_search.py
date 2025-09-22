from scholar_flux.api.models import ProcessedResponse, ReconstructedResponse, APIResponse
from scholar_flux.api import SearchCoordinator, ResponseCoordinator
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.exceptions import InvalidResponseReconstructionException, InvalidCoordinatorParameterException
from scholar_flux.data import DataParser
import requests_mock
from requests import Response
import pytest


def test_plos_reprocessing(plos_search_api, plos_page_1_url, plos_page_1_data, plos_headers):
    plos_search_coordinator = SearchCoordinator(
        query="social wealth equity", search_api=plos_search_api, provider_name="plos", base_url=plos_page_1_url
    )

    with requests_mock.Mocker() as m:
        m.get(
            plos_page_1_url,
            json=plos_page_1_data,
            headers=plos_headers,
            status_code=200,
        )

        response = plos_search_coordinator.search(page=1)
        assert isinstance(response, ProcessedResponse)

        cache_key = response.cache_key
        rehandled_response = plos_search_coordinator.response_coordinator.handle_response(response, cache_key, from_cache=False)  # type: ignore
        assert rehandled_response == response

        assert (
            isinstance(response.status_code, int)
            and isinstance(response.content, bytes)
            and isinstance(response.reason, str)
            and isinstance(response, ProcessedResponse)
            and isinstance(response.response, Response)
        )

        # use as a reconstruction of the original response
        reconstructed_response = APIResponse.as_reconstructed_response(response)

        # mock the previously rehandled response as using a ReconstructedResponse instead of a Response
        rehandled_response.response = APIResponse.as_reconstructed_response(rehandled_response)

        # use a reconstructed response to regenerate a new response for later comparison
        re_rehandled_response = plos_search_coordinator.response_coordinator.handle_response(reconstructed_response, cache_key, from_cache=False)  # type: ignore

        # compare the processed response against the response that's been rehandled and processed twice
        assert re_rehandled_response == rehandled_response
        assert ProcessedResponse.model_validate_json(re_rehandled_response.model_dump_json()) == rehandled_response


def test_response_coordinated_validation(plos_search_api, plos_page_1_url, plos_page_1_data, plos_headers):

    api_response = APIResponse.from_response(
        url=plos_page_1_url, json=plos_page_1_data, headers=plos_headers, status_code=200
    )

    assert isinstance(api_response, ResponseProtocol)
    assert ResponseCoordinator._resolve_response(api_response, validate=True) == api_response.response

    # missing the URL
    invalid_api_response = APIResponse.from_response(
        url="invalid url", json=plos_page_1_data, headers=plos_headers, status_code=200
    )

    # still has the URL attribute, just missing a value. A ResponseProtocol checks class structure only
    assert isinstance(invalid_api_response, ResponseProtocol)
    # attempts to reconstruct a response objec if not already, doesn't validate field values yet
    assert ResponseCoordinator._resolve_response(invalid_api_response, validate=False) == invalid_api_response.response

    # validates the field values and throws an error, because the URL is invalid:
    with pytest.raises(InvalidResponseReconstructionException) as excinfo:
        _ = ResponseCoordinator._resolve_response(invalid_api_response, validate=True)

    assert (
        "The ReconstructedResponse was not created successfully: Missing valid values for critical "
        "fields to validate the response. The following fields are invalid: {'url': 'invalid url'}"
    ) in str(excinfo.value)


def test_mocked_response_like_search(plos_search_api, plos_page_1_url, plos_page_1_data, plos_headers, monkeypatch):

    response = APIResponse.from_response(
        url=plos_page_1_url, json=plos_page_1_data, headers=plos_headers, status_code=200
    )

    # otherwise raises an error if invalid
    assert (
        response
        and response.response
        and isinstance(response, ResponseProtocol)
        and isinstance(response.response, ResponseProtocol)
        and isinstance(response.response, ReconstructedResponse)
    )

    assert response.response.validate() is None  # type: ignore

    parser = DataParser()

    parsed_response = parser(response)
    assert isinstance(parsed_response, (dict, list))
    assert parsed_response == response.response.json()


def test_response_like_exception(monkeypatch):
    response = APIResponse.from_response(
        cache_key="cache-key", status_code=200, content=b"success", url="https://google.com"
    )
    assert isinstance(response, APIResponse)
    assert isinstance(response.response, ReconstructedResponse)
    assert isinstance(response, ResponseProtocol)
    assert response.response.validate() is None  # type: ignore

    monkeypatch.setattr(APIResponse, "as_reconstructed_response", lambda *args, **kwargs: None)

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = ResponseCoordinator._resolve_response(response, validate=False)

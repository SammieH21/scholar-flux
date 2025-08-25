from typing import Any, Dict, Optional
import requests_mock
import pytest

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _build_response(request, data: Dict[str, Any]):
    """
    Build a requests.Response via requests-mock using a dict payload.

    Expected keys in `data`:
      - '_content': str | bytes (response body, required)
      - 'status_code': int = 200
      - 'headers': dict = {'Content-Type': 'text/xml; charset=UTF-8'}
      - 'encoding': str = 'UTF-8'
      - 'reason', 'cookies' (optional)
    """
    # Body -> bytes
    encoding = data.get("encoding", "UTF-8")
    raw_content = data["_content"]
    if isinstance(raw_content, str):
        content = raw_content.encode(encoding)
    else:
        content = raw_content

    headers = {"Content-Type": "text/xml; charset=UTF-8"}
    headers.update(data.get("headers", {}))

    return requests_mock.create_response(
        request,
        content=content,
        status_code=data.get("status_code", 200),
        headers=headers,
        reason=data.get("reason"),
        cookies=data.get("cookies"),
    )

def make_pubmed_matcher(esearch_data: Dict[str, Any],
                        efetch_data: Dict[str, Any]):
    """
    Returns a matcher that activates both endpoints simultaneously.
    It ignores querystrings and matches by URL prefix.
    """
    def _matcher(req):
        url = req.url
        if url.startswith(ESEARCH_URL):
            return _build_response(req, esearch_data)
        if url.startswith(EFETCH_URL):
            return _build_response(req, efetch_data)
        return None  # let other matchers (or real_http) handle
    return _matcher


@pytest.fixture
def pubmed_mock_factory(requests_mock):
    """
    Usage:
        rm = pubmed_mock_factory(esearch_payload, efetch_payload)
        # now run code that calls ESearch/EFetch; other hosts remain unmocked unless you add more.
    """
    def _install(esearch_data, efetch_data, mocker = None):
        if mocker is None:
            mocker = requests_mock
        requests_mock.add_matcher(make_pubmed_matcher(esearch_data, efetch_data))
        return mocker
    return _install

if __name__ == '__main__':
    import requests
    
    esearch_payload = {
        "_content": """<?xml version="1.0" encoding="UTF-8"?>
    <eSearchResult><IdList><Id>12345</Id><Id>67890</Id></IdList></eSearchResult>""",
        "status_code": 200,
        "headers": {"Content-Type": "text/xml; charset=UTF-8"},
        "encoding": "UTF-8",
    }

    efetch_payload = {
        "_content": """<?xml version="1.0" encoding="UTF-8"?>
    <PubmedArticleSet><PubmedArticle><PMID>12345</PMID></PubmedArticle></PubmedArticleSet>""",
        "status_code": 200,
        "headers": {"Content-Type": "text/xml; charset=UTF-8"},
        "encoding": "UTF-8",
    }

    with requests_mock.Mocker(real_http=False) as m:
        m.add_matcher(make_pubmed_matcher(esearch_payload, efetch_payload))

        r1 = requests.get(ESEARCH_URL + "?db=pubmed&term=test")
        r2 = requests.get(EFETCH_URL  + "?db=pubmed&id=12345&rettype=xml")

        assert r1.status_code == 200 and r1.headers["Content-Type"].startswith("text/xml")
        assert r2.status_code == 200 and "<PMID>12345</PMID>" in r2.text
        assert isinstance(r1, requests.Response)
        print(r1.__dict__)




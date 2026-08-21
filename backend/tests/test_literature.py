import httpx

from app.config import Settings
from app.literature import LiteratureClient


PUBMED_XML = b"""<?xml version='1.0' encoding='UTF-8'?>
<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID>
<Article><ArticleTitle>CRISPR intervention for sickle-cell disease</ArticleTitle>
<Abstract><AbstractText>Source-grounded abstract.</AbstractText></Abstract>
<Journal><JournalIssue><PubDate><Year>2024</Year><Month>01</Month><Day>02</Day></PubDate></JournalIssue></Journal>
<AuthorList><Author><LastName>Researcher</LastName><Initials>A</Initials></Author></AuthorList>
</Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType='doi'>10.1000/example</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle></PubmedArticleSet>"""


def test_real_api_clients_normalize_pubmed_and_europe_pmc_records() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("esearch.fcgi"):
            assert "sickle cell disease" in request.url.params["term"]
            assert "CRISPR" in request.url.params["term"]
            return httpx.Response(200, json={"esearchresult": {"idlist": ["12345"]}})
        if request.url.path.endswith("efetch.fcgi"):
            return httpx.Response(200, content=PUBMED_XML)
        if request.url.path.endswith("/search"):
            assert "TITLE_ABS" in request.url.params["query"]
            return httpx.Response(
                200,
                json={
                    "resultList": {
                        "result": [
                            {
                                "id": "PMC123",
                                "source": "PMC",
                                "pmid": "12345",
                                "title": "CRISPR intervention for sickle-cell disease",
                                "abstractText": "Europe PMC abstract.",
                                "authorString": "Researcher A",
                                "firstPublicationDate": "2024-01-02",
                                "doi": "10.1000/example",
                            }
                        ]
                    }
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    settings = Settings(literature_max_results=3, literature_timeout_seconds=3)
    client = LiteratureClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))

    pubmed = client.search_pubmed("sickle-cell CRISPR")
    europe_pmc = client.search_europe_pmc("sickle-cell CRISPR")

    assert pubmed[0].source == "pubmed"
    assert pubmed[0].external_id == "12345"
    assert pubmed[0].doi == "10.1000/example"
    assert pubmed[0].authors == ["Researcher A"]
    assert "CRISPR" in pubmed[0].metadata["search_query"]
    assert europe_pmc[0].source == "pubmed"
    assert europe_pmc[0].external_id == "12345"
    assert europe_pmc[0].metadata["source_records"] == ["europepmc"]
    assert "TITLE_ABS" in europe_pmc[0].metadata["search_query"]

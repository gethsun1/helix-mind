import httpx

from app.config import Settings
from app.literature import EUROPE_PMC, LiteratureClient, _clean_doi, _clean_pmcid, _clean_pmid


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

    assert pubmed[0].source == "PUBMED"
    assert pubmed[0].external_id == "12345"
    assert pubmed[0].doi == "10.1000/example"
    assert pubmed[0].authors == ["Researcher A"]
    assert "CRISPR" in pubmed[0].metadata["search_query"]
    assert pubmed[0].metadata["source_identifiers"]["PUBMED"] == "12345"
    assert europe_pmc[0].source == "EUROPE_PMC"
    assert europe_pmc[0].external_id == "pmc:PMC123"
    assert europe_pmc[0].pmid == "12345"
    assert europe_pmc[0].metadata["source_records"] == ["EUROPE_PMC"]
    assert europe_pmc[0].metadata["source_identifiers"]["EUROPE_PMC"] == "PMC123"
    assert "TITLE_ABS" in europe_pmc[0].metadata["search_query"]


def test_identifier_normalization_and_provider_registry() -> None:
    assert _clean_doi("https://doi.org/10.1000/Example") == "10.1000/example"
    assert _clean_pmid("pmid:12345") == "12345"
    assert _clean_pmcid("pmc:PMC123") == "PMC123"
    client = LiteratureClient(settings=Settings(), client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200))))
    assert set(client.providers) == {"PUBMED", EUROPE_PMC}
    client.close()

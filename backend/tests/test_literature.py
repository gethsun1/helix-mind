import httpx
from datetime import date

from app.config import Settings
from app.literature import EUROPE_PMC, LiteratureClient, NormalizedPaper, _clean_doi, _clean_pmcid, _clean_pmid, deduplicate_papers
from app.literature_intelligence import calculate_relevance, deduplication_groups, identity_keys, normalized_title, snapshot_literature_diff
from app.models import Paper


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


def test_literature_identity_normalizes_identifiers_and_keeps_title_matches_advisory() -> None:
    first = Paper(id="00000000-0000-0000-0000-000000000001", title="CRISPR: HBB editing", source="PUBMED", external_id="1", doi="https://doi.org/10.1000/EXAMPLE", pmid="123")
    second = Paper(id="00000000-0000-0000-0000-000000000002", title="CRISPR HBB editing", source="EUROPE_PMC", external_id="2", doi="10.1000/example", pmid="123")
    assert normalized_title(first.title) == normalized_title(second.title)
    assert "doi:10.1000/example" in identity_keys(first)
    groups = deduplication_groups([first, second])
    assert any(item["basis"] == "canonical_identifier" and not item["merged"] for item in groups)
    assert any(item["basis"] == "title_candidate" and not item["merged"] for item in groups)


def test_literature_relevance_is_deterministic_bounded_and_separate_from_confidence() -> None:
    kwargs = {"rank": 1, "evidence_count": 2, "entity_count": 4, "has_proposition": True, "has_hypothesis": False}
    first = calculate_relevance(**kwargs)
    assert calculate_relevance(**kwargs) == first
    assert first["score"] == 0.75
    assert first["inputs"]["entity_overlap"] == 1.0
    assert "confidence" not in first
    assert calculate_relevance(rank=None, evidence_count=0, entity_count=0, has_proposition=False, has_hypothesis=False)["score"] == 0
    assert calculate_relevance(rank=-4, evidence_count=-1, entity_count=0, has_proposition=False, has_hypothesis=False)["inputs"]["retrieval_rank"] == 0


def test_canonical_dedup_uses_identifiers_and_conservative_title_author_year() -> None:
    pubmed = NormalizedPaper(source="PUBMED", external_id="123", title="Source title", abstract="Abstract", authors=["A Author"], publication_date=date(2024, 1, 1), doi="10.1000/shared", url=None, metadata={"source_records": ["PUBMED"]}, pmid="123")
    europe = NormalizedPaper(source="EUROPE_PMC", external_id="PMC123", title="Different provider title", abstract=None, authors=["A Author"], publication_date=date(2024, 1, 1), doi="10.1000/shared", url=None, metadata={"source_records": ["EUROPE_PMC"]}, pmid="123")
    fallback_a = NormalizedPaper(source="PUBMED", external_id="a", title="A punctuation-sensitive title!", abstract=None, authors=["A Author"], publication_date=date(2022, 1, 1), doi=None, url=None)
    fallback_same = NormalizedPaper(source="EUROPE_PMC", external_id="b", title="A punctuation-sensitive title", abstract=None, authors=["A Author"], publication_date=date(2022, 4, 1), doi=None, url=None)
    fallback_distinct_author = NormalizedPaper(source="EUROPE_PMC", external_id="c", title="A punctuation-sensitive title", abstract=None, authors=["Different Author"], publication_date=date(2022, 1, 1), doi=None, url=None)
    unique, removed = deduplicate_papers([pubmed, europe, fallback_a, fallback_same, fallback_distinct_author])
    assert len(unique) == 3 and removed == 2
    assert set(unique[0].metadata["source_records"]) == {"PUBMED", "EUROPE_PMC"}


def test_snapshot_literature_diff_uses_frozen_record_links() -> None:
    paper = {"id": "p1", "title": "Fixture publication"}
    left = {"papers": [paper], "claims": [{"id": "c1", "paper_id": "p1", "proposition_id": "pr1"}], "evidence": [{"id": "e1", "paper_id": "p1", "proposition_id": "pr1", "extracted_text": "Original span"}], "entities": [], "relationships": [], "propositions": [{"id": "pr1", "description": "p"}], "hypotheses": []}
    right = {"papers": [paper], "claims": [{"id": "c1", "paper_id": "p1", "proposition_id": "pr1"}, {"id": "c2", "paper_id": "p1", "proposition_id": "pr1"}], "evidence": [{"id": "e1", "paper_id": "p1", "proposition_id": "pr1", "extracted_text": "Changed span"}, {"id": "e2", "paper_id": "p1", "proposition_id": "pr1"}], "entities": [], "relationships": [], "propositions": [{"id": "pr1", "description": "p"}], "hypotheses": [{"id": "h1", "proposition_id": "pr1"}]}
    result = snapshot_literature_diff(left, right)
    assert result["publicationsAdded"] == [] and result["publicationsRemoved"] == []
    changes = result["contributionChanges"][0]["changes"]
    assert changes["evidence"]["added"] == ["e2"]
    assert changes["evidence"]["changed"] == ["e1"]
    assert changes["claims"]["added"] == ["c2"]
    assert changes["hypotheses"]["added"] == ["h1"]

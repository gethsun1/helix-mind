"""Source-attributed PubMed and Europe PMC literature intelligence."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Protocol

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import InvestigationPaper, Paper


PUBMED = "PUBMED"
EUROPE_PMC = "EUROPE_PMC"
PUBMED_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_STOP_WORDS = {"and", "or", "the", "of", "for", "with", "from", "to", "in", "a", "an", "on", "by"}


class LiteratureError(RuntimeError):
    """A source response could not be retrieved or normalized safely."""


@dataclass
class NormalizedPaper:
    source: str
    external_id: str
    title: str
    abstract: str | None
    authors: list[str]
    publication_date: date | None
    doi: str | None
    url: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    journal: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    publication_type: list[str] = field(default_factory=list)
    language: str | None = None
    mesh_terms: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    publisher_identifier: str | None = None
    full_text_url: str | None = None
    journal_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source = self.source.upper().replace("EUROPEPMC", EUROPE_PMC)
        self.source = source


@dataclass
class SourceSearchResult:
    source: str
    query: str
    papers: list[NormalizedPaper]
    total_count: int


class LiteratureProvider(Protocol):
    """Provider contract for source retrieval and normalization."""

    source: str

    def search(self, query: str, *, page: int = 1, page_size: int | None = None, filters: dict[str, Any] | None = None) -> SourceSearchResult:
        ...


def _text(node: element_tree.Element | None) -> str | None:
    if node is None:
        return None
    value = "".join(node.itertext()).strip()
    return value or None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    month_names = {name: number for number, name in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
    for candidate in (value, value[:10], value[:7], value[:4]):
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
                return date.fromisoformat(candidate)
            if re.fullmatch(r"\d{4}-\d{2}", candidate):
                return date.fromisoformat(f"{candidate}-01")
            if re.fullmatch(r"\d{4}", candidate):
                return date.fromisoformat(f"{candidate}-01-01")
        except ValueError:
            pass
    match = re.search(r"(\d{4})\s+([A-Za-z]{3})", value)
    if match and match.group(2).title() in month_names:
        return date(int(match.group(1)), month_names[match.group(2).title()], 1)
    year_match = re.search(r"\d{4}", value)
    return date(int(year_match.group(0)), 1, 1) if year_match else None


def _clean_doi(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().lower()
    cleaned = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", cleaned)
    cleaned = cleaned.removeprefix("doi:").strip()
    return cleaned or None


def _clean_pmid(value: Any) -> str | None:
    cleaned = _clean_identifier(value)
    return cleaned.removeprefix("pmid:").strip() if cleaned else None


def _clean_pmcid(value: Any) -> str | None:
    cleaned = _clean_identifier(value)
    if not cleaned:
        return None
    return cleaned.removeprefix("pmcid:").removeprefix("pmc:").strip().upper()


def _clean_identifier(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _europe_full_text_url(record: dict[str, Any]) -> str | None:
    values = record.get("fullTextUrlList", {}).get("fullTextUrl", []) if isinstance(record.get("fullTextUrlList"), dict) else []
    if not isinstance(values, list):
        return None
    for item in values:
        if isinstance(item, dict):
            url = _clean_identifier(item.get("url"))
            if url:
                return url
    return None


def build_pubmed_query(plan_query: str) -> str:
    """Return an actual PubMed query, preserving plan-derived syntax."""
    if "[Title/Abstract]" in plan_query or "[Mesh]" in plan_query:
        return plan_query
    normalized = plan_query.lower()
    has_crispr = "crispr" in normalized
    has_sickle_cell = bool(re.search(r"sickle[- ]cell", normalized))
    if has_crispr and has_sickle_cell:
        return '"sickle cell disease"[Title/Abstract] AND (CRISPR[Title/Abstract] OR "gene editing"[Title/Abstract])'
    return plan_query.strip()


def build_europe_pmc_query(plan_query: str) -> str:
    """Return a Europe PMC query equivalent to the plan-derived concepts."""
    if "TITLE_ABS:" in plan_query:
        return plan_query
    normalized = plan_query.lower()
    has_crispr = "crispr" in normalized
    has_sickle_cell = bool(re.search(r"sickle[- ]cell", normalized))
    if has_crispr and has_sickle_cell:
        return 'TITLE_ABS:"sickle cell disease" AND (TITLE_ABS:CRISPR OR TITLE_ABS:"gene editing")'
    return plan_query.strip()


def _pubmed_article(article: element_tree.Element) -> NormalizedPaper | None:
    pmid = _clean_pmid(_text(article.find(".//PMID")))
    title = _text(article.find(".//ArticleTitle"))
    if not pmid or not title:
        return None

    abstract_parts = []
    for node in article.findall(".//Abstract/AbstractText"):
        value = _text(node)
        if value:
            label = node.attrib.get("Label")
            abstract_parts.append(f"{label}: {value}" if label else value)
    authors: list[str] = []
    for author in article.findall(".//Author"):
        collective = _text(author.find("CollectiveName"))
        if collective:
            authors.append(collective)
            continue
        family = _text(author.find("LastName"))
        initials = _text(author.find("Initials"))
        if family:
            authors.append(" ".join(part for part in (family, initials) if part))

    identifiers = {node.attrib.get("IdType", "").lower(): _text(node) for node in article.findall(".//ArticleId")}
    doi = _clean_doi(identifiers.get("doi"))
    pmcid = _clean_pmcid(identifiers.get("pmc"))
    pub_date = article.find(".//Article/Journal/JournalIssue/PubDate")
    year = _text(pub_date.find("Year")) if pub_date is not None else None
    month = _text(pub_date.find("Month")) if pub_date is not None else None
    day = _text(pub_date.find("Day")) if pub_date is not None else None
    publication_date = _parse_date("-".join(part for part in (year, month, day) if part))
    if publication_date is None:
        publication_date = _parse_date(_text(pub_date.find("MedlineDate")) if pub_date is not None else None)
    journal = _text(article.find(".//Article/Journal/Title"))
    journal_metadata = {
        key: value for key, value in {
            "issn": _text(article.find(".//Article/Journal/ISSN")),
            "volume": _text(article.find(".//Article/Journal/JournalIssue/Volume")),
            "issue": _text(article.find(".//Article/Journal/JournalIssue/Issue")),
        }.items() if value
    }
    full_text_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else None
    publisher_identifier = _clean_identifier(identifiers.get("pii")) or _clean_identifier(identifiers.get("publisherid"))
    publication_types = [_text(node) for node in article.findall(".//PublicationTypeList/PublicationType")]
    languages = [_text(node) for node in article.findall(".//Language")]
    mesh_terms = [_text(node) for node in article.findall(".//MeshHeading/DescriptorName")]
    keywords = [_text(node) for node in article.findall(".//KeywordList/Keyword")]
    return NormalizedPaper(
        source=PUBMED,
        external_id=pmid,
        title=title,
        abstract="\n".join(abstract_parts) or None,
        authors=authors,
        publication_date=publication_date,
        doi=doi,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        metadata={"pmid": pmid, "source_records": [PUBMED], "source_identifiers": {PUBMED: pmid}},
        journal=journal,
        pmid=pmid,
        pmcid=pmcid,
        publication_type=[item for item in publication_types if item],
        language=languages[0] if languages and languages[0] else None,
        mesh_terms=[item for item in mesh_terms if item],
        keywords=[item for item in keywords if item],
        publisher_identifier=publisher_identifier,
        full_text_url=full_text_url,
        journal_metadata=journal_metadata,
    )


def _europe_pmc_article(record: dict[str, Any]) -> NormalizedPaper | None:
    title = str(record.get("title") or "").strip()
    source_id = _clean_identifier(record.get("id"))
    source_name = str(record.get("source") or "").strip().upper()
    pmid = _clean_pmid(record.get("pmid"))
    if not title or not source_id:
        return None
    pmcid = _clean_pmcid(source_id) if source_name == "PMC" or source_id.upper().startswith("PMC") else _clean_pmcid(record.get("pmcid"))
    journal = _clean_identifier(record.get("journalTitle"))
    journal_metadata = {key: record[key] for key in ("journalIssn", "journalVolume", "issue") if record.get(key)}
    full_text_url = _europe_full_text_url(record)
    publication_types = record.get("pubType") or record.get("publicationType") or []
    if isinstance(publication_types, str):
        publication_types = [item.strip() for item in publication_types.split(";") if item.strip()]
    authors = [value.strip() for value in str(record.get("authorString") or "").split(",") if value.strip()]
    keywords = record.get("keywordList", {}).get("keyword", []) if isinstance(record.get("keywordList"), dict) else []
    if isinstance(keywords, str):
        keywords = [keywords]
    return NormalizedPaper(
        source=EUROPE_PMC,
        external_id=f"{source_name.lower()}:{source_id}",
        title=title,
        abstract=str(record.get("abstractText") or "").strip() or None,
        authors=authors,
        publication_date=_parse_date(record.get("firstPublicationDate") or record.get("firstIndexDate")),
        doi=_clean_doi(record.get("doi")),
        url=f"https://europepmc.org/article/{source_name.lower()}/{source_id}",
        metadata={"europe_pmc_id": source_id, "europe_pmc_source": source_name, "source_records": [EUROPE_PMC], "source_identifiers": {EUROPE_PMC: source_id}},
        journal=journal,
        pmid=pmid,
        pmcid=pmcid,
        publication_type=[str(item).strip() for item in publication_types if str(item).strip()],
        language=_clean_identifier(record.get("language")),
        keywords=[str(item).strip() for item in keywords if str(item).strip()],
        publisher_identifier=_clean_identifier(record.get("publisherId")),
        full_text_url=full_text_url,
        journal_metadata=journal_metadata,
    )


class LiteratureClient:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client or httpx.Client(timeout=self.settings.literature_timeout_seconds, follow_redirects=True)
        self._owns_client = client is None
        self.providers: dict[str, LiteratureProvider] = {
            PUBMED: PubMedProvider(self),
            EUROPE_PMC: EuropePMCProvider(self),
        }

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except (ValueError, TypeError) as error:
            raise LiteratureError("Scientific literature source returned malformed JSON.") from error
        if not isinstance(payload, dict):
            raise LiteratureError("Scientific literature source returned an invalid response.")
        return payload

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        attempts = max(0, self.settings.literature_retries) + 1
        for attempt in range(attempts):
            try:
                response = self.client.request(method, url, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < attempts:
                        retry_after = response.headers.get("Retry-After")
                        delay = min(float(retry_after), 3.0) if retry_after and retry_after.isdigit() else min(0.5 * (attempt + 1), 2.0)
                        time.sleep(delay)
                        continue
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as error:
                last_error = error
                if attempt + 1 >= attempts:
                    break
                time.sleep(min(0.5 * (attempt + 1), 2.0))
        raise LiteratureError("Scientific literature source request failed.") from last_error

    def search_pubmed_result(self, query: str, *, page: int = 1, page_size: int | None = None, filters: dict[str, Any] | None = None) -> SourceSearchResult:
        source_query = build_pubmed_query(query)
        size = min(page_size or self.settings.literature_max_results, self.settings.literature_max_results)
        filters = filters or {}
        params: dict[str, Any] = {"db": "pubmed", "term": source_query, "retmode": "json", "retstart": max(0, page - 1) * size, "retmax": size, "tool": self.settings.ncbi_tool}
        if self.settings.ncbi_email:
            params["email"] = self.settings.ncbi_email
        if self.settings.ncbi_api_key:
            params["api_key"] = self.settings.ncbi_api_key
        for key in ("mindate", "maxdate", "datetype"):
            if filters.get(key):
                params[key] = filters[key]
        response = self._request("GET", f"{PUBMED_EUTILS}/esearch.fcgi", params=params)
        result = self._json(response).get("esearchresult", {})
        if not isinstance(result, dict):
            raise LiteratureError("PubMed returned an invalid search response.")
        ids = [str(value) for value in result.get("idlist", []) if str(value).strip()]
        total_count = int(result.get("count", len(ids)) or 0)
        if not ids:
            return SourceSearchResult(PUBMED, source_query, [], total_count)
        fetch_params: dict[str, Any] = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml", "tool": self.settings.ncbi_tool}
        if self.settings.ncbi_email:
            fetch_params["email"] = self.settings.ncbi_email
        if self.settings.ncbi_api_key:
            fetch_params["api_key"] = self.settings.ncbi_api_key
        fetched = self._request("GET", f"{PUBMED_EUTILS}/efetch.fcgi", params=fetch_params)
        try:
            root = element_tree.fromstring(fetched.content)
        except element_tree.ParseError as error:
            raise LiteratureError("PubMed returned invalid XML.") from error
        papers = [paper for article in root.findall(".//PubmedArticle") if (paper := _pubmed_article(article))]
        for paper in papers:
            paper.metadata["search_query"] = source_query
        return SourceSearchResult(PUBMED, source_query, papers, total_count)

    def search_pubmed(self, query: str, *, page: int = 1, page_size: int | None = None, filters: dict[str, Any] | None = None) -> list[NormalizedPaper]:
        return self.search_pubmed_result(query, page=page, page_size=page_size, filters=filters).papers

    def search_europe_pmc_result(self, query: str, *, page: int = 1, page_size: int | None = None, filters: dict[str, Any] | None = None) -> SourceSearchResult:
        source_query = build_europe_pmc_query(query)
        size = min(page_size or self.settings.literature_max_results, self.settings.literature_max_results)
        filters = filters or {}
        params: dict[str, Any] = {"query": source_query, "format": "json", "pageSize": size, "page": max(1, page), "resultType": "core"}
        if filters.get("fromPublicationDate"):
            params["fromPublicationDate"] = filters["fromPublicationDate"]
        if filters.get("toPublicationDate"):
            params["toPublicationDate"] = filters["toPublicationDate"]
        response = self._request("GET", EUROPE_PMC_SEARCH, params=params)
        payload = self._json(response)
        result_list = payload.get("resultList", {})
        papers = [paper for record in result_list.get("result", []) if (paper := _europe_pmc_article(record))]
        for paper in papers:
            paper.metadata["search_query"] = source_query
        return SourceSearchResult(EUROPE_PMC, source_query, papers, int(payload.get("hitCount", len(papers)) or 0))

    def search_europe_pmc(self, query: str, *, page: int = 1, page_size: int | None = None, filters: dict[str, Any] | None = None) -> list[NormalizedPaper]:
        return self.search_europe_pmc_result(query, page=page, page_size=page_size, filters=filters).papers

    def search_all(self, query: str) -> tuple[list[NormalizedPaper], dict[str, str]]:
        papers: list[NormalizedPaper] = []
        failures: dict[str, str] = {}
        for source, search in ((PUBMED, self.search_pubmed), (EUROPE_PMC, self.search_europe_pmc)):
            try:
                papers.extend(search(query))
            except LiteratureError as error:
                failures[source] = type(error).__name__
        return papers, failures

    def search_provider(self, source: str, query: str, *, page: int = 1, page_size: int | None = None, filters: dict[str, Any] | None = None) -> SourceSearchResult:
        """Search a registered provider without coupling callers to its API."""
        normalized_source = source.upper().replace("EUROPEPMC", EUROPE_PMC)
        provider = self.providers.get(normalized_source)
        if provider is None:
            raise LiteratureError(f"Unsupported literature provider: {source}.")
        return provider.search(query, page=page, page_size=page_size, filters=filters)


class PubMedProvider:
    source = PUBMED

    def __init__(self, client: LiteratureClient) -> None:
        self.client = client

    def search(self, query: str, *, page: int = 1, page_size: int | None = None, filters: dict[str, Any] | None = None) -> SourceSearchResult:
        return self.client.search_pubmed_result(query, page=page, page_size=page_size, filters=filters)


class EuropePMCProvider:
    source = EUROPE_PMC

    def __init__(self, client: LiteratureClient) -> None:
        self.client = client

    def search(self, query: str, *, page: int = 1, page_size: int | None = None, filters: dict[str, Any] | None = None) -> SourceSearchResult:
        return self.client.search_europe_pmc_result(query, page=page, page_size=page_size, filters=filters)


def build_search_strategy(research_plan: dict[str, Any], research_question: str) -> dict[str, str]:
    """Derive reproducible source queries from the persisted OmegaClaw plan."""
    concepts = []
    for value in research_plan.get("key_concepts", []):
        cleaned = re.sub(r"[()]+", " ", str(value).replace("‑", "-").replace("–", "-")).strip()
        if cleaned and cleaned.lower() not in {item.lower() for item in concepts}:
            concepts.append(cleaned)
    if not concepts:
        raise LiteratureError("The OmegaClaw plan contains no search concepts.")
    question_tokens = _tokens(research_question)
    anchor_hints = ("disease", "syndrome", "condition", "hbb", "cell")
    intervention_hints = ("crispr", "gene edit", "therapy", "therapeut", "treatment", "cas9")
    anchors = [concept for concept in concepts if any(hint in concept.lower() for hint in anchor_hints)]
    interventions = [concept for concept in concepts if any(hint in concept.lower() for hint in intervention_hints)]
    anchors.sort(key=lambda concept: len(_tokens(concept) & question_tokens), reverse=True)
    interventions.sort(key=lambda concept: len(_tokens(concept) & question_tokens), reverse=True)
    anchors = (anchors or concepts)[:3]
    interventions = (interventions or [concept for concept in concepts if concept not in anchors] or concepts)[:4]
    anchor_terms = [_search_term(concept) for concept in anchors]
    intervention_terms = [_search_term(concept) for concept in interventions]
    anchor_terms = list(dict.fromkeys(item for item in anchor_terms if item))
    intervention_terms = list(dict.fromkeys(item for item in intervention_terms if item))
    pubmed_anchor = " OR ".join(f'"{concept}"[Title/Abstract]' for concept in anchor_terms)
    pubmed_intervention = " OR ".join(f'"{concept}"[Title/Abstract]' for concept in intervention_terms)
    europe_anchor = " OR ".join(f'TITLE_ABS:"{concept}"' for concept in anchor_terms)
    europe_intervention = " OR ".join(f'TITLE_ABS:"{concept}"' for concept in intervention_terms)
    return {
        "pubmed": f"({pubmed_anchor}) AND ({pubmed_intervention})",
        "europe_pmc": f"({europe_anchor}) AND ({europe_intervention})",
    }


def _search_term(concept: str) -> str:
    """Reduce descriptive plan labels to searchable scientific concepts."""
    normalized = re.sub(r"\([^)]*\)", " ", concept.lower().replace("‑", "-").replace("–", "-"))
    normalized = re.sub(r"[^a-z0-9\s-]", " ", normalized).replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if "sickle" in normalized and "cell" in normalized:
        return "sickle cell disease"
    if "crispr" in normalized:
        return "CRISPR"
    if "gene editing" in normalized:
        return "gene editing"
    if "gene therapy" in normalized:
        return "gene therapy"
    if "hbb" in normalized:
        return "HBB"
    generic = {"pathophysiology", "mutation", "variant", "methods", "method", "delivery", "approaches", "approach", "process", "phases", "phase", "issues", "current", "emerging"}
    terms = [token for token in normalized.split() if token not in generic and token not in _STOP_WORDS]
    return " ".join(terms[:4])


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _fallback_key(candidate: NormalizedPaper) -> str:
    author = candidate.authors[0].lower() if candidate.authors else ""
    year = str(candidate.publication_date.year) if candidate.publication_date else ""
    return f"title:{_normalize_title(candidate.title)}|author:{_normalize_title(author)}|year:{year}"


def _identity_key(candidate: NormalizedPaper) -> str:
    if candidate.pmid:
        return f"pmid:{candidate.pmid}"
    if candidate.doi:
        return f"doi:{candidate.doi}"
    if candidate.pmcid:
        return f"pmcid:{candidate.pmcid.lower()}"
    europe_id = candidate.metadata.get("europe_pmc_id")
    if europe_id:
        return f"europe:{str(europe_id).lower()}"
    return _fallback_key(candidate)


def _merge_candidates(primary: NormalizedPaper, duplicate: NormalizedPaper) -> NormalizedPaper:
    primary.metadata["source_records"] = sorted(set(primary.metadata.get("source_records", [])) | set(duplicate.metadata.get("source_records", [])))
    primary.abstract = primary.abstract or duplicate.abstract
    primary.doi = primary.doi or duplicate.doi
    primary.pmid = primary.pmid or duplicate.pmid
    primary.pmcid = primary.pmcid or duplicate.pmcid
    primary.journal = primary.journal or duplicate.journal
    primary.publication_date = primary.publication_date or duplicate.publication_date
    primary.authors = primary.authors or duplicate.authors
    primary.publication_type = primary.publication_type or duplicate.publication_type
    primary.language = primary.language or duplicate.language
    primary.mesh_terms = primary.mesh_terms or duplicate.mesh_terms
    primary.keywords = primary.keywords or duplicate.keywords
    primary.publisher_identifier = primary.publisher_identifier or duplicate.publisher_identifier
    primary.full_text_url = primary.full_text_url or duplicate.full_text_url
    primary.journal_metadata = primary.journal_metadata or duplicate.journal_metadata
    primary.metadata.update({key: value for key, value in duplicate.metadata.items() if value is not None and key not in {"source_records"}})
    if primary.pmid and duplicate.source == PUBMED:
        primary.source = PUBMED
        primary.external_id = primary.pmid
        primary.url = duplicate.url
    return primary


def deduplicate_papers(papers: list[NormalizedPaper]) -> tuple[list[NormalizedPaper], int]:
    unique: dict[str, NormalizedPaper] = {}
    for candidate in papers:
        key = _identity_key(candidate)
        if key in unique:
            _merge_candidates(unique[key], candidate)
        else:
            unique[key] = candidate
    return list(unique.values()), len(papers) - len(unique)


def _find_existing(session: Session, candidate: NormalizedPaper) -> Paper | None:
    clauses = []
    if candidate.doi:
        clauses.append(Paper.doi == candidate.doi)
    if candidate.pmid:
        clauses.append(Paper.pmid == candidate.pmid)
    if candidate.pmcid:
        clauses.append(Paper.pmcid == candidate.pmcid)
    clauses.append((Paper.source == candidate.source) & (Paper.external_id == candidate.external_id))
    if clauses:
        existing = session.scalar(select(Paper).where(or_(*clauses)))
        if existing is not None:
            return existing
    possible = session.scalars(select(Paper).where(Paper.title == candidate.title)).all()
    candidate_key = _fallback_key(candidate)
    for paper in possible:
        other = NormalizedPaper(PUBMED, paper.external_id, paper.title, paper.abstract, paper.authors or [], paper.publication_date, paper.doi, paper.url, paper.paper_metadata or {}, pmid=paper.pmid, pmcid=paper.pmcid)
        if _fallback_key(other) == candidate_key:
            return paper
    return None


def persist_papers(session: Session, investigation_id: object, search_query: str, papers: list[NormalizedPaper], research_search_id: object | None = None, research_search_ids: dict[str, object] | None = None) -> list[Paper]:
    """Persist canonical papers and provenance-rich investigation links."""
    persisted: list[Paper] = []
    unique_papers, _ = deduplicate_papers(papers)
    for candidate in unique_papers:
        existing = _find_existing(session, candidate)
        if existing is None:
            existing = Paper(
                source=candidate.source,
                external_id=candidate.external_id,
                title=candidate.title,
                abstract=candidate.abstract,
                authors=candidate.authors,
                journal=candidate.journal,
                publication_date=candidate.publication_date,
                publication_type=candidate.publication_type,
                language=candidate.language,
                mesh_terms=candidate.mesh_terms,
                keywords=candidate.keywords,
                publisher_identifier=candidate.publisher_identifier,
                full_text_url=candidate.full_text_url,
                journal_metadata=candidate.journal_metadata,
                doi=candidate.doi,
                pmid=candidate.pmid,
                pmcid=candidate.pmcid,
                url=candidate.url,
                paper_metadata=candidate.metadata,
            )
            session.add(existing)
            session.flush()
        else:
            metadata = dict(existing.paper_metadata or {})
            metadata["source_records"] = sorted(set(metadata.get("source_records") or []) | set(candidate.metadata.get("source_records") or []))
            metadata.update({key: value for key, value in candidate.metadata.items() if value is not None and key != "source_records"})
            existing.paper_metadata = metadata
            existing.source = PUBMED if candidate.pmid and candidate.source == PUBMED else existing.source
            existing.title = existing.title or candidate.title
            existing.abstract = existing.abstract or candidate.abstract
            existing.authors = existing.authors or candidate.authors
            existing.journal = existing.journal or candidate.journal
            existing.publication_date = existing.publication_date or candidate.publication_date
            existing.publication_type = existing.publication_type or candidate.publication_type
            existing.language = existing.language or candidate.language
            existing.mesh_terms = existing.mesh_terms or candidate.mesh_terms
            existing.keywords = existing.keywords or candidate.keywords
            existing.publisher_identifier = existing.publisher_identifier or candidate.publisher_identifier
            existing.full_text_url = existing.full_text_url or candidate.full_text_url
            existing.journal_metadata = existing.journal_metadata or candidate.journal_metadata
            existing.doi = existing.doi or candidate.doi
            existing.pmid = existing.pmid or candidate.pmid
            existing.pmcid = existing.pmcid or candidate.pmcid
            existing.url = existing.url or candidate.url

        association = session.scalar(select(InvestigationPaper).where(InvestigationPaper.investigation_id == investigation_id, InvestigationPaper.paper_id == existing.id))
        if association is None:
            association = InvestigationPaper(
                investigation_id=investigation_id,
                paper_id=existing.id,
                source_query=str(candidate.metadata.get("search_query") or search_query),
                source=candidate.source,
                research_search_id=(research_search_ids or {}).get(candidate.source, research_search_id),
            )
            session.add(association)
        elif association.research_search_id is None:
            association.research_search_id = research_search_id
        persisted.append(existing)
    session.flush()
    return persisted


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", value.lower()) if token not in _STOP_WORDS}


def rank_investigation_papers(session: Session, investigation_id: object, research_plan: dict[str, Any]) -> list[InvestigationPaper]:
    concepts = [str(item).strip() for item in research_plan.get("key_concepts", []) if str(item).strip()]
    concept_tokens = {concept: _tokens(concept) for concept in concepts}
    rows = session.execute(select(InvestigationPaper, Paper).join(Paper, Paper.id == InvestigationPaper.paper_id).where(InvestigationPaper.investigation_id == investigation_id)).all()
    ranked: list[tuple[float, InvestigationPaper, str]] = []
    current_year = datetime.now(timezone.utc).year
    for association, paper in rows:
        title_tokens = _tokens(paper.title)
        abstract_tokens = _tokens(paper.abstract or "")
        matched = [concept for concept, tokens in concept_tokens.items() if tokens and (tokens & title_tokens or tokens & abstract_tokens)]
        title_overlap = min(1.0, sum(len(concept_tokens[item] & title_tokens) for item in matched) / max(1, sum(len(value) for value in concept_tokens.values())))
        abstract_overlap = min(1.0, sum(len(concept_tokens[item] & abstract_tokens) for item in matched) / max(1, sum(len(value) for value in concept_tokens.values())))
        recency = max(0.0, 1.0 - max(0, current_year - paper.publication_date.year) / 10) if paper.publication_date else 0.0
        score = min(1.0, 0.6 * title_overlap + 0.3 * abstract_overlap + 0.1 * recency)
        reason = f"Matched {len(matched)} of {len(concepts)} OmegaClaw plan concepts in source title/abstract; recency is a secondary ordering signal."
        ranked.append((score, association, reason))
    ranked.sort(key=lambda item: (-item[0], str(item[1].paper_id)))
    for position, (score, association, reason) in enumerate(ranked, start=1):
        association.relevance_score = round(score, 4)
        association.relevance_reason = reason
        association.rank = position
    session.flush()
    return [association for _, association, _ in ranked]

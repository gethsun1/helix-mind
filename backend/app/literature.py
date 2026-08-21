"""Real, source-attributed scientific literature retrieval for HelixMind."""

from __future__ import annotations

import re
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import InvestigationPaper, Paper


PUBMED_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


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
    url: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _text(node: element_tree.Element | None) -> str | None:
    if node is None:
        return None
    value = "".join(node.itertext()).strip()
    return value or None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for candidate in (value, value[:10], value[:7], value[:4]):
        try:
            return date.fromisoformat(candidate if len(candidate) == 10 else f"{candidate}-01" if len(candidate) == 7 else f"{candidate}-01-01")
        except ValueError:
            pass
    return None


def _clean_doi(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().removeprefix("https://doi.org/") or None


def build_pubmed_query(question: str) -> str:
    """Create a conservative high-signal query for known scientific entities.

    Broader planning will later supply richer query plans. This intentionally
    avoids pretending that a natural-language question is already a valid
    PubMed query syntax.
    """
    normalized = question.lower()
    has_crispr = "crispr" in normalized
    has_sickle_cell = bool(re.search(r"sickle[- ]cell", normalized))
    if has_crispr and has_sickle_cell:
        return '("sickle cell disease"[Title/Abstract]) AND (CRISPR[Title/Abstract] OR "gene editing"[Title/Abstract])'
    return question


def build_europe_pmc_query(question: str) -> str:
    normalized = question.lower()
    has_crispr = "crispr" in normalized
    has_sickle_cell = bool(re.search(r"sickle[- ]cell", normalized))
    if has_crispr and has_sickle_cell:
        return '(TITLE_ABS:"sickle cell disease") AND (TITLE_ABS:CRISPR OR TITLE_ABS:"gene editing")'
    return question


def _pubmed_article(article: element_tree.Element) -> NormalizedPaper | None:
    pmid = _text(article.find(".//PMID"))
    title = _text(article.find(".//ArticleTitle"))
    if not pmid or not title:
        return None

    abstract_parts = [_text(node) for node in article.findall(".//Abstract/AbstractText")]
    authors = []
    for author in article.findall(".//Author"):
        collective = _text(author.find("CollectiveName"))
        if collective:
            authors.append(collective)
            continue
        family = _text(author.find("LastName"))
        initials = _text(author.find("Initials"))
        if family:
            authors.append(" ".join(part for part in (family, initials) if part))

    doi = None
    for identifier in article.findall(".//ArticleId"):
        if identifier.attrib.get("IdType") == "doi":
            doi = _clean_doi(_text(identifier))
            break

    pub_date = article.find(".//Article/Journal/JournalIssue/PubDate")
    year = _text(pub_date.find("Year")) if pub_date is not None else None
    month = _text(pub_date.find("Month")) if pub_date is not None else None
    day = _text(pub_date.find("Day")) if pub_date is not None else None
    date_value = _parse_date("-".join(part for part in (year, month, day) if part))
    if date_value is None:
        medline_date = _text(pub_date.find("MedlineDate")) if pub_date is not None else None
        year_match = re.search(r"\d{4}", medline_date or "")
        date_value = _parse_date(year_match.group(0) if year_match else None)

    return NormalizedPaper(
        source="pubmed",
        external_id=pmid,
        title=title,
        abstract="\n".join(part for part in abstract_parts if part) or None,
        authors=authors,
        publication_date=date_value,
        doi=doi,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        metadata={"pmid": pmid, "source_records": ["pubmed"]},
    )


def _europe_pmc_article(record: dict[str, Any]) -> NormalizedPaper | None:
    title = (record.get("title") or "").strip()
    source_id = (record.get("id") or "").strip()
    source_name = (record.get("source") or "").strip().lower()
    pmid = (record.get("pmid") or "").strip()
    if not title or not source_id:
        return None

    # A Europe PMC record with a PMID is the same canonical paper as PubMed.
    source = "pubmed" if pmid else "europepmc"
    external_id = pmid or f"{source_name}:{source_id}"
    doi = _clean_doi(record.get("doi"))
    authors = [value.strip() for value in (record.get("authorString") or "").split(",") if value.strip()]
    metadata = {
        "europe_pmc_id": source_id,
        "europe_pmc_source": source_name,
        "pmid": pmid or None,
        "journal": record.get("journalTitle"),
        "source_records": ["europepmc"],
    }
    return NormalizedPaper(
        source=source,
        external_id=external_id,
        title=title,
        abstract=(record.get("abstractText") or "").strip() or None,
        authors=authors,
        publication_date=_parse_date(record.get("firstPublicationDate") or record.get("firstIndexDate")),
        doi=doi,
        url=f"https://europepmc.org/article/{source_name}/{source_id}",
        metadata=metadata,
    )


class LiteratureClient:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client or httpx.Client(timeout=self.settings.literature_timeout_seconds, follow_redirects=True)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def search_pubmed(self, question: str) -> list[NormalizedPaper]:
        source_query = build_pubmed_query(question)
        params: dict[str, Any] = {
            "db": "pubmed",
            "term": source_query,
            "retmode": "json",
            "retmax": self.settings.literature_max_results,
            "tool": self.settings.ncbi_tool,
        }
        if self.settings.ncbi_email:
            params["email"] = self.settings.ncbi_email
        response = self.client.get(f"{PUBMED_EUTILS}/esearch.fcgi", params=params)
        response.raise_for_status()
        ids = response.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        fetch_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml", "tool": self.settings.ncbi_tool}
        if self.settings.ncbi_email:
            fetch_params["email"] = self.settings.ncbi_email
        response = self.client.get(f"{PUBMED_EUTILS}/efetch.fcgi", params=fetch_params)
        response.raise_for_status()
        try:
            root = element_tree.fromstring(response.content)
        except element_tree.ParseError as error:
            raise LiteratureError("PubMed returned invalid XML.") from error
        papers = [paper for article in root.findall(".//PubmedArticle") if (paper := _pubmed_article(article))]
        for paper in papers:
            paper.metadata["search_query"] = source_query
        return papers

    def search_europe_pmc(self, question: str) -> list[NormalizedPaper]:
        source_query = build_europe_pmc_query(question)
        response = self.client.get(
            EUROPE_PMC_SEARCH,
            params={"query": source_query, "format": "json", "pageSize": self.settings.literature_max_results, "resultType": "core"},
        )
        response.raise_for_status()
        papers = [paper for record in response.json().get("resultList", {}).get("result", []) if (paper := _europe_pmc_article(record))]
        for paper in papers:
            paper.metadata["search_query"] = source_query
        return papers

    def search_all(self, question: str) -> tuple[list[NormalizedPaper], dict[str, str]]:
        papers: list[NormalizedPaper] = []
        failures: dict[str, str] = {}
        for source, search in (("pubmed", self.search_pubmed), ("europepmc", self.search_europe_pmc)):
            try:
                papers.extend(search(question))
            except (httpx.HTTPError, LiteratureError, ValueError) as error:
                failures[source] = type(error).__name__
        return papers, failures


def persist_papers(session: Session, investigation_id: object, question: str, papers: list[NormalizedPaper]) -> list[Paper]:
    """Deduplicate by canonical source/id and DOI, then preserve source provenance."""
    persisted: list[Paper] = []
    seen: set[object] = set()
    for candidate in papers:
        existing = session.scalar(
            select(Paper).where(
                or_(
                    (Paper.source == candidate.source) & (Paper.external_id == candidate.external_id),
                    Paper.doi == candidate.doi if candidate.doi else False,
                )
            )
        )
        if existing is None:
            existing = Paper(
                source=candidate.source,
                external_id=candidate.external_id,
                title=candidate.title,
                abstract=candidate.abstract,
                authors=candidate.authors,
                publication_date=candidate.publication_date,
                doi=candidate.doi,
                url=candidate.url,
                paper_metadata=candidate.metadata,
            )
            session.add(existing)
            session.flush()
        else:
            metadata = dict(existing.paper_metadata or {})
            sources = set(metadata.get("source_records") or []) | set(candidate.metadata.get("source_records") or [])
            metadata["source_records"] = sorted(sources)
            metadata.update({key: value for key, value in candidate.metadata.items() if value is not None})
            existing.paper_metadata = metadata
            existing.abstract = existing.abstract or candidate.abstract
            existing.doi = existing.doi or candidate.doi

        if existing.id not in seen:
            association = session.scalar(
                select(InvestigationPaper).where(
                    InvestigationPaper.investigation_id == investigation_id,
                    InvestigationPaper.paper_id == existing.id,
                )
            )
            if association is None:
                session.add(InvestigationPaper(investigation_id=investigation_id, paper_id=existing.id, source_query=question))
            persisted.append(existing)
            seen.add(existing.id)
    session.flush()
    return persisted

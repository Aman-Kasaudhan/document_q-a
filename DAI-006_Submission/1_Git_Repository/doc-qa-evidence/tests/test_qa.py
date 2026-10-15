import json
import pytest
from src.config import PROJECT_ROOT
from src.models import ProviderResult
from src.providers import ProviderError
from src.providers.base import AnswerProvider
from src.providers.ollama import OllamaProvider
from src.qa import QAService

EVAL = json.loads((PROJECT_ROOT / "data" / "eval_questions.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("item", EVAL, ids=[i["id"] for i in EVAL])
def test_eval_questions(loaded, settings, item):
    """Every answerable question cites the right document; every unanswerable one is refused."""
    ans = QAService(loaded, settings).ask(item["question"])
    if item["answerable"]:
        assert ans.status == "answered"
        assert ans.primary_source.filename == item["expected_source"]
        assert item["expected_contains"].lower() in ans.answer.lower()
        assert ans.primary_source.text                       # the evidence chunk is returned
    else:
        assert ans.status=="insufficient_evidence"
        assert ans.answer is None


def test_near_miss_entity_is_refused(loaded, settings):
    """Keywords 'plan cost month' match the Pro plan, but 'Enterprise' exists nowhere."""
    ans = QAService(loaded, settings).ask("How much does the Enterprise plan cost per month?")
    assert ans.status == "insufficient_evidence"
    assert ans.note=="unknown_entity_not_in_documents:enterprise"
    assert ans.top_score >= settings.min_score          # keyword coverage alone would have passed


def test_empty_question_is_insufficient(loaded, settings):
    ans = QAService(loaded, settings).ask("   ")
    assert ans.status == "insufficient_evidence" and ans.note == "empty_question"


def test_question_with_only_stopwords_is_insufficient(loaded, settings):
    assert QAService(loaded, settings).ask("what is the").status == "insufficient_evidence"


def test_empty_database_never_invents_an_answer(conn, settings):
    ans = QAService(conn, settings).ask("How many days of annual leave do I get?")
    assert ans.status == "insufficient_evidence"


def test_queries_are_audited(loaded, settings):
    qa = QAService(loaded, settings)
    qa.ask("How long must passwords be?")
    qa.ask("What is the CEO's salary?")
    rows = loaded.execute("SELECT status FROM query_log ORDER BY query_id").fetchall()
    assert [r["status"] for r in rows] == ["answered", "insufficient_evidence"]


class ExplodingProvider(AnswerProvider):
    name = "exploding"

    def answer(self, question, chunks):
        raise ProviderError("simulated timeout")


class RefusingProvider(AnswerProvider):
    name = "refusing"

    def answer(self, question, chunks):
        return ProviderResult(answer=None, insufficient=True, provider=self.name)


def test_provider_failure_falls_back_to_extractive(loaded, settings):
    ans = QAService(loaded, settings, provider=ExplodingProvider()).ask("How long must passwords be?")
    assert ans.status == "answered" and ans.provider == "extractive"
    assert "provider_failed_fallback_used" in ans.note and "14 characters" in ans.answer


def test_model_refusal_is_respected(loaded, settings):
    ans = QAService(loaded, settings, provider=RefusingProvider()).ask("How long must passwords be?")
    assert ans.status == "insufficient_evidence"


# ---- Ollama provider: response handling with a fake HTTP layer (no server needed) ----

class FakeResponse:
    def __init__(self, payload=None, status=200, bad_json=False):
        self.status_code, self._payload, self._bad = status, payload, bad_json

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._payload


def make_provider(response=None, exc=None):
    def post(url, json, timeout):
        if exc:
            raise exc
        return response
    return OllamaProvider("http://localhost:11434", "test-model", 1.0, http_post=post)


def chunks_for(loaded, settings, q="How long must passwords be?"):
    from src.retrieval import retrieve
    return retrieve(loaded, q, settings.top_k)


def test_ollama_valid_answer_with_citation(loaded, settings):
    chunks = chunks_for(loaded, settings)
    prov = make_provider(FakeResponse({"response": "Passwords must be 14 characters long. [1]"}))
    res = prov.answer("How long must passwords be?", chunks)
    assert res.answer == "Passwords must be 14 characters long." and res.chunk_id == chunks[0].chunk_id


@pytest.mark.parametrize("response", [
    FakeResponse({"response": ""}),                          # empty output
    FakeResponse({"response": "It is 14 characters."}),      # no citation
    FakeResponse({"response": "It is 14. [9]"}),             # citation to a passage that doesn't exist
    FakeResponse({"unexpected": "shape"}),                   # schema problem
    FakeResponse(bad_json=True),                             # invalid JSON
    FakeResponse({"response": "x"}, status=500),             # server error
])
def test_ollama_bad_responses_raise_provider_error(loaded, settings, response):
    with pytest.raises(ProviderError):
        make_provider(response).answer("q", chunks_for(loaded, settings))


def test_ollama_timeout_raises_provider_error(loaded, settings):
    with pytest.raises(ProviderError):
        make_provider(exc=TimeoutError("timed out")).answer("q", chunks_for(loaded, settings))


def test_ollama_refusal_token_means_insufficient(loaded, settings):
    res = make_provider(FakeResponse({"response": "INSUFFICIENT_EVIDENCE"})).answer(
        "q", chunks_for(loaded, settings))
    assert res.insufficient


def test_service_survives_broken_ollama_end_to_end(loaded, settings):
    broken = make_provider(exc=ConnectionError("refused"))
    ans = QAService(loaded, settings, provider=broken).ask("How long must passwords be?")
    assert ans.status == "answered" and ans.provider == "extractive"


def test_reference_sql_file_is_valid(loaded):
    from src.config import PROJECT_ROOT
    sql = (PROJECT_ROOT / "sql" / "queries.sql").read_text(encoding="utf-8")
    statements = [s.strip() for s in sql.split(";") if "SELECT" in s.upper()]
    assert len(statements) >= 6
    for stmt in statements:
        loaded.execute(stmt, {"q": '"leave"'}).fetchall()
    orphan = loaded.execute(statements[-1]).fetchall()
    assert orphan == []                                   # integrity query: every chunk is indexed

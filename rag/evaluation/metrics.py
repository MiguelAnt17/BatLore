"""RAG evaluation metrics: retrieval (P@k, R@k, Hit Rate, MRR), LLM-as-judge, Ragas and Token F1."""

import math
import os
import re
import string
import unicodedata
from collections import Counter


# 1-3. Retrieval (P@k, R@k, Hit Rate, MRR)
def precision_at_k(relevance, k):
    """P@k = |relevant in top-k| / k."""
    if k <= 0:
        raise ValueError("k must be >= 1")
    return sum(relevance[:k]) / k


def recall_at_k(hit_ids_per_rank, relevant_ids, k):
    """R@k = |relevant docs found in top-k| / |relevant docs|."""
    if not relevant_ids:
        return float("nan")
    found = set().union(*hit_ids_per_rank[:k]) if hit_ids_per_rank[:k] else set()
    return len(found & set(relevant_ids)) / len(set(relevant_ids))


def hit_rate_at_k(relevance, k):
    """Hit@k = 1 if at least one relevant chunk is in the top-k, else 0."""
    return float(any(relevance[:k]))


def reciprocal_rank(relevance, k=None):
    """1 / rank of the first relevant chunk, or 0."""
    ranked = relevance if k is None else relevance[:k]
    for rank, rel in enumerate(ranked, start=1):
        if rel:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(relevance_lists, k=None):
    """Mean of the reciprocal ranks."""
    if not relevance_lists:
        return float("nan")
    return sum(reciprocal_rank(r, k) for r in relevance_lists) / len(relevance_lists)


# 8. Token F1
_ARTICLES = {
    # English
    "a", "an", "the",
    # Portuguese
    "o", "os", "as", "um", "uma", "uns", "umas",
}
_PUNCTUATION = set(string.punctuation) | {"«", "»", "“", "”", "‘", "’", "–", "—", "…"}


def normalize_answer(text):
    """SQuAD-style normalisation."""
    text = unicodedata.normalize("NFC", strip_thinking(text).lower())
    text = "".join(" " if ch in _PUNCTUATION else ch for ch in text)
    return " ".join(tok for tok in text.split() if tok not in _ARTICLES)


def token_f1(prediction, reference):
    """Returns (f1, precision, recall) over token bags."""
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(reference).split()
    if not pred_tokens or not gold_tokens:
        score = float(pred_tokens == gold_tokens)
        return score, score, score
    common = sum((Counter(pred_tokens) & Counter(gold_tokens)).values())
    if common == 0:
        return 0.0, 0.0, 0.0
    precision = common / len(pred_tokens) # De todas as palavras que o modelo gerou, qual percentagem coincide com a resposta esperada
    recall = common / len(gold_tokens) # De todas as palavras que estavam na resposta esperada, quantas é que o modelo gerou?
    return 2 * precision * recall / (precision + recall), precision, recall


# LLM-as-judge: "total rating" prompt from the course slides (Hugging Face LLM-judge cookbook).
# Question and answer only, no reference answer.
JUDGE_PROMPT = """You will be given a user_question and system_answer couple. Your task is to provide a 'total rating' scoring how well the system_answer answers the user concerns expressed in the user_question. Give your answer as a float on a scale of 0 to 10, where 0 means that the system_answer is not helpful at all, and 10 means that the answer completely and helpfully addresses the question.

Provide your feedback as follows:

Feedback:::
Total rating: (your rating, as a float between 0 and 10)

Now here are the question and answer.

Question: {question}
Answer: {answer}

Feedback:::
Total rating: """

_RATING_RE = re.compile(r"Total rating:\s*([0-9]+(?:[.,][0-9]+)?)", re.IGNORECASE)
_NUMBER_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)")


def extract_rating(text):
    """0-10 rating from the judge's reply; NaN if there is no number."""
    match = _RATING_RE.search(text or "") or _NUMBER_RE.search(text or "")
    if not match:
        return math.nan
    return min(10.0, max(0.0, float(match.group(1).replace(",", "."))))


# Ragas correctness (pass/fail DiscreteMetric), prompt from the course slides and the Ragas
# "evaluate and improve RAG" guide. The guide asks for accuracy "based on the provided context"
# without passing it; here the context is the chunks given to the generator.
CORRECTNESS_PROMPT = """Compare the model response to the expected answer and determine if it's correct.

Consider the response correct if it:
1. Contains the key information from the expected answer
2. Is factually accurate based on the provided context
3. Adequately addresses the question asked

Return 'pass' if the response is correct, 'fail' if it's incorrect.

Question: {question}
Expected Answer: {expected_answer}
Context: {context}
Model Response: {response}

Evaluation:"""


def make_correctness_metric():
    """Ragas DiscreteMetric 'correctness' (pass/fail). Lazy import: ragas is heavy."""
    from ragas.metrics import DiscreteMetric

    return DiscreteMetric(name="correctness", prompt=CORRECTNESS_PROMPT, allowed_values=["pass", "fail"])


# 4-7. Ragas
OLLAMA_URL = "http://localhost:11434/v1"


class RagasEvaluator:
    """Ragas metrics with an OpenAI-compatible judge (local Ollama by default)."""

    def __init__(self, judge_model="qwen2.5:7b",
                 embedding_model="sentence-transformers/all-mpnet-base-v2",
                 n_questions=3, base_url=OLLAMA_URL, api_key="ollama", reasoning_effort="none"):
        # Lazy imports
        os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
        from openai import AsyncOpenAI
        from ragas.embeddings.huggingface_provider import HuggingFaceEmbeddings
        from ragas.llms import llm_factory
        from ragas.metrics.collections import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

        client = AsyncOpenAI(base_url=base_url, api_key=api_key)  # Ollama ignores the key
        # Deterministic, no thinking (reasoning_effort=None leaves it to the provider)
        extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
        llm = llm_factory(judge_model, provider="openai", client=client,
                          temperature=0, max_tokens=4096, **extra)
        embeddings = HuggingFaceEmbeddings(model=embedding_model)

        self.context_precision = ContextPrecision(llm=llm)
        # O LLM avalia cada chunk do contexto recuperado para verificar se ele é relevante para responder à 
        # pergunta/referência e analisa a sua posição na lista.

        self.context_recall = ContextRecall(llm=llm)
        # O LLM quebra a resposta de referência (ground truth) em afirmações atómicas e 
        # verifica se cada uma delas pode ser deduzida a partir dos chunks de contexto recuperados.

        self.faithfulness = Faithfulness(llm=llm)
        # O LLM extrai todas as afirmações feitas na resposta gerada pelo modelo (response) e verifica 
        # se cada uma delas é estritamente sustentada pelo contexto fornecido (retrieved_contexts).

        self.answer_relevance = AnswerRelevancy(llm=llm, embeddings=embeddings, strictness=n_questions)

    async def ascore(self, question, reference, response, contexts, only=None):
        """({metric: score}, {metric: error}); failures are NaN. only: metric subset."""
        calls = {
            "ContextPrecision": lambda: self.context_precision.ascore(
                user_input=question, reference=reference, retrieved_contexts=contexts),
            "ContextRecall": lambda: self.context_recall.ascore(
                user_input=question, retrieved_contexts=contexts, reference=reference),
            "Faithfulness": lambda: self.faithfulness.ascore(
                user_input=question, response=response, retrieved_contexts=contexts),
            "AnswerRelevance": lambda: self.answer_relevance.ascore(
                user_input=question, response=response),
        }
        if only is not None:
            calls = {name: call for name, call in calls.items() if name in only}
        scores, errors = {}, {}
        for name, call in calls.items():
            try:
                scores[name] = float((await call()).value)
            except Exception as e:
                scores[name] = math.nan
                errors[name] = f"{type(e).__name__}: {e}"
        return scores, errors


# Helpers
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_thinking(text):
    """Removes <think>...</think> blocks."""
    return _THINK_RE.sub("", text or "").strip()


def nanmean(values):
    """Mean ignoring NaN/None; NaN if nothing is left."""
    vals = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return sum(vals) / len(vals) if vals else float("nan")

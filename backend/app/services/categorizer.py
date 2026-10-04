"""ML transaction categorisation.

TF-IDF over character n-grams (robust to "SWIGY", "ZOMATO*1234", truncated narrations) plus word
n-grams, fed into a logistic regression. Each user gets their own model: the seed dataset plus that
user's corrections, weighted heavily so the model adapts to how *their* bank writes narrations.
An exact-merchant memory makes a correction apply instantly to every matching transaction.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from .merchants import clean_narration, merchant_key
from .training_data import build_dataset

CORRECTION_WEIGHT = 8.0
MIN_CONFIDENCE = 0.25  # below this we say "Other" rather than guess


def _make_pipeline() -> Pipeline:
    features = FeatureUnion([
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=1)),
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True)),
    ])
    return Pipeline([("features", features), ("clf", LogisticRegression(C=8.0, max_iter=2000))])


@dataclass
class Prediction:
    category: str
    confidence: float


class Categorizer:
    def __init__(self, corrections: list[tuple[str, str]] | None = None):
        texts, labels, _ = build_dataset()
        weights = [1.0] * len(texts)
        self.memory: dict[str, str] = {}
        for text, label in corrections or []:
            texts.append(text)
            labels.append(label)
            weights.append(CORRECTION_WEIGHT)
            self.memory[merchant_key(text)] = label
        self.model = _make_pipeline()
        self.model.fit([clean_narration(t) for t in texts], labels, clf__sample_weight=np.array(weights))

    def predict(self, texts: list[str], amounts: list[float] | None = None) -> list[Prediction]:
        if not texts:
            return []
        probs = self.model.predict_proba([clean_narration(t) for t in texts])
        classes = self.model.classes_
        out = []
        for i, text in enumerate(texts):
            remembered = self.memory.get(merchant_key(text))
            if remembered:
                out.append(Prediction(remembered, 1.0))
                continue
            row = probs[i].copy()
            # Direction of money is a strong signal: a credit is never "Food & Dining".
            if amounts is not None:
                credit_ok = {"Salary", "Other Income", "Transfers", "Investments"}
                for j, c in enumerate(classes):
                    if amounts[i] > 0 and c not in credit_ok:
                        row[j] *= 0.15
                    elif amounts[i] < 0 and c in ("Salary", "Other Income"):
                        row[j] *= 0.15
                row /= row.sum()
            j = int(np.argmax(row))
            conf = float(row[j])
            out.append(Prediction(str(classes[j]) if conf >= MIN_CONFIDENCE else "Other", round(conf, 3)))
        return out


_cache: dict[int, tuple[int, Categorizer]] = {}
_lock = threading.Lock()


def get_categorizer(user_id: int, corrections: list[tuple[str, str]]) -> Categorizer:
    """Per-user model, retrained only when that user's corrections change."""
    key = hash(tuple(corrections))
    with _lock:
        cached = _cache.get(user_id)
        if cached and cached[0] == key:
            return cached[1]
    model = Categorizer(corrections)
    with _lock:
        _cache[user_id] = (key, model)
    return model


def evaluate_holdout(seed: int = 0) -> dict:
    """Two honest scores.

    known_merchants: new narrations (different formats/ref numbers) of merchants seen in training.
    unseen_merchants: grouped split, so test merchants never appear in training at all. Brand names
    like "ZEPTO" carry no meaning on their own, which is why the user-correction loop exists.
    """
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import GroupShuffleSplit, train_test_split

    texts, labels, merchants = build_dataset()
    clean = [clean_narration(t) for t in texts]

    def score(train_idx, test_idx):
        model = _make_pipeline()
        model.fit([clean[i] for i in train_idx], [labels[i] for i in train_idx])
        pred = model.predict([clean[i] for i in test_idx])
        truth = [labels[i] for i in test_idx]
        return {"accuracy": round(float(accuracy_score(truth, pred)), 3),
                "macro_f1": round(float(f1_score(truth, pred, average="macro")), 3),
                "test_size": len(test_idx)}

    idx = list(range(len(texts)))
    tr, te = train_test_split(idx, test_size=0.25, random_state=seed, stratify=labels)
    gtr, gte = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
                    .split(texts, labels, groups=merchants))
    return {"known_merchants": score(tr, te), "unseen_merchants": score(gtr, gte)}

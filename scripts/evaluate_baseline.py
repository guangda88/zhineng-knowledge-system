"""
Baseline metrics evaluation script for fine-tuning.

Measures:
1. MRR@10 and Recall@5 on val_pairs.jsonl (embedding retrieval)
2. Intent classification F1 (macro) on test.jsonl

Uses bge-small-zh-v1.5 model. GPU if available, CPU fallback.
"""
import json
import os
import sys
import time
import numpy as np
from pathlib import Path
from collections import defaultdict

TRAINING_DIR = Path(__file__).parent.parent / "data" / "training"
MODEL_PATH = "/data/models/bge-small-zh"


def load_embedding_pairs(filepath):
    """Load anchor-positive pairs from jsonl."""
    pairs = []
    with open(filepath) as f:
        for line in f:
            d = json.loads(line)
            pairs.append({
                "anchor": d["anchor"],
                "positive": d["positive"],
                "doc_id": d.get("doc_id"),
                "category": d.get("category", "unknown"),
                "pair_type": d.get("pair_type", "unknown"),
            })
    return pairs


def load_intent_data(filepath):
    """Load intent classifier data from jsonl."""
    data = []
    with open(filepath) as f:
        for line in f:
            d = json.loads(line)
            data.append({"query": d["query"], "intent": d["intent"]})
    return data


def evaluate_retrieval(pairs, model, batch_size=64):
    """Evaluate MRR@10 and Recall@5 on val pairs.

    For each anchor, rank all positives by cosine similarity.
    The correct positive is the one from the same pair.
    """
    print(f"\n{'='*60}")
    print(f"Retrieval Evaluation ({len(pairs)} pairs)")
    print(f"{'='*60}")

    anchors = [p["anchor"] for p in pairs]
    positives = [p["positive"] for p in pairs]

    t0 = time.time()
    print(f"Encoding {len(anchors)} anchors...")
    anchor_embs = model.encode(anchors, batch_size=batch_size, show_progress_bar=True,
                               normalize_embeddings=True)

    print(f"Encoding {len(positives)} positives...")
    pos_embs = model.encode(positives, batch_size=batch_size, show_progress_bar=True,
                            normalize_embeddings=True)
    encode_time = time.time() - t0
    print(f"Encoding time: {encode_time:.1f}s")

    # Compute similarity matrix: (N, N) — anchor i vs positive j
    sim_matrix = np.dot(anchor_embs, pos_embs.T)

    # For each anchor i, rank all positives by similarity
    # The correct positive for anchor i is positive i (same index)
    mrr_scores = []
    recall_at_5 = []
    recall_at_10 = []

    for i in range(len(pairs)):
        sims = sim_matrix[i]
        ranked_indices = np.argsort(-sims)
        rank_of_correct = np.where(ranked_indices == i)[0][0] + 1

        # MRR
        mrr_scores.append(1.0 / rank_of_correct)

        # Recall@5: is correct in top 5?
        recall_at_5.append(1.0 if rank_of_correct <= 5 else 0.0)

        # Recall@10: is correct in top 10?
        recall_at_10.append(1.0 if rank_of_correct <= 10 else 0.0)

    mrr_at_10 = np.mean(mrr_scores)
    r5 = np.mean(recall_at_5)
    r10 = np.mean(recall_at_10)

    # Also compute by category
    cat_metrics = defaultdict(lambda: {"mrr": [], "r5": [], "r10": []})
    for i, p in enumerate(pairs):
        cat = p["category"]
        cat_metrics[cat]["mrr"].append(mrr_scores[i])
        cat_metrics[cat]["r5"].append(recall_at_5[i])
        cat_metrics[cat]["r10"].append(recall_at_10[i])

    print(f"\n--- Overall ---")
    print(f"MRR@10:   {mrr_at_10:.4f}")
    print(f"Recall@5: {r5:.4f}")
    print(f"Recall@10:{r10:.4f}")

    print(f"\n--- By Category ---")
    print(f"{'Category':<12} {'Count':>6} {'MRR@10':>8} {'R@5':>8} {'R@10':>8}")
    for cat in sorted(cat_metrics.keys(), key=lambda c: -len(cat_metrics[c]["mrr"])):
        m = cat_metrics[cat]
        n = len(m["mrr"])
        print(f"{cat:<12} {n:>6} {np.mean(m['mrr']):>8.4f} {np.mean(m['r5']):>8.4f} {np.mean(m['r10']):>8.4f}")

    return {"mrr_at_10": mrr_at_10, "recall_at_5": r5, "recall_at_10": r10}


def evaluate_intent_classification(test_data, model, batch_size=64):
    """Evaluate intent classification using embedding similarity.

    Baseline approach: encode all training queries per intent, compute centroid,
    classify test queries by nearest centroid (zero-shot via embedding).
    """
    from sklearn.metrics import f1_score, classification_report

    # Load training data for centroids
    train_data = load_intent_data(TRAINING_DIR / "intent_classifier" / "train.jsonl")

    print(f"\n{'='*60}")
    print(f"Intent Classification Evaluation")
    print(f"{'='*60}")

    # Group train by intent
    intent_queries = defaultdict(list)
    for d in train_data:
        intent_queries[d["intent"]].append(d["query"])

    intents = sorted(intent_queries.keys())
    print(f"Intents: {intents}")
    print(f"Train: {len(train_data)}, Test: {len(test_data)}")

    # Encode all training queries
    all_train_queries = []
    intent_indices = {}
    idx = 0
    for intent in intents:
        queries = intent_queries[intent]
        all_train_queries.extend(queries)
        intent_indices[intent] = (idx, idx + len(queries))
        idx += len(queries)

    t0 = time.time()
    print(f"Encoding {len(all_train_queries)} train queries...")
    train_embs = model.encode(all_train_queries, batch_size=batch_size,
                              show_progress_bar=True, normalize_embeddings=True)

    # Compute centroids
    centroids = []
    for intent in intents:
        start, end = intent_indices[intent]
        centroid = np.mean(train_embs[start:end], axis=0)
        centroid = centroid / np.linalg.norm(centroid)
        centroids.append(centroid)
    centroids = np.array(centroids)

    # Encode test queries
    test_queries = [d["query"] for d in test_data]
    test_labels = [d["intent"] for d in test_data]
    print(f"Encoding {len(test_queries)} test queries...")
    test_embs = model.encode(test_queries, batch_size=batch_size,
                             show_progress_bar=True, normalize_embeddings=True)
    encode_time = time.time() - t0
    print(f"Encoding time: {encode_time:.1f}s")

    # Classify by nearest centroid
    sim_to_centroids = np.dot(test_embs, centroids.T)
    pred_indices = np.argmax(sim_to_centroids, axis=1)
    pred_labels = [intents[i] for i in pred_indices]

    # Metrics
    f1_macro = f1_score(test_labels, pred_labels, average="macro")
    f1_weighted = f1_score(test_labels, pred_labels, average="weighted")
    accuracy = np.mean([p == t for p, t in zip(pred_labels, test_labels)])

    print(f"\n--- Intent Classification (centroid-based zero-shot) ---")
    print(f"Accuracy:     {accuracy:.4f}")
    print(f"F1 (macro):   {f1_macro:.4f}")
    print(f"F1 (weighted):{f1_weighted:.4f}")

    print(f"\n--- Classification Report ---")
    print(classification_report(test_labels, pred_labels, digits=4))

    return {"f1_macro": f1_macro, "f1_weighted": f1_weighted, "accuracy": accuracy}


def main():
    print("Loading model...")
    from sentence_transformers import SentenceTransformer

    device = os.environ.get("EVAL_DEVICE", "auto")
    if device == "auto":
        device = "cuda" if _cuda_available() else "cpu"
    print(f"Device: {device}")

    model = SentenceTransformer(MODEL_PATH, device=device)
    print(f"Model loaded: {model.get_sentence_embedding_dimension()}d embeddings")

    # 1. Retrieval metrics
    val_pairs = load_embedding_pairs(TRAINING_DIR / "embedding_pairs" / "val_pairs.jsonl")
    retrieval_results = evaluate_retrieval(val_pairs, model)

    # 2. Intent classification
    test_data = load_intent_data(TRAINING_DIR / "intent_classifier" / "test.jsonl")
    intent_results = evaluate_intent_classification(test_data, model)

    # Summary
    print(f"\n{'='*60}")
    print(f"BASELINE SUMMARY")
    print(f"{'='*60}")
    print(f"MRR@10:        {retrieval_results['mrr_at_10']:.4f}")
    print(f"Recall@5:      {retrieval_results['recall_at_5']:.4f}")
    print(f"Recall@10:     {retrieval_results['recall_at_10']:.4f}")
    print(f"Intent F1(macro): {intent_results['f1_macro']:.4f}")
    print(f"Intent Accuracy:  {intent_results['accuracy']:.4f}")

    # Save results
    results = {
        "model": "BAAI/bge-small-zh-v1.5 (baseline, no fine-tuning)",
        "device": device,
        "retrieval": retrieval_results,
        "intent_classification": intent_results,
    }
    output_path = TRAINING_DIR / "baseline_metrics.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {output_path}")


def _cuda_available():
    try:
        import torch
        avail = torch.cuda.is_available()
        if avail:
            free_mem = torch.cuda.mem_get_info(0)[0] / 1024**2
            print(f"GPU free memory: {free_mem:.0f} MiB")
            if free_mem < 200:
                print("Not enough GPU memory (<200 MiB), using CPU")
                return False
        return avail
    except Exception:
        return False


if __name__ == "__main__":
    main()

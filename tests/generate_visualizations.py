"""
Generates a confusion matrix and per-class precision/recall/F1 bar chart from
the Triage Agent's real test-set evaluation. Saves as PNG for the README/demo.
"""
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.triage_agent import TriageAgent, SEVERITY_MAP

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
CATEGORIES = list(SEVERITY_MAP.keys())

def plot_confusion_matrix(cm, categories, out_path):
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(categories)))
    ax.set_yticks(range(len(categories)))
    ax.set_xticklabels(categories)
    ax.set_yticklabels(categories)
    ax.set_xlabel("Predicted category")
    ax.set_ylabel("True category")
    ax.set_title("Triage Agent Confusion Matrix\n(real test set, 22,544 records)")

    for i in range(len(categories)):
        for j in range(len(categories)):
            val = cm[i, j]
            color = "white" if val > cm.max() / 2 else "black"
            ax.text(j, i, str(val), ha="center", va="center", color=color, fontsize=9)

    fig.colorbar(im, ax=ax, label="Number of records")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved confusion matrix to {out_path}")

def plot_prf_bars(report, categories, out_path):
    metrics = ["precision", "recall", "f1-score"]
    x = np.arange(len(categories))
    width = 0.25

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, metric in enumerate(metrics):
        values = [report[cat][metric] for cat in categories]
        ax.bar(x + i * width, values, width, label=metric)

    ax.set_xticks(x + width)
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Triage Agent: Precision / Recall / F1 by Category\n(real test set, honestly measured -- note low r2l/u2r recall)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved precision/recall/F1 chart to {out_path}")

if __name__ == "__main__":
    agent = TriageAgent()
    agent.load()

    test_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test_clean.csv")
    report, cm = agent.evaluate(test_csv)

    plot_confusion_matrix(cm, CATEGORIES, os.path.join(OUT_DIR, "confusion_matrix.png"))
    plot_prf_bars(report, CATEGORIES, os.path.join(OUT_DIR, "precision_recall_f1.png"))

    print("\nThese are generated directly from the real evaluate() run -- same numbers as agents/triage_agent.py output.")

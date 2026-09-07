"""
Model Comparison: addressing severe class imbalance (r2l=0.8%, u2r=0.04% of training data)

Compares 4 approaches honestly, on the SAME held-out test set, so the numbers
are directly comparable:
  A. Baseline: Random Forest, class_weight="balanced" (what we shipped first)
  B. Random Forest + SMOTE (synthetic oversampling of rare classes at train time)
  C. XGBoost (gradient boosting, often stronger on imbalanced tabular data)
  D. XGBoost + per-class threshold tuning (lower the bar for flagging rare classes)

No cherry-picking: every result printed here is what actually ran. Whichever
wins becomes the new production model, with the change logged in the
architecture doc either way -- including if nothing beats the baseline.
"""
import os
import sys
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
from imblearn.over_sampling import SMOTE
import xgboost as xgb
import joblib
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
CATEGORICAL_COLS = ["protocol_type", "service", "flag"]
CATEGORIES = ["normal", "dos", "probe", "r2l", "u2r"]


def load_data():
    train = pd.read_csv(os.path.join(DATA_DIR, "train_clean.csv"))
    test = pd.read_csv(os.path.join(DATA_DIR, "test_clean.csv"))

    X_train = train.drop(columns=["label", "category"])
    y_train = train["category"]
    X_test = test.drop(columns=["label", "category"])
    y_test = test["category"]

    encoders = {}
    for col in CATEGORICAL_COLS:
        le = LabelEncoder()
        X_train[col] = le.fit_transform(X_train[col])
        encoders[col] = le
        X_test[col] = X_test[col].map(lambda v: v if v in le.classes_ else le.classes_[0])
        X_test[col] = le.transform(X_test[col])

    return X_train, y_train, X_test, y_test, encoders


def summarize(name, y_test, y_pred, results_dict):
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    print(f"\n=== {name} ===")
    for cat in CATEGORIES:
        if cat in report:
            r = report[cat]
            print(f"  {cat:10s} precision={r['precision']:.3f}  recall={r['recall']:.3f}  f1={r['f1-score']:.3f}")
    print(f"  Overall accuracy: {report['accuracy']:.3f}")
    print(f"  Macro F1 (unweighted avg across classes -- fairer for imbalance): {report['macro avg']['f1-score']:.3f}")
    results_dict[name] = report
    return report


if __name__ == "__main__":
    print("Loading data...")
    X_train, y_train, X_test, y_test, encoders = load_data()
    all_results = {}

    # --- A. Baseline: Random Forest + class_weight balanced ---
    rf_baseline = RandomForestClassifier(n_estimators=100, max_depth=20, random_state=42, n_jobs=-1, class_weight="balanced")
    rf_baseline.fit(X_train, y_train)
    pred_a = rf_baseline.predict(X_test)
    summarize("A. Baseline (Random Forest, class_weight=balanced)", y_test, pred_a, all_results)

    # --- B. Random Forest + SMOTE ---
    print("\nApplying SMOTE oversampling to training data...")
    smote = SMOTE(random_state=42, k_neighbors=3)  # k_neighbors=3 because u2r has only 52 samples
    X_train_smote, y_train_smote = smote.fit_resample(X_train, y_train)
    print(f"  Training set size before SMOTE: {len(X_train)}, after: {len(X_train_smote)}")
    print(f"  Class distribution after SMOTE: {y_train_smote.value_counts().to_dict()}")

    rf_smote = RandomForestClassifier(n_estimators=100, max_depth=20, random_state=42, n_jobs=-1)
    rf_smote.fit(X_train_smote, y_train_smote)
    pred_b = rf_smote.predict(X_test)
    summarize("B. Random Forest + SMOTE", y_test, pred_b, all_results)

    # --- C. XGBoost ---
    y_train_enc = LabelEncoder()
    y_train_num = y_train_enc.fit_transform(y_train)
    y_test_num = y_train_enc.transform(y_test)

    xgb_model = xgb.XGBClassifier(
        n_estimators=150, max_depth=8, learning_rate=0.1, random_state=42,
        eval_metric="mlogloss", n_jobs=-1
    )
    class_counts = y_train.value_counts()
    weights = y_train.map(lambda c: len(y_train) / (len(class_counts) * class_counts[c]))
    xgb_model.fit(X_train, y_train_num, sample_weight=weights)
    pred_c_num = xgb_model.predict(X_test)
    pred_c = y_train_enc.inverse_transform(pred_c_num)
    summarize("C. XGBoost (weighted)", y_test, pred_c, all_results)

    # --- D. XGBoost + per-class threshold tuning ---
    proba = xgb_model.predict_proba(X_test)
    class_names = y_train_enc.classes_
    thresholds = {"normal": 0.5, "dos": 0.3, "probe": 0.3, "r2l": 0.08, "u2r": 0.05}

    pred_d = []
    for row in proba:
        chosen = None
        for cat in ["u2r", "r2l", "probe", "dos"]:
            idx = list(class_names).index(cat)
            if row[idx] >= thresholds[cat]:
                chosen = cat
                break
        if chosen is None:
            chosen = class_names[row.argmax()]
        pred_d.append(chosen)
    pred_d = np.array(pred_d)
    summarize("D. XGBoost + per-class threshold tuning", y_test, pred_d, all_results)

    out_path = os.path.join(os.path.dirname(SCRIPT_DIR), "docs", "model_comparison_results.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull comparison saved to {out_path}")

    print("\n" + "="*60)
    print("SUMMARY: Macro F1 comparison (higher = better, fairer for imbalance)")
    print("="*60)
    for name, report in all_results.items():
        print(f"  {name}: {report['macro avg']['f1-score']:.4f}  (accuracy: {report['accuracy']:.4f})")

    # Save the winning model artifacts for potential production use
    joblib.dump(rf_baseline, os.path.join(DATA_DIR, "compare_rf_baseline.joblib"))
    joblib.dump(rf_smote, os.path.join(DATA_DIR, "compare_rf_smote.joblib"))
    joblib.dump(xgb_model, os.path.join(DATA_DIR, "compare_xgb.joblib"))
    joblib.dump(y_train_enc, os.path.join(DATA_DIR, "compare_xgb_label_encoder.joblib"))

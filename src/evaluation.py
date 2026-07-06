import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn import svm
from sklearn import metrics
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
from sklearn.tree import plot_tree
from sklearn import svm


FILE_LABELLING = "data/labelling/labelling.csv"
FILE_MODEL = "data/production/model.pkl"

COLS = ["eval_birth", "eval_name", "eval_sex", "eval_country", "eval_city2", "eval_father", "eval_occupation", "eval_affiliation"]
UMBRAL = 0.85

def show_metrics(y_true, y_pred):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    print(f"accuracy={(tp+tn)/(tp+tn+fp+fn):.3f}  "
          f"precision={precision_score(y_true, y_pred, zero_division=0):.3f}  "
          f"recall={recall_score(y_true, y_pred, zero_division=0):.3f}  "
          f"f1={f1_score(y_true, y_pred, zero_division=0):.3f}")
    print(f"  TP={tp}  FP={fp}  TN={tn}  FN={fn}")

def heuristics(X, y, umbral):
    return ((X[:, COLS.index("eval_city2")] >= umbral) |
            (X[:, COLS.index("eval_occupation")] == 1)).astype(int)

def regression(X, y):
    clf = LogisticRegression(
        class_weight="balanced",
        C=1.0,              
        max_iter=1000,
        solver="lbfgs",
    )
    clf.fit(X, y)
    return clf

def forest(X, y):
    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=3,
        min_samples_leaf=3,
        max_features="sqrt",
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X, y)
    return clf

def xgboost(X, y):
    clf = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=3,
        random_state=42,
    )
    clf.fit(X, y)
    return clf
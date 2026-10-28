import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ConfusionMatrixDisplay, confusion_matrix
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent

with open(ROOT / "corpus.json", "r", encoding="utf-8") as f:
    corpus = json.load(f)

texts = [x["text"] for x in corpus]
types = [x["type"] for x in corpus]
severities = [x["severity"] for x in corpus]

X_train, X_test, y_type_train, y_type_test, y_sev_train, y_sev_test = train_test_split(
    texts,
    types,
    severities,
    test_size=0.20,
    random_state=42
)

vectorizer = TfidfVectorizer(
    ngram_range=(1, 2),
    min_df=2,
    max_df=0.98,
    sublinear_tf=True
)

X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

type_model = LogisticRegression(
    max_iter=3000,
    class_weight="balanced",
    random_state=42
)

severity_model = LogisticRegression(
    max_iter=3000,
    class_weight="balanced",
    random_state=42
)

type_model.fit(X_train_vec, y_type_train)
severity_model.fit(X_train_vec, y_sev_train)

type_pred = type_model.predict(X_test_vec)
sev_pred = severity_model.predict(X_test_vec)

# -----------------------------
# INCIDENT TYPE MATRIX
# -----------------------------
cm_type = confusion_matrix(
    y_type_test,
    type_pred,
    labels=["MEDICAL", "FIRE", "CRIME"]
)

fig, ax = plt.subplots(figsize=(6, 5))

disp = ConfusionMatrixDisplay(
    confusion_matrix=cm_type,
    display_labels=["Medical", "Fire", "Crime"]
)

disp.plot(ax=ax)

plt.title("Incident Type Confusion Matrix")
plt.tight_layout()
plt.savefig("incident_type_confusion_matrix.png", dpi=300)
plt.close()

# -----------------------------
# SEVERITY MATRIX
# -----------------------------
cm_sev = confusion_matrix(
    y_sev_test,
    sev_pred,
    labels=["LOW", "HIGH", "CRITICAL"]
)

fig, ax = plt.subplots(figsize=(6, 5))

disp = ConfusionMatrixDisplay(
    confusion_matrix=cm_sev,
    display_labels=["Low", "High", "Critical"]
)

disp.plot(ax=ax)

plt.title("Severity Confusion Matrix")
plt.tight_layout()
plt.savefig("severity_confusion_matrix.png", dpi=300)
plt.close()

print("Done.")
print("Saved:")
print("incident_type_confusion_matrix.png")
print("severity_confusion_matrix.png")
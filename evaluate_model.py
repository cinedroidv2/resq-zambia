import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent

with (ROOT / 'corpus.json').open('r', encoding='utf-8') as f:
    corpus = json.load(f)

# Remove exact duplicates before splitting.
unique = {}
for item in corpus:
    key = (' '.join(item['text'].lower().split()), item['type'].upper(), item['severity'].upper())
    unique[key] = {'text': key[0], 'type': key[1], 'severity': key[2]}
corpus = list(unique.values())

texts = [x['text'] for x in corpus]
types = [x['type'] for x in corpus]
severities = [x['severity'] for x in corpus]

indices = list(range(len(corpus)))
train_idx, test_idx = train_test_split(
    indices,
    test_size=0.20,
    random_state=42,
    stratify=[f'{types[i]}::{severities[i]}' for i in indices]
)

X_train_text = [texts[i] for i in train_idx]
X_test_text = [texts[i] for i in test_idx]
y_type_train = [types[i] for i in train_idx]
y_type_test = [types[i] for i in test_idx]
y_sev_train = [severities[i] for i in train_idx]
y_sev_test = [severities[i] for i in test_idx]

vectorizer = TfidfVectorizer(
    ngram_range=(1, 2), min_df=2, max_df=0.98,
    sublinear_tf=True, strip_accents='unicode'
)
X_train = vectorizer.fit_transform(X_train_text)
X_test = vectorizer.transform(X_test_text)

model_args = dict(max_iter=3000, class_weight='balanced', random_state=42)
type_model = LogisticRegression(**model_args).fit(X_train, y_type_train)
severity_model = LogisticRegression(**model_args).fit(X_train, y_sev_train)

type_pred = type_model.predict(X_test)
sev_pred = severity_model.predict(X_test)

print('TYPE ACCURACY:', round(accuracy_score(y_type_test, type_pred), 4))
print(classification_report(y_type_test, type_pred, digits=4))
print('TYPE CONFUSION MATRIX:')
print(confusion_matrix(y_type_test, type_pred, labels=['MEDICAL', 'FIRE', 'CRIME']))

print('\nSEVERITY ACCURACY:', round(accuracy_score(y_sev_test, sev_pred), 4))
print(classification_report(y_sev_test, sev_pred, digits=4))
print('SEVERITY CONFUSION MATRIX:')
print(confusion_matrix(y_sev_test, sev_pred, labels=['LOW', 'HIGH', 'CRITICAL']))

combined = [a == b and c == d for a, b, c, d in zip(y_type_test, type_pred, y_sev_test, sev_pred)]
print('\nCOMBINED ACCURACY:', round(sum(combined) / len(combined), 4))

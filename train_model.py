import json
import pickle
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parent
CORPUS_PATH = ROOT / 'corpus.json'
MODEL_DIR = ROOT / 'app' / 'nlp'


def load_corpus():
    with CORPUS_PATH.open('r', encoding='utf-8') as f:
        corpus = json.load(f)

    allowed_types = {'MEDICAL', 'FIRE', 'CRIME'}
    allowed_severities = {'LOW', 'HIGH', 'CRITICAL'}

    cleaned = []
    seen = set()
    for item in corpus:
        text = ' '.join(str(item['text']).lower().split())
        incident_type = str(item['type']).upper()
        severity = str(item['severity']).upper()
        if incident_type not in allowed_types or severity not in allowed_severities:
            continue
        key = (text, incident_type, severity)
        if key not in seen:
            seen.add(key)
            cleaned.append({'text': text, 'type': incident_type, 'severity': severity})

    return cleaned


def train():
    corpus = load_corpus()
    texts = [x['text'] for x in corpus]
    types = [x['type'] for x in corpus]
    severities = [x['severity'] for x in corpus]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.98,
        sublinear_tf=True,
        strip_accents='unicode'
    )
    X = vectorizer.fit_transform(texts)

    type_model = LogisticRegression(
        max_iter=3000,
        class_weight='balanced',
        random_state=42
    )
    severity_model = LogisticRegression(
        max_iter=3000,
        class_weight='balanced',
        random_state=42
    )

    type_model.fit(X, types)
    severity_model.fit(X, severities)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with (MODEL_DIR / 'vectorizer.pkl').open('wb') as f:
        pickle.dump(vectorizer, f)
    with (MODEL_DIR / 'type_model.pkl').open('wb') as f:
        pickle.dump(type_model, f)
    with (MODEL_DIR / 'severity_model.pkl').open('wb') as f:
        pickle.dump(severity_model, f)

    print(f'Trained on {len(corpus)} unique records')
    print('Type classes:', list(type_model.classes_))
    print('Severity classes:', list(severity_model.classes_))
    print('Models saved to app/nlp/')


if __name__ == '__main__':
    train()

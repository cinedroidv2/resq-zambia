import os
import pickle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'vectorizer.pkl'), 'rb') as f:
    vectorizer = pickle.load(f)
with open(os.path.join(BASE_DIR, 'type_model.pkl'), 'rb') as f:
    type_model = pickle.load(f)
with open(os.path.join(BASE_DIR, 'severity_model.pkl'), 'rb') as f:
    severity_model = pickle.load(f)

ALLOWED_TYPES = {'MEDICAL', 'FIRE', 'CRIME'}
ALLOWED_SEVERITIES = {'LOW', 'HIGH', 'CRITICAL'}

CRITICAL_TERMS = {
    'not breathing', 'sakupuma', 'sapema', 'unconscious and not responding',
    'wakomoka ndipo sayankha', 'heart attack', 'mtima kubaba kwambiri',
    'severe bleeding that will not stop', 'magazi yambiri osaleka',
    'people trapped', 'bantu bankala sibachoka mukati', 'gas explosion', 'kuphulika kwa gasi',
    'active shooting', 'kuwombera kukuchitika', 'gunshots with people injured',
    'maululu a mfuti ndipo anthu avulala', 'hostage', 'multiple stabbing victims'
}


def triage(text):
    if not text or not str(text).strip():
        return {
            'incident_type': 'OTHER',
            'severity': 'LOW',
            'confidence': 0.0,
            'classification_status': 'Needs Review'
        }

    cleaned = ' '.join(str(text).lower().split())
    X = vectorizer.transform([cleaned])

    type_probs = type_model.predict_proba(X)[0]
    severity_probs = severity_model.predict_proba(X)[0]

    type_index = int(type_probs.argmax())
    severity_index = int(severity_probs.argmax())

    incident_type = str(type_model.classes_[type_index]).upper()
    severity = str(severity_model.classes_[severity_index]).upper()

    type_conf = float(type_probs[type_index])
    severity_conf = float(severity_probs[severity_index])
    confidence = min(type_conf, severity_conf)

    # Limited life-safety override. It changes severity only, not incident type.
    if any(term in cleaned for term in CRITICAL_TERMS):
        severity = 'CRITICAL'
        confidence = max(confidence, 0.90)

    if incident_type not in ALLOWED_TYPES:
        incident_type = 'OTHER'
    if severity not in ALLOWED_SEVERITIES:
        severity = 'LOW'

    return {
        'incident_type': incident_type,
        'severity': severity,
        'confidence': round(confidence, 4),
        # Below 0.75 does not block classification or saving.
        'classification_status': 'AI Classified' if confidence >= 0.75 else 'Needs Review'
    }

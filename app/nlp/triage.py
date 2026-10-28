import math
import os
import pickle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VECTORIZER_PATH = os.path.join(BASE_DIR, "vectorizer.pkl")
TYPE_MODEL_PATH = os.path.join(BASE_DIR, "type_model.pkl")
SEVERITY_MODEL_PATH = os.path.join(
    BASE_DIR,
    "severity_model.pkl"
)

vectorizer = None
type_model = None
severity_model = None
MODELS_LOADED = False

ALLOWED_TYPES = {
    "MEDICAL",
    "FIRE",
    "CRIME"
}

ALLOWED_SEVERITIES = {
    "LOW",
    "HIGH",
    "CRITICAL"
}


# These phrases are reserved for immediate life-threatening
# situations. They may override the trained severity result.
CRITICAL_TERMS = {
    # Medical - English
    "not breathing",
    "unconscious and not responding",
    "heart attack",
    "severe bleeding that will not stop",
    "person choking",
    "multiple people unconscious",
    "child not breathing",

    # Medical - local wording
    "sakupuma",
    "sapema",
    "wakomoka ndipo sayankha",
    "mtima kubaba kwambiri",
    "magazi yambiri osaleka",
    "afenta ndipo sayanka",
    "mtima kubaba maningi",
    "magazi yambili osaleka",
    "kugwa pansi osayankha",

    # Fire - English
    "people trapped",
    "house on fire with people trapped",
    "gas explosion",
    "petrol station fire",
    "hospital building burning",
    "multiple houses burning",

    # Fire - local wording
    "bantu bankala sibachoka mukati",
    "kuphulika kwa gasi",
    "nyumba yayaka ndipo bantu basala mukati",
    "moto pa petrol station",
    "nyumba zambiri zikuyaka",
    "moto waukulu ndi anthu mkati",

    # Crime - English
    "active shooting",
    "gunshots with people injured",
    "hostage situation",
    "armed robbery with shots fired",
    "multiple stabbing victims",
    "person threatening to kill someone with a gun",

    # Crime - local wording
    "kuwombera kukuchitika",
    "kuwombera kukuchitika pano",
    "maululu a mfuti ndipo anthu avulala",
    "maululu a mfuti ndipo bantu avulala",
    "bantu agwidwa hostage",
    "kubela ndi mfuti kuwombera kwachitika",
    "bantu bambili abayidwa",
    "munthu akufuna kupha wina ndi mfuti",
    "muntu bamu paya"
}


# These terms help identify the category only.
# They do not automatically make the incident Critical.
FIRE_TYPE_TERMS = {
    "fire",
    "burning",
    "explosion",
    "smoke",
    "gas leak",
    "moto",
    "kuwotcha",
    "kuwotcha nyumba",
    "mulilo",
    "kupwa",
    "napya",
    "ikuyaka",
    "ikupya"
}

MEDICAL_TYPE_TERMS = {
    "fever",
    "headache",
    "bleeding",
    "wound",
    "cut",
    "vomiting",
    "asthma",
    "chest pain",
    "unconscious",
    "not breathing",
    "heart attack",
    "chilonda",
    "mutu ibaba",
    "mugazi",
    "magazi",
    "sapema",
    "sayanka",
    "mwana adwala"
}

CRIME_TYPE_TERMS = {
    "gun",
    "shooting",
    "robbery",
    "stabbing",
    "knife",
    "theft",
    "stolen",
    "assault",
    "hostage",
    "mfuti",
    "kubela",
    "kumenya",
    "kuba",
    "banibela",
    "lasa",
    "juba",
    "baba phone"
}


def load_models():
    global vectorizer
    global type_model
    global severity_model
    global MODELS_LOADED

    try:
        with open(VECTORIZER_PATH, "rb") as file:
            vectorizer = pickle.load(file)

        with open(TYPE_MODEL_PATH, "rb") as file:
            type_model = pickle.load(file)

        with open(SEVERITY_MODEL_PATH, "rb") as file:
            severity_model = pickle.load(file)

        MODELS_LOADED = True

        print("NLP models loaded successfully.")
        print(
            "Type classes:",
            list(type_model.classes_)
        )
        print(
            "Severity classes:",
            list(severity_model.classes_)
        )

        if "LOW" not in {
            str(label).upper()
            for label in severity_model.classes_
        }:
            print(
                "WARNING: Severity model has no LOW class. "
                "Retrain the model."
            )

    except FileNotFoundError as error:
        print(
            f"NLP model file was not found: {error}"
        )
        print("Run train_model.py first.")
        MODELS_LOADED = False

    except Exception as error:
        print(
            f"NLP models could not be loaded: {error}"
        )
        MODELS_LOADED = False


def model_confidence(model, features):
    """
    Returns a confidence-like score.

    Logistic regression models use predict_proba().
    LinearSVC models use the decision margin.
    """

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(features)[0]
        return float(max(probabilities))

    if hasattr(model, "decision_function"):
        scores = model.decision_function(features)

        # Binary classifier
        if getattr(scores, "ndim", 1) == 1:
            margin = abs(float(scores[0]))
            return 1.0 / (1.0 + math.exp(-margin))

        # Multiclass classifier
        class_scores = sorted(
            [float(score) for score in scores[0]],
            reverse=True
        )

        if len(class_scores) >= 2:
            margin = class_scores[0] - class_scores[1]
        else:
            margin = abs(class_scores[0])

        return 1.0 / (1.0 + math.exp(-margin))

    return 0.75


def contains_any(text, terms):
    return any(
        term in text
        for term in terms
    )


def triage(text):
    if not text or not str(text).strip():
        return {
            "incident_type": "OTHER",
            "severity": "LOW",
            "confidence": 0.0,
            "classification_status": "Needs Review"
        }

    if not MODELS_LOADED:
        return {
            "incident_type": "OTHER",
            "severity": "LOW",
            "confidence": 0.0,
            "classification_status": "Needs Review"
        }

    try:
        cleaned = " ".join(
            str(text).lower().split()
        )

        features = vectorizer.transform(
            [cleaned]
        )

        predicted_type = str(
            type_model.predict(features)[0]
        ).upper()

        predicted_severity = str(
            severity_model.predict(features)[0]
        ).upper()

        type_confidence = model_confidence(
            type_model,
            features
        )

        severity_confidence = model_confidence(
            severity_model,
            features
        )

        confidence = min(
            type_confidence,
            severity_confidence
        )

        # Category keyword assistance.
        # This changes the category only, not severity.
        if contains_any(cleaned, FIRE_TYPE_TERMS):
            predicted_type = "FIRE"

        elif contains_any(cleaned, CRIME_TYPE_TERMS):
            predicted_type = "CRIME"

        elif contains_any(cleaned, MEDICAL_TYPE_TERMS):
            predicted_type = "MEDICAL"

        # Genuine life-safety override.
        if contains_any(cleaned, CRITICAL_TERMS):
            predicted_severity = "CRITICAL"
            confidence = max(
                confidence,
                0.90
            )

        # High fever should not become Critical unless the
        # report also contains a genuine critical condition.
        elif (
            "high fever" in cleaned
            or "very high fever" in cleaned
            or "persistent high fever" in cleaned
        ):
            predicted_type = "MEDICAL"
            predicted_severity = "HIGH"
            confidence = max(
                confidence,
                0.80
            )

        if predicted_type not in ALLOWED_TYPES:
            predicted_type = "OTHER"

        if predicted_severity not in ALLOWED_SEVERITIES:
            predicted_severity = "LOW"

        classification_status = (
            "AI Classified"
            if confidence >= 0.75
            else "Needs Review"
        )

        return {
            "incident_type": predicted_type,
            "severity": predicted_severity,
            "confidence": round(confidence, 4),
            "classification_status": classification_status
        }

    except Exception as error:
        print(
            f"NLP triage error: {error}"
        )

        return {
            "incident_type": "OTHER",
            "severity": "LOW",
            "confidence": 0.0,
            "classification_status": "Needs Review"
        }


load_models()
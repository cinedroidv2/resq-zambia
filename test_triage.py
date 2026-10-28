from app.nlp.triage import triage

TESTS = [
    "someone stole my phone when i was shopping",
    "thief entered my shop while i was asleep",
    "banimenya",
    "baba phone pano",

    "headache for two days non stop",
    "muntu wagwa pansi",
    "sapema",
    "child has a fever",

    "there is smoke outside",
    "mulilo ku nyumba",
    "shop is on fire",
    "nyumba yayaka muli banthu  mkati"

]

for text in TESTS:
    print(text)
    print(triage(text))
    print('-' * 50)

import json
import random
from pathlib import Path

random.seed(42)

OUTPUT = Path('corpus.json')

LOCATIONS = [
    'kanyama', 'matero', 'chawama', 'unza', 'lusaka city',
    'town centre', 'chipata road', 'manda hill', 'airport road',
    'garden compound', 'kamwala', 'chelstone', 'garden township', 'libala', 'chilenje', 'chalala', 'zcas', 'unza'
]

PREFIXES = [
    'there is', 'please help with', 'someone reports', 'we need help for',
    'i think there is', 'urgent report of', 'munthu akuti pali',
    'tikufuna thandizo pa', 'pali', 'help'
]

SUFFIXES = [
    '', 'please', 'urgent', 'now', 'quickly', 'pls', 'help',
    'near the road', 'behind the market', 'at the bus stop'
]

# Only the approved incident types and severities.
SCENARIOS = {
    'MEDICAL': {
        'LOW': [
            'minor cut', 'small wound', 'mild headache', 'dizziness but awake', 'headache', 'fever', 'nose bleeding lightly',
            'feeling weak but conscious', 'minor burn on hand', 'nose bleeding lightly',
            'chilonda kanono', 'mutu ibaba pangono', 'mugazi pangono',
            'nimvela dizi', 'menso yababa', 'meno ibaba'
        ],
        'HIGH': [
            'deep cut but still conscious', 'broken arm', 'heavy vomiting',
            'person collapsed but is breathing', 'serious chest pain',
            'moderate bleeding', 'severe asthma attack but conscious',
            'mwana adwala', 'mwana achosa rush', 'high fever',
            'muntu agwa pansi', 'magazi yambili koma ali conscious',
            'nakangiwa movutika koma ayanka', 'manta'
        ],
        'CRITICAL': [
            'not breathing', 'unconscious and not responding', 'heart attack',
            'severe bleeding that will not stop', 'person choking',
            'multiple people unconscious', 'child not breathing',
            'sapema', 'afenta ndipo sayanka', 'mtima kubaba maningi',
            'magazi yambili osaleka', 'akufa', 'sapema',
            'kugwa pansi osayankha', 'afa', 'afela', 'mimba yachoka', 'mimba', 'badwa'
        ]
    },
    'FIRE': {
        'LOW': [
            'small rubbish fire already controlled', 'small cooking fire',
            'smoke from a bin', 'minor electrical smell with no flames',
            'small grass fire away from houses',
            'moto wa zinyalala pangono', 'chutsi pangono mu kitchen',
            'moto pangono wa grass itali ndi nyumba', 'kununka kaya koma kulibe manzi'
        ],
        'HIGH': [
            'room on fire', 'vehicle burning', 'shop burning with people outside',
            'large grass fire near houses', 'electrical fire spreading',
            'gas smell inside a building', 'thick smoke from a house',
            'kapinga yayaka', 'galimoto ikuyaka', 'nyumba ikupya koma bantu bali panja',
            'moto wa grass pafupi ndi nyumba', 'mpweya na gasi munyumba',
            'chusi yambili kuchokera mnyumba', 'motoka ikuyaka pafupi ndi nyumba', 'nyumba ikupya kwambiri'
        ],
        'CRITICAL': [
            'house on fire with people trapped', 'building burning rapidly',
            'gas explosion', 'petrol station fire', 'school on fire',
            'hospital building burning', 'multiple houses burning',
            'nyumba yayaka ndipo bantu basala mukati',
            'nyumba ikupya kwambiri', 'kuphulika kwa gasi',
            'moto pa petrol station', 'sukulu ikuyaka',
            'nyumba zambiri zikuyaka', 'moto waukulu ndi anthu mkati', 'bana basobela nama light', 'kaleza'
        ]
    },
    'CRIME': {
        'LOW': [
            'phone stolen with no violence', 'minor property theft',
            'suspicious person watching houses', 'shoplifting with no weapon',
            'verbal threat with no weapon', 'bag stolen and suspect left',
            'foni yabedwa palibe wavulala', 'bani bela chola',
            'ba pwanya window', 'kuopseza popanda chida',
            'chikwama chabewa koma palibe wavulala', 'baba phone'
        ],
        'HIGH': [
            'robbery in progress', 'assault with injuries', 'stabbing victim conscious',
            'armed suspect seen nearby', 'violent break in', 'person being beaten',
            'domestic violence happening now', 'kubela kukuchitika pano',
            'kumenya munthu maningi', 'kubaya koma victim ali conscious',
            'munthu ali na ndeo', 'mwana akuba mu shop', 
            'kabolala munyumba siniziba'
        ],
        'CRITICAL': [
            'active shooting', 'gunshots with people injured', 'hostage situation',
            'armed robbery with shots fired', 'multiple stabbing victims',
            'person threatening to kill someone with a gun', 'dead body', 'child missing',
            'maululu a mfuti ndipo bantu avulala', 'kuwombera kukuchitika pano',
            'bantu agwidwa hostage', 'kubela ndi mfuti kuwombera kwachitika','bataba mu njila'
            'bantu bambili abayidwa', 'munthu akufuna kupha wina ndi mfuti', 'mwana asoba', 'mwana saoneka', 'muntu bamu paya'
        ]
    }
}

TEMPLATES = [
    '{prefix} {event} at {location} {suffix}',
    '{event} happening in {location} {suffix}',
    'report from {location}: {event} {suffix}',
    'someone at {location} says {event} {suffix}',
    '{prefix} {event} ku {location} {suffix}',
    '{event} pafupi ndi {location} {suffix}',
    'emergency in {location}, {event} {suffix}',
    'dispatcher report: {event}, location {location} {suffix}'
]


def make_text(event: str) -> str:
    template = random.choice(TEMPLATES)
    text = template.format(
        prefix=random.choice(PREFIXES),
        event=event,
        location=random.choice(LOCATIONS),
        suffix=random.choice(SUFFIXES),
    )
    return ' '.join(text.lower().split())


def generate(per_label: int = 220):
    rows = []
    seen = set()

    for incident_type, severities in SCENARIOS.items():
        for severity, events in severities.items():
            while sum(1 for r in rows if r['type'] == incident_type and r['severity'] == severity) < per_label:
                text = make_text(random.choice(events))
                key = (text, incident_type, severity)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({'text': text, 'type': incident_type, 'severity': severity})

    random.shuffle(rows)
    return rows


if __name__ == '__main__':
    corpus = generate()
    OUTPUT.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Corpus generated: {len(corpus)} records')
    print('Types: MEDICAL, FIRE, CRIME')
    print('Severities: LOW, HIGH, CRITICAL')

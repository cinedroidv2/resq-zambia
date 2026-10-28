import json
from collections import Counter

with open('corpus.json', 'r', encoding='utf-8') as f:
    corpus = json.load(f)

print('Total:', len(corpus))
print('Types:', Counter(x['type'] for x in corpus))
print('Severities:', Counter(x['severity'] for x in corpus))
print('Type + severity:')
for key, value in sorted(Counter((x['type'], x['severity']) for x in corpus).items()):
    print(f'  {key[0]:8} {key[1]:8} {value}')

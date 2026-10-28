"""Cross-chapter display groups; never removes rows or asserts reachability."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
import re

SCHEMA = 'key-english-1'


def prefix(key):
    match = re.fullmatch(r'(.*_gml_)\d+_\d+(?:_[A-Za-z0-9]+)*', key)
    return match[1] if match else key


def annotate(chapters):
    counts, records = {}, []
    for data in chapters:
        ch = data['chapter']
        counts[ch] = Counter()
        en_column = data['languages'].index('en') + 1
        for i, row in enumerate(data['rows']):
            en = None if row[en_column] is None else data['strings'][row[en_column]]
            if not en:  # Missing or empty English cannot establish equality.
                continue
            base = (prefix(row[0]), en)
            counts[ch][base] += max(1, len(row[6]))
            records.append((data, i, base))
        data['display_dedup'] = {'schema': SCHEMA, 'groups': [None] * len(data['rows']), 'chapters': {}}
    repeated = {base for count in counts.values() for base, n in count.items() if n > 1}
    groups = defaultdict(list)
    for data, i, base in records:
        # Ambiguity anywhere in the full inventory forbids cross-key pairing.
        identity = (base, data['rows'][i][0] if base in repeated else None)
        groups[identity].append((data, i))
    # A shared revision prevents stale chapter packages from mixing group IDs.
    membership = [(identity, [(data['chapter'], i) for data, i in members])
                  for identity, members in groups.items()]
    revision = sha256(json.dumps(membership, ensure_ascii=False).encode('utf-8')).hexdigest()
    for data in chapters:
        data['display_dedup']['revision'] = revision
    group_id = 0
    for members in groups.values():
        if len({data['chapter'] for data, _ in members}) < 2:
            continue
        assert len({data['chapter'] for data, _ in members}) == len(members)
        for data, i in members:
            data['display_dedup']['groups'][i] = group_id
            data['display_dedup']['chapters'][str(group_id)] = sorted(d['chapter'] for d, _ in members)
        group_id += 1
    return group_id

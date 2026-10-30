"""Attach reviewed artword transcriptions only to matching original strings."""
import hashlib
import json


def project(path, chapter, lines):
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 1:
        raise ValueError('Unexpected artword schema')
    rows = {row['key']: row for row in lines}
    result = {}
    seen = set()
    for entry in data['entries']:
        identity = (entry['chapter'], entry['key'])
        if identity in seen:
            raise ValueError('Duplicate artword binding')
        seen.add(identity)
        if entry['chapter'] != chapter or entry['key'] not in rows:
            continue
        row = rows[entry['key']]
        fields = {}
        for field, binding in entry['fields'].items():
            raw = row.get(field)
            if not isinstance(raw, str) or hashlib.sha256(raw.encode('utf-8')).hexdigest() != binding['raw_sha256']:
                continue  # Changed input: retain the placeholder until reviewed again.
            slots = binding['slots']
            if any(not isinstance(slot, str) or len(slot) != 1 or not slot.isascii() or not slot.isdigit()
                   or not isinstance(text, str) or not text.strip() or '\\O' + slot not in raw
                   for slot, text in slots.items()):
                raise ValueError('Invalid artword slot or transcription')
            fields[field] = slots
        if fields:
            result[entry['key']] = fields
    return result

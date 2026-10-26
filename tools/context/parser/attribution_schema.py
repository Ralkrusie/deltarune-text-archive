"""Build stable occurrence identifiers from chapter and source positions."""
from __future__ import annotations

import hashlib

import json

from pathlib import PurePosixPath

import re

SOURCE_KINDS = {'canonical', 'zh'}

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()

def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('missing ' + label)

def _hash(value, label):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid SHA-256: ' + label)

def _path(value, label):
    _nonempty(value, label)
    path = PurePosixPath(value)
    if (path.is_absolute() or '\\' in value or ':' in value or
            '..' in path.parts or path.as_posix() != value or value == '.'):
        raise ValueError('path must be normalized project-relative text: ' + label)

def _chapter(chapter):
    if type(chapter) is not int or chapter not in range(1, 6):
        raise ValueError('chapter must be an integer in 1..5')

def occurrence_id(chapter, source_kind, path, sha256, key, offset, call):
    _chapter(chapter)
    if source_kind not in SOURCE_KINDS:
        raise ValueError('invalid source kind')
    _path(path, 'occurrence source')
    _hash(sha256, 'occurrence source')
    if key is not None:
        _nonempty(key, 'localization key')
    if type(offset) is not int or offset < 0:
        raise ValueError('source offset must be a nonnegative integer')
    _nonempty(call, 'registration call')
    return 'occurrence:' + digest([chapter, source_kind, path, sha256, key, offset, call])[:32]

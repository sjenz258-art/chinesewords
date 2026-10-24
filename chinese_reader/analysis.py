"""Deterministic Han-character statistics; punctuation and titles are excluded."""
from collections import Counter


def is_han(char):
    n = ord(char)
    return (0x3400 <= n <= 0x4DBF or 0x4E00 <= n <= 0x9FFF
            or 0xF900 <= n <= 0xFAFF or 0x20000 <= n <= 0x2FA1F
            or 0x30000 <= n <= 0x323AF)


def characters(text):
    return [c for c in text if is_han(c)]


def unique_characters(text):
    return list(dict.fromkeys(characters(text)))


def analyse(text, mastered=(), learning=(), targets=(), desired=200):
    counts = Counter(characters(text))
    unique = set(counts)
    mastered, learning, targets = map(set, (mastered, learning, targets))
    included = targets & unique
    unfamiliar = unique - mastered - learning
    return {
        'total': sum(counts.values()), 'unique': len(unique),
        'mastered_unique_pct': 100 * len(unique & mastered) / len(unique) if unique else 0,
        'mastered_occurrence_pct': 100 * sum(counts[c] for c in mastered) / sum(counts.values()) if counts else 0,
        'target_count': len(included), 'target_total': len(targets),
        'target_coverage_pct': 100 * len(included) / len(targets) if targets else None,
        'target_frequency': {c: counts[c] for c in sorted(targets)},
        'missing_targets': sorted(targets - unique),
        'unfamiliar': sorted(unfamiliar), 'unfamiliar_count': len(unfamiliar),
        'within_length': desired - 20 <= sum(counts.values()) <= desired + 20,
    }

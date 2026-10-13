import re


def conservative_checks(claim_text: str, source_texts: tuple[str, ...]) -> tuple[str, ...]:
    """Negative checks only. Matching words/numbers never prove entailment."""
    problems = []
    source = '\n'.join(source_texts).lower()
    claim = claim_text.lower()
    numbers = set(re.findall(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[%％]?', claim))
    source_numbers = set(re.findall(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[%％]?', source))
    if numbers - source_numbers:
        problems.append('unanchored_numeric_value')
    restrictions = ('only in', 'exclusively', '仅适用', '只适用', '仅在', '只在')
    universals = ('all languages', 'all settings', 'universally', '所有语言', '任何场景', '所有场景')
    if any(x in source for x in restrictions) and any(x in claim for x in universals) and not any(x in source for x in universals):
        problems.append('scope_expansion')
    return tuple(problems)

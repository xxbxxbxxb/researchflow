import re

_NUMBER = r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?'
_UNIT = r'(?:mmol|[µμu]mol|nmol|mol|[µμu]g|ng|mg|kg|g|mL|ml|dL|dl|L|l|ms|s|min|h|mm|cm|km|m|mM|nM|M|°C|°F|[%％])'
_QUANTITY = re.compile(rf'({_NUMBER})\s*({_UNIT}(?:\s*/\s*{_UNIT})?)(?![A-Za-zµμ])')
_ENGLISH_RESTRICTION = re.compile(r'\b(?:only|exclusively)\s+(?:in|under|for)\s+([^.;,\n]+)')
_CHINESE_RESTRICTION = re.compile(r'(?:仅|只)(?:在|对)([^，。；\n]+?)(?:条件下|情况下|中|时|下)|(?:仅|只)适用于?([^，。；\n]+)')


def quantities(text: str) -> set[tuple[str, str]]:
    # Keep unit case: mM and M are not interchangeable. No implicit conversions.
    return {(number,re.sub(r'\s+','',unit).replace('μ','µ').replace('％','%')) for number,unit in _QUANTITY.findall(text)}


def restrictions(text: str) -> tuple[str, ...]:
    result=[]
    for match in _ENGLISH_RESTRICTION.finditer(text):
        condition=re.split(r'\s+\b(?:at|with|using|when|where|and)\b',match.group(1),maxsplit=1)[0]
        result.append(' '.join(condition.split()))
    for match in _CHINESE_RESTRICTION.finditer(text):
        result.append(next(group for group in match.groups() if group))
    return tuple(result)


def conservative_checks(claim_text: str, source_texts: tuple[str, ...]) -> tuple[str, ...]:
    """Negative checks only. Matching words/numbers never prove entailment."""
    problems = []
    source = '\n'.join(source_texts).lower()
    claim = claim_text.lower()
    numbers = set(re.findall(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[%％]?', claim))
    source_numbers = set(re.findall(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[%％]?', source))
    if numbers - source_numbers:
        problems.append('unanchored_numeric_value')
    if quantities(claim_text) - quantities('\n'.join(source_texts)):
        problems.append('unit_binding_mismatch')
    if any(condition not in claim for condition in restrictions(source)):
        problems.append('experimental_condition_missing')
    restriction_markers = ('only in', 'exclusively', '仅适用', '只适用', '仅在', '只在')
    universals = ('all languages', 'all settings', 'universally', '所有语言', '任何场景', '所有场景')
    if any(x in source for x in restriction_markers) and any(x in claim for x in universals) and not any(x in source for x in universals):
        problems.append('scope_expansion')
    return tuple(problems)

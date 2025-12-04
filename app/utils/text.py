import re

# Match a clean sentence ending: ., !, ? optionally followed by a closing quote.
_TERMINAL_RE = re.compile(r'[.!?](?:(?:"|”|\')+)?$')

def _last_sentence_end(text: str) -> int:
    """
    Return index of the last terminal punctuation that likely ends a sentence.
    If none, return -1.
    """
    last = -1
    for m in re.finditer(r'[.!?]', text):
        last = m.start()
    return last

def _trim_trailing_fragment(text: str) -> str:
    """
    If the text ends without terminal punctuation, trim any trailing fragment
    after the last full sentence. If no sentence exists, add a period.
    """
    s = (text or "").strip()
    if not s:
        return s
    if _TERMINAL_RE.search(s):
        return s
    i = _last_sentence_end(s)
    if i >= 0:
        return s[: i + 1].strip()
    # No terminal punctuation at all — append a period to avoid dangling close.
    return s + "."

def finalize_script(text: str) -> str:
    """
    Ensure the script ends cleanly on a full sentence.
    1) Trim any trailing partial sentence.
    2) If still not terminal, append a short present-tense affirmation (kept minimal).
    """
    s = _trim_trailing_fragment(text)
    if _TERMINAL_RE.search(s):
        return s
    # Fallback micro-affirmation if some edge case slips through.
    return s + " You are here, breathing, and moving forward."

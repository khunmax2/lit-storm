"""Write a STORM report in a language other than English.

Copied from the Streamlit app's article_language.py (STORM half only). The
Co-STORM half comes back with Discussion in the second release; the app was
removed on 2026-09-30, and the file is in git history:
``git log --diff-filter=D -- frontend/demo_light/article_language.py``.

STORM's prompts live as docstrings on its ``dspy.Signature`` classes, and DSPy
reads ``Signature.instructions`` straight off ``__doc__`` every time it builds a
prompt. So the language is switched by appending a directive to the docstrings
of the signatures whose output a reader sees.

That is a change to class attributes, so it holds for the whole process. Two
Runs in one process would write in whichever language was applied last,
which is why every Run gets a process of its own (docs/adr/0003).

Search queries are deliberately left alone: query wording decides which
sources are found, and pinning it to one language would shrink the evidence.
"""

from knowledge_storm.storm_wiki.modules import (
    article_generation,
    article_polish,
    knowledge_curation,
    outline_generation,
    persona_generator,
)

# Report language code -> the name the model is told to write in. None means
# "leave STORM alone", which is not the same as asking it for English.
LANGUAGES = {
    "th": "Thai (ภาษาไทย)",
    "en": None,
}


def _article(language):
    """The reader-facing article: headings, body, citation markers."""
    return f"""

IMPORTANT — Language:
Write ALL output in {language}, including every section heading and the body
text. The collected information may be in another language; translate what you
use rather than quoting it verbatim.
Keep these exactly as they are:
- the inline citation markers [1], [2], ... and their positions;
- the "#", "##", "###" heading markers;
- proper nouns, and technical or scientific terms — give the {language} term
  followed by the original in parentheses the first time each one appears.
"""


def _lead(language):
    """The lead: prose only. Measured: told to keep "#" markers, a model
    opened the lead with the first section's heading, and STORM merged the
    lead into that section and dropped it."""
    return f"""

IMPORTANT — Language:
Write the lead section in {language}.
Write paragraphs only: no heading, no "#" line, no title. Keep the inline
citation markers [1], [2], ... exactly as they are. Give proper nouns and
technical terms in {language} followed by the original in parentheses the
first time each one appears.
"""


def _persona(language):
    """The editor personas."""
    return f"""

IMPORTANT — Language:
Write the editors' summaries and descriptions in {language}.
Keep the numbered "1. summary: description" output format exactly as specified.
"""


def _question(language):
    """The interview questions."""
    return f"""

IMPORTANT — Language:
Ask your questions in {language}.
One exception: when you have no more questions, end with the English sentence
"Thank you so much for your help!" written exactly like that — it is the signal
that closes the conversation, and a translation would not be recognised.
"""


def _answer(language):
    """The expert's answers."""
    return f"""

IMPORTANT — Language:
Answer in {language}. The gathered information is usually in another language;
translate what you use rather than quoting it verbatim, and keep the inline
citation markers [1], [2], ... exactly where they belong.
"""


def _query(language):
    """Search queries — not shown to the reader, and not forced into one language."""
    return f"""

Note on the search queries: the question may be written in {language}, but the
queries do not have to be. Write each query in whichever language is most likely
to find good sources — usually English, and {language} for topics that are local
to the people who speak it. Mixing the two across queries is fine.
"""


_TARGETS = (
    (outline_generation.WritePageOutline, _article),
    (outline_generation.WritePageOutlineFromConv, _article),
    (article_generation.WriteSection, _article),
    (article_polish.WriteLeadSection, _lead),
    (article_polish.PolishPage, _article),
    (persona_generator.GenPersona, _persona),
    (knowledge_curation.AskQuestion, _question),
    (knowledge_curation.AskQuestionWithPersona, _question),
    (knowledge_curation.AnswerQuestion, _answer),
    (knowledge_curation.QuestionToQuery, _query),
)

_ORIGINAL_DOCS = {}


def apply(code):
    """Point STORM's prompts at report language `code`. Safe to call repeatedly."""
    if code not in LANGUAGES:
        raise ValueError(f"{code!r} is not a report language: {sorted(LANGUAGES)}")
    language = LANGUAGES[code]

    for signature, directive in _TARGETS:
        if signature not in _ORIGINAL_DOCS:
            _ORIGINAL_DOCS[signature] = signature.__doc__
        original = _ORIGINAL_DOCS[signature]
        signature.__doc__ = original if language is None else original + directive(language)


def applied_instructions():
    """The article prompt as DSPy will read it now. For tests."""
    return outline_generation.WritePageOutline.__doc__

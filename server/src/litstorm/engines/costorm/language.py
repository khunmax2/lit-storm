"""Hold a Co-STORM Discussion in a language other than English.

The Co-STORM half of the Streamlit app's article_language.py (in git
history: ``git log --diff-filter=D -- frontend/demo_light/article_language.py``),
which engines/storm/language.py left for this release. The mechanism is the
same: Co-STORM's prompts are docstrings on ``dspy.Signature`` classes, and a
directive appended to them changes what the model writes. That is process-
wide, which a Turn can afford because each has a process of its own
(docs/adr/0003).

What is covered is what a reader sees: the invited speakers, what they say
at the round table, the mind map's concept names, and the report. The warm
start borrows STORM's outline prompt, so STORM's switch is applied too.

Left alone on purpose:
- search queries, whose wording decides which sources are found;
- ``InsertInformation``, whose output is a control token ("insert",
  "step: <node>", "create: <node>") a language directive is as likely to
  translate as the node name.
"""

from knowledge_storm.collaborative_storm.modules import (
    article_generation,
    expert_generation,
    grounded_question_answering,
    grounded_question_generation,
    information_insertion_module,
    warmstart_hierarchical_chat,
)

from litstorm.engines.storm import language as storm_language

LANGUAGES = storm_language.LANGUAGES


def _article(language):
    return storm_language._article(language)


def _query(language):
    return storm_language._query(language)


def _speaker(language):
    """The invited experts, whose roles are shown as the speakers' names."""
    return f"""

IMPORTANT — Language:
Write each speaker's role and description in {language}.
Keep the numbered "1. role: description" output format exactly as specified,
including the colon — it is what separates the name from the description.
"""


def _utterance(language):
    """What is said at the round table: the questions and the replies."""
    return f"""

IMPORTANT — Language:
Speak in {language}. The gathered information is usually in another language;
translate what you use rather than quoting it verbatim, and keep the inline
citation markers [1], [2], ... exactly where they belong.
"""


def _heading(language):
    """Names of the mind map's concepts, which become the report's headings."""
    return f"""

IMPORTANT — Language:
Write the section names in {language}, keeping the output format specified
above exactly as it is.
"""


_TARGETS = (
    (article_generation.WriteSection, _article),
    (expert_generation.GenerateExpertGeneral, _speaker),
    (expert_generation.GenerateExpertWithFocus, _speaker),
    (grounded_question_answering.AnswerQuestion, _utterance),
    (grounded_question_answering.QuestionToQuery, _query),
    (grounded_question_generation.ConvertUtteranceStyle, _utterance),
    (grounded_question_generation.GroundedQuestionGeneration, _utterance),
    (warmstart_hierarchical_chat.WarmStartModerator, _utterance),
    (warmstart_hierarchical_chat.SectionToConvTranscript, _utterance),
    (warmstart_hierarchical_chat.GenerateWarmStartOutline, _heading),
    (information_insertion_module.ExpandSection, _heading),
)

_ORIGINAL_DOCS = {}


def apply(code):
    """Point Co-STORM's prompts (and STORM's) at report language `code`."""
    storm_language.apply(code)
    language = LANGUAGES[code]
    for signature, directive in _TARGETS:
        if signature not in _ORIGINAL_DOCS:
            _ORIGINAL_DOCS[signature] = signature.__doc__
        original = _ORIGINAL_DOCS[signature]
        signature.__doc__ = original if language is None else original + directive(language)

"""Run STORM and Co-STORM in a language other than English.

STORM's prompts live as docstrings on its ``dspy.Signature`` classes, and DSPy
reads ``Signature.instructions`` straight off ``__doc__`` every time it builds a
prompt. So the language is switched by appending a directive to the docstrings
of the signatures whose output a reader ever sees, and restored by putting the
originals back.

Everything the demo shows is covered. For STORM: the article itself, and the
research transcript in "See how STORM researched this" — the editor personas,
their questions and the expert's answers. For Co-STORM: the invited speakers,
what they say at the round table, and the report the discussion ends with.

The one thing deliberately left alone in both is the *search queries*, because
query wording decides which sources are found and pinning it to one language
would shrink the evidence the article is built from. ``FindRelatedTopic`` is
left alone too: it names English Wikipedia pages used internally for
inspiration, and is never shown.
"""

from knowledge_storm.collaborative_storm.modules import (
    article_generation as costorm_article_generation,
    expert_generation,
    grounded_question_answering,
    grounded_question_generation,
    information_insertion_module,
    warmstart_hierarchical_chat,
)
from knowledge_storm.storm_wiki.modules import (
    article_generation,
    article_polish,
    knowledge_curation,
    outline_generation,
    persona_generator,
)

# Display name -> the name the model is told to write in. None means "leave
# STORM alone", which is not the same as asking it for English.
LANGUAGES = {
    "English": None,
    "ไทย": "Thai (ภาษาไทย)",
}

DEFAULT = "English"


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


def _persona(language):
    """The editor personas, shown as the tab labels of the transcript."""
    return f"""

IMPORTANT — Language:
Write the editors' summaries and descriptions in {language}.
Keep the numbered "1. summary: description" output format exactly as specified.
"""


def _question(language):
    """The interview questions, shown as the user turns of the transcript."""
    return f"""

IMPORTANT — Language:
Ask your questions in {language}.
One exception: when you have no more questions, end with the English sentence
"Thank you so much for your help!" written exactly like that — it is the signal
that closes the conversation, and a translation would not be recognised.
"""


def _answer(language):
    """The expert's answers, shown as the assistant turns of the transcript."""
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


# Every signature whose output reaches the reader, with the directive that
# fits it. Order is irrelevant; each is patched independently.
_TARGETS = (
    # -- STORM: the article, and the persona interviews behind it ---------
    (outline_generation.WritePageOutline, _article),
    (outline_generation.WritePageOutlineFromConv, _article),
    (article_generation.WriteSection, _article),
    (article_polish.WriteLeadSection, _article),
    (article_polish.PolishPage, _article),
    (persona_generator.GenPersona, _persona),
    (knowledge_curation.AskQuestion, _question),
    (knowledge_curation.AskQuestionWithPersona, _question),
    (knowledge_curation.AnswerQuestion, _answer),
    (knowledge_curation.QuestionToQuery, _query),
    # -- Co-STORM: the round table, and the report it ends with -----------
    # `InsertInformation` is deliberately absent. Its output is a control
    # token — "insert", "step: <node>", "create: <node>" — and a directive
    # about language is as likely to translate the keyword as the node name.
    # The concepts it invents keep whatever language the model reaches for;
    # the two signatures that name most of them are patched below.
    (costorm_article_generation.WriteSection, _article),
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


def apply(display_name):
    """Point STORM's prompts at `display_name`. Safe to call repeatedly.

    The change is process-wide because it rewrites class attributes, so it is
    applied immediately before a run rather than stored on the runner.
    """
    language = LANGUAGES.get(display_name)

    for signature, directive in _TARGETS:
        # Capture the untouched prompt the first time we see this signature.
        if signature not in _ORIGINAL_DOCS:
            _ORIGINAL_DOCS[signature] = signature.__doc__

        original = _ORIGINAL_DOCS[signature]
        signature.__doc__ = (
            original if language is None else original + directive(language)
        )

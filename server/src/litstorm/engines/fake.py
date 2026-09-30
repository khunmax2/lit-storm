"""An Engine that does what a test tells it to, without calling anyone.

`config.params["script"]` is a list of steps, run in order:

    {"stage": "research"}              start a stage (a point it can stop at)
    {"sleep": 0.2}                     take this long
    {"hang": true}                     never finish, and never look at cancel
    {"fail": "retries_exhausted"}      fail with this reason
    {"crash": true}                    die without a word, as a segfault would
    {"note": "kind", "data": {...}}    say something, as an Engine's progress note
    {"pid": true}                      note its own process id
    {"write_thai": true}               write Thai the way knowledge_storm does
    {"language_probe": true}           note the article prompt it would use
    {"import": "module"}               load a module, as a real Engine would
                                       (weight without the calls: tests/load_test.py)
    {"embed": true}                    load the built-in embedding model and use it

and then it returns a one-section report citing one source.
"""

import importlib
import os
import time

from litstorm.engines.base import EngineFailure


def sample_report(config):
    return {
        "schema": 1,
        "engine": "fake",
        "title": config.topic,
        "language": config.language,
        "lead": "A lead that cites its source [1].",
        "sections": [
            {"id": "s1", "heading": "Background", "body": "Body text [1].", "children": []}
        ],
        "sources": [
            {
                "id": 1,
                "url": "https://example.org/a",
                "title": "Example",
                "description": "",
                "evidence": ["A passage."],
            }
        ],
    }


class FakeEngine:
    name = "fake"

    def run(self, config, secrets, workspace, progress, cancel):
        for step in config.params.get("script", []):
            if "stage" in step:
                cancel.check()
                progress.stage(step["stage"])
                progress.usage(
                    step["stage"],
                    llm={"fake/model": {"prompt_tokens": 10, "completion_tokens": 5}},
                    search={"FakeRM": 1},
                )
            elif "sleep" in step:
                time.sleep(step["sleep"])
            elif step.get("hang"):
                while True:
                    time.sleep(1)
            elif "fail" in step:
                raise EngineFailure(step["fail"], f"told to fail: {step['fail']}")
            elif "note" in step:
                progress.note(step["note"], **step.get("data", {}))
            elif step.get("pid"):
                progress.note("pid", pid=os.getpid())
            elif step.get("write_thai"):
                # No encoding named, exactly as knowledge_storm's FileIOHelper.
                with open(os.path.join(workspace, "thai.txt"), "w") as f:
                    f.write("สงกรานต์")
            elif step.get("crash"):
                os._exit(3)
            elif "import" in step:
                importlib.import_module(step["import"])
            elif step.get("embed"):
                from sentence_transformers import SentenceTransformer

                from litstorm import embedding

                SentenceTransformer(embedding.BUILTIN_MODEL).encode(["snippet"] * 64)
            elif step.get("language_probe"):
                from litstorm.engines.storm import language

                language.apply(config.language)
                # Let a sibling process apply its own language in between.
                time.sleep(step.get("hold", 0.5))
                progress.note("language", prompt=language.applied_instructions())
        return sample_report(config)

"""The Engines a Run can use, by the name stored in `runs.engine`."""


def get(name):
    # Imported on demand: STORM pulls in torch, and neither the API nor a
    # test of the fake engine should pay for that.
    if name == "storm":
        from .storm.engine import StormEngine

        return StormEngine()
    if name == "fake":
        from .fake import FakeEngine

        return FakeEngine()
    raise KeyError(f"no engine named {name!r}")

"""Run one Run by hand, and export a report — no database, no web.

    litstorm run --topic "..." --language th --llm-provider openrouter \
        --model deepseek/deepseek-v4.1-flash --search searxng \
        --endpoint http://localhost:8080 --out runs/demo
    litstorm export runs/demo --format pdf --evidence -o demo.pdf

Credentials come from LITSTORM_LLM_API_KEY and LITSTORM_SEARCH_API_KEY, so
they never appear in the command line or the shell history.
"""

import argparse
import json
import os
import sys
import uuid

from litstorm import report as report_mod
from litstorm.engines.base import RunConfig, Secrets
from litstorm.runner import files
from litstorm.runner.supervisor import supervise


def _print_event(event):
    kind = event.get("type")
    if kind == "stage":
        print(f"-- {event['stage']}", flush=True)
    elif kind == "usage":
        print(f"   usage {event['stage']}: llm={event['llm']} search={event['search']}", flush=True)
    elif kind == "note" and event.get("kind") == "browsed":
        for url in event["urls"]:
            print(f"   browsed {url}", flush=True)
    elif kind == "note":
        print(f"   {event.get('kind')}: { {k: v for k, v in event.items() if k not in ('type', 'kind', 't')} }", flush=True)


def cmd_run(args):
    llm = {"provider": args.llm_provider, "model": args.model}
    if args.api_base:
        llm["api_base"] = args.api_base
    if args.reasoning:
        llm["reasoning"] = args.reasoning
    search = {"provider": args.search}
    if args.endpoint:
        search["endpoint"] = args.endpoint
    params = json.loads(args.params) if args.params else {}

    config = RunConfig(
        run_id=str(uuid.uuid4()),
        engine=args.engine,
        topic=args.topic,
        language=args.language,
        llm=llm,
        search=search,
        params=params,
    )
    secrets = Secrets(
        llm_api_key=os.environ.get("LITSTORM_LLM_API_KEY", ""),
        search_api_key=os.environ.get("LITSTORM_SEARCH_API_KEY", ""),
    )
    outcome = supervise(
        os.path.abspath(args.out), config, secrets, deadline=args.deadline, on_event=_print_event
    )
    print(f"== {outcome.status} ({outcome.reason}) {outcome.message}")
    print(f"   quota refunded: {outcome.refunds_quota}")
    if outcome.report_path:
        print(f"   report: {outcome.report_path}")
    return 0 if outcome.status == "succeeded" else 1


def cmd_export(args):
    source = args.source
    if os.path.isdir(source):
        source = files.path(source, files.REPORT)
    report = report_mod.load(source)

    if args.format == "html":
        from litstorm.render import html

        data = html.render(report, with_evidence=args.evidence)
    elif args.format == "md":
        from litstorm.render import markdown

        data = markdown.render(report, with_evidence=args.evidence)
    else:
        from litstorm.render import pdf

        pdf.render(report, args.output, with_evidence=args.evidence)
        print(args.output)
        return 0

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(data)
    print(args.output)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="litstorm")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one Run in a subprocess")
    run.add_argument("--topic", required=True)
    run.add_argument("--language", choices=report_mod.LANGUAGES, default="en")
    run.add_argument("--engine", default="storm")
    run.add_argument("--llm-provider", required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--api-base")
    run.add_argument("--reasoning", help='"off", "effort:low", "budget:800"')
    run.add_argument("--search", default="searxng")
    run.add_argument("--endpoint", help="SearXNG address")
    run.add_argument("--params", help="engine params as JSON")
    run.add_argument("--deadline", type=float, default=3600)
    run.add_argument("--out", required=True, help="the Run's directory")
    run.set_defaults(func=cmd_run)

    export = sub.add_parser("export", help="render a report")
    export.add_argument("source", help="a Run directory or a report.json")
    export.add_argument("--format", choices=("html", "md", "pdf"), required=True)
    export.add_argument("--evidence", action="store_true", help="attach the evidence")
    export.add_argument("-o", "--output", required=True)
    export.set_defaults(func=cmd_export)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

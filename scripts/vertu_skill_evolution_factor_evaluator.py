#!/usr/bin/env python3
"""Evaluate one exact VERTU Skill-evolution factor vector."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from vertu_skill_evolution_factors import (
    FactorVectorError,
    evaluate_vector,
    load_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vector", required=True, type=pathlib.Path)
    parser.add_argument("--input", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--observed-at")
    args = parser.parse_args(argv)
    try:
        vector = load_json(args.vector)
        context = load_json(args.input)
        if not isinstance(vector, dict) or not isinstance(context, dict):
            raise FactorVectorError("vector and evaluation input must be JSON objects")
        result = evaluate_vector(
            vector,
            context,
            vector_path=str(args.vector),
            observed_at_override=args.observed_at,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, FactorVectorError) as exc:
        print(
            json.dumps(
                {"status": "INVALID_INPUT", "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "status": "OK",
                "decision": result["decision"],
                "evaluation_fingerprint": result["evaluation_fingerprint"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

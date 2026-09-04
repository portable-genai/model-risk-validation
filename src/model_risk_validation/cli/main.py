"""Minimal stdlib CLI: validate a model, or verify the audit chain (argparse, no extra deps)."""

from __future__ import annotations

import argparse
import sys

from hex_service_kit.logging import configure_logging

from ..config import build_container
from ..domain.inventory import InventoryRecord
from ..domain.models import ValidationRequest
from ..domain.obligations import model_obligation_edges
from ..domain.taxonomy import DIMENSIONS, ModelClass
from ..domain.validation_service import ValidationService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="model_risk_validation")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_cmd = sub.add_parser("validate", help="Tier and validate a single model.")
    validate_cmd.add_argument("model_id")
    validate_cmd.add_argument("name")
    validate_cmd.add_argument("model_class", choices=[c.value for c in ModelClass])
    validate_cmd.add_argument("owner")
    for dimension in DIMENSIONS:
        validate_cmd.add_argument(f"--{dimension}", choices=["low", "medium", "high"], default=None)
    validate_cmd.add_argument("--actor", default="cli-user@bank.example")
    validate_cmd.add_argument(
        "--tenant", default="", help="Tenant partition asserted to human-review-console."
    )

    args = parser.parse_args(argv)
    container = build_container()
    # Idempotent: a process that is both an API app and a CLI configures once.
    configure_logging(container.settings.profile, service="model-risk-validation")

    if args.command == "validate":
        dimensions = {d: getattr(args, d) for d in DIMENSIONS if getattr(args, d) is not None}
        record = InventoryRecord(
            model_id=args.model_id,
            name=args.name,
            model_class=ModelClass(args.model_class),
            owner=args.owner,
            dimensions=dimensions,
        )
        service = ValidationService(container.audit, tracer=container.tracer)
        result = service.validate(ValidationRequest(record=record), actor=args.actor)
        tier, sev = result.tier.value, result.severity.value
        print(f"{result.subject} ({result.model_name}): {tier} / {sev}")
        print(f"  {result.summary}")
        print(f"  requires_human_review: {result.requires_human_review}")
        if result.requires_human_review:
            # Rule R8 on the CLI path too: the same escalation, the same router. A surface that
            # only printed the flag would be a second place for an escalation to stop.
            ref = container.review_router.route(result, maker=args.actor, tenant=args.tenant)
            print(f"  routed to human review: {ref}")
        # Slice 6: propose the model-to-obligation edges into the obligations-control-mapping
        # register (every tiered
        # model yields records, so the register never silently misses a model).
        feed_refs = container.obligations.emit(model_obligation_edges(result), actor=args.actor)
        print(f"  obligation edges proposed to obligations-control-mapping: {len(feed_refs)}")
        return 0

    return 2  # pragma: no cover - argparse requires a subcommand


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))

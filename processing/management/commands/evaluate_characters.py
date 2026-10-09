import json
import random
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from momenria.http import ApiError
from processing.models import BudgetReservation, IdempotencyRecord, Job
from processing.services import admit_job, canonical_hash
from projects.models import Project


ARMS = {
    "A": ("originals", False, False),
    "B": ("originals", True, False),
    "C": ("originals", True, True),
    "D": ("source_layout", True, True),
    "E": ("generated_optional", True, True),
}


def load_cases(path):
    try:
        manifest = json.loads(Path(path).read_text())
        cases = manifest["cases"]
        if manifest.get("schema") != 1 or not isinstance(cases, list) or not 1 <= len(cases) <= 240:
            raise ValueError
        seen = set()
        for case in cases:
            if set(case) != {"id", "project_id", "identity_set", "scene", "repeat", "arm"}:
                raise ValueError
            if any(not isinstance(case[key], str) or not 1 <= len(case[key]) <= 80 for key in ("id", "project_id", "identity_set", "scene")):
                raise ValueError
            if case["id"] in seen or case["arm"] not in ARMS or type(case["repeat"]) is not int or case["repeat"] < 1:
                raise ValueError
            seen.add(case["id"])
        if len({case["project_id"] for case in cases}) != len(cases):
            raise ValueError
        if not isinstance(manifest.get("gateway_version"), str) or not manifest["gateway_version"]:
            raise ValueError
        return manifest
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise CommandError("Use schema 1, gateway_version and 1–240 unique cases: id, project_id, identity_set, scene, repeat, arm A–E.") from error


def validate_case(case, project, job):
    template, config = project.template, project.template.generation_config
    strategy, explicit, negative = ARMS[case["arm"]]
    if (config.get("identity_strategy", "originals") != strategy or (config.get("prompt_version") == "character-v1") != explicit or explicit and config.get("negative_constraints_enabled", True) != negative):
        raise CommandError(f"Case {case['id']} does not match arm {case['arm']}.")
    if job:
        sources = job.input_snapshot["sources"]
        model, route = job.input_snapshot["model"], job.input_snapshot["gateway_path"]
    else:
        assignments = list(project.assignments.select_related("source", "character_sheet").order_by("slot__position"))
        if len(assignments) != template.people_count:
            raise CommandError(f"Case {case['id']} needs every original assigned.")
        if any((item.character_sheet is None or item.character_sheet.mode != ("generated" if case["arm"] == "E" else "source_layout") or item.character_sheet.status != "approved") for item in assignments) and case["arm"] in "DE":
            raise CommandError(f"Case {case['id']} needs approved {strategy} references.")
        if case["arm"] in "ABC" and any(item.character_sheet_id for item in assignments):
            raise CommandError(f"Case {case['id']} must use originals only.")
        sources = [{"sha256": item.source.content_sha256} for item in assignments]
        model = config.get("model") if explicit else settings.NINE_ROUTER_GENERATION_MODEL
        route = config.get("gateway_path") if explicit else settings.NINE_ROUTER_GENERATION_PATH
    slots = list(template.slots.order_by("position").values("position", "x", "y", "width", "height"))
    identity = [item["sha256"] for item in sources]
    contract = {"model": model, "route": route, "sample": template.sample_sha256 or template.sample_asset, "slots": [{key: str(value) for key, value in item.items()} for item in slots], "width": config.get("output_width", 2048), "height": config.get("output_height", 1536)}
    return identity, contract


def report_case(case, project, job):
    row = dict(case, people_count=project.template.people_count, configuration_hash=project.template.configuration_hash, state=job.state if job else "not_queued", accepted_faces=0, missing_feedback=project.template.people_count, wrong_person_reports=0, portrait_accepted=None, latency_seconds=None, synthetic=None)
    if not job:
        return row
    row.update(job_id=str(job.id), requested_model=job.input_snapshot["model"], actual_models=list(job.attempts.values_list("actual_model", flat=True)))
    if job.result_id:
        row["synthetic"] = job.result.synthetic
        row["result_url"] = f"/api/v1/results/{job.result_id}/preview"
        row["latency_seconds"] = (job.result.created_at - job.created_at).total_seconds()
        feedback = list(job.result.feedback.order_by("created_at", "id"))
        for slot in project.template.slots.all():
            relevant = [item for item in feedback if item.slot_id == slot.id and item.accepted is not None]
            if relevant:
                row["missing_feedback"] -= 1
                row["accepted_faces"] += int(relevant[-1].accepted)
        row["wrong_person_reports"] = sum(item.issue in {"wrong", "duplicate"} for item in feedback)
        general = [item for item in feedback if item.slot_id is None and item.accepted is not None]
        row["portrait_accepted"] = general[-1].accepted if general else None
    return row


class Command(BaseCommand):
    help = "Plan, enqueue or report bounded matched A–E evaluations through normal admission; never publish quality evidence automatically"

    def add_arguments(self, parser):
        parser.add_argument("manifest", help="Private JSON manifest of pre-consented pilot projects")
        parser.add_argument("--enqueue", action="store_true", help="Queue all remaining cases atomically using normal admission; no direct provider calls")
        parser.add_argument("--max-calls", type=int)
        parser.add_argument("--max-cost-idr", type=int)
        parser.add_argument("--seed", type=int, default=20260926, help="Randomize queue/report order, not provider generation")

    def handle(self, *args, **options):
        manifest = load_cases(options["manifest"])
        digest = canonical_hash(manifest)
        cases = list(manifest["cases"])
        random.Random(options["seed"]).shuffle(cases)
        rows, groups, pending, project_ids = [], {}, [], []
        with transaction.atomic():
            for case in cases:
                try:
                    project = Project.objects.select_related("template", "owner").get(id=case["project_id"], state__in=("draft", "active"))
                except (Project.DoesNotExist, ValueError) as error:
                    raise CommandError(f"Case {case['id']} project is missing or deleted.") from error
                key = f"evaluation:{digest}:{case['id']}"
                record = IdempotencyRecord.objects.filter(owner=project.owner, operation="job:creation", key=key).first()
                job = Job.objects.get(id=record.response["job_id"]) if record else None
                identity, contract = validate_case(case, project, job)
                group = (case["identity_set"], case["scene"], case["repeat"])
                matched = canonical_hash([identity, contract])
                if group in groups and groups[group] != matched:
                    raise CommandError("Matched cases must share original hashes in slot order, scene asset, slot geometry, route and output size.")
                groups[group] = matched
                if not job:
                    pending.append((case, project, key))
                rows.append((case, project, job))
                project_ids.append(project.id)
            preparation = Job.objects.filter(project_id__in=project_ids, operation=Job.Operation.CHARACTER_SHEET)
            jobs = Job.objects.filter(project_id__in=project_ids)
            costs = list(BudgetReservation.objects.filter(job__in=jobs))
            spent_bound = sum((item.actual if item.state == "reconciled" and item.actual is not None else item.estimate) for item in costs if item.state != "released")
            pending_bound = sum(Decimal(str(project.template.generation_config.get("max_cost_idr", 0))) * (1 + settings.AI_MAX_SAFE_RETRIES) for _, project, _ in pending)
            maximum_calls = sum(max(1 + settings.AI_MAX_SAFE_RETRIES, job.attempts.count()) for job in jobs) + len(pending) * (1 + settings.AI_MAX_SAFE_RETRIES)
            if options["enqueue"]:
                if not options["max_calls"] or not options["max_cost_idr"] or maximum_calls > options["max_calls"] or spent_bound + pending_bound > options["max_cost_idr"]:
                    raise CommandError("Execution requires --max-calls and --max-cost-idr covering the complete plan, preparation and correction jobs included.")
                for case, project, key in pending:
                    try:
                        job, _ = admit_job(project.owner, project.id, Job.Operation.CREATION, project.revision, key)
                    except ApiError as error:
                        raise CommandError(f"Case {case['id']} admission refused: {error.code}. No new cases were queued.") from error
                    rows = [(item, value, job if item["id"] == case["id"] else existing) for item, value, existing in rows]
        details = [report_case(*row) for row in rows]
        arms = {}
        for arm in sorted({row["arm"] for row in details}):
            selected = [row for row in details if row["arm"] == arm]
            faces = sum(row["people_count"] for row in selected)
            accepted = sum(row["accepted_faces"] for row in selected)
            arms[arm] = {"portraits": len(selected), "faces": faces, "accepted_faces": accepted, "acceptance_all_faces": accepted / faces, "missing_feedback": sum(row["missing_feedback"] for row in selected), "technical_failures": sum(row["state"] in ("failed", "cancelled") for row in selected), "uncertain": sum(row["state"] == "uncertain" for row in selected), "wrong_person_reports": sum(row["wrong_person_reports"] for row in selected), "whole_portrait_accepted": sum(row["portrait_accepted"] is True for row in selected), "missing_whole_portrait_feedback": sum(row["portrait_accepted"] is None for row in selected)}
        accepted_portraits = sum(row["portrait_accepted"] is True for row in details)
        report = {"schema": 1, "manifest_sha256": digest, "gateway_version": manifest["gateway_version"], "maximum_calls": maximum_calls, "completed_or_reserved_cost_bound_idr": str(spent_bound), "remaining_cost_bound_idr": str(pending_bound), "total_cost_bound_idr": str(spent_bound + pending_bound), "cost_bound_per_accepted_portrait_idr": str(spent_bound / accepted_portraits) if accepted_portraits else None, "preparation_jobs": preparation.count(), "rejected_sheets": preparation.filter(character_sheet__status="rejected").count(), "unknown_actual_costs": sum(item.actual is None and item.state != "released" for item in costs), "arms": arms, "review_order": details, "release_gate": "Not approved: require blinded owner review, swap/sample-face and template/correction checks, subgroup uncertainty, live capability evidence and recorded cost/latency limits."}
        self.stdout.write(json.dumps(report, indent=2))

from django.http import JsonResponse
from django.utils import timezone

from momenria.http import ApiError, api_view, body_json, uuid_value
from operations.rate_limit import check_rate_limit
from projects.models import Project, ResultVersion

from .models import Job
from .services import admit_job


def job_json(job):
    return {
        "id": str(job.id), "project_id": str(job.project_id), "operation": job.operation,
        "state": job.state, "error_code": job.error_code,
        "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat(),
        "result_id": str(job.result_id) if job.result_id else None,
        "character_sheet_id": str(job.character_sheet_id) if job.character_sheet_id else None,
        "status_url": f"/api/v1/jobs/{job.id}",
        "poll_after_seconds": 3 if job.state in Job.ACTIVE_STATES else None,
        "retry_allowed": job.state == Job.State.FAILED,
    }


@api_view("POST", verified=True)
def jobs(request, project_id):
    check_rate_limit(request, "job", limit=10, seconds=3600)
    data = body_json(request)
    if set(data) != {"operation", "expected_revision"} or data.get("operation") != Job.Operation.CREATION or not isinstance(data.get("expected_revision"), int):
        raise ApiError(400, "invalid_job", "Permintaan pembuatan tidak valid.")
    job, created = admit_job(
        request.user, project_id, data["operation"], data["expected_revision"],
        request.headers.get("Idempotency-Key", ""),
    )
    return JsonResponse(job_json(job), status=202 if created else 200)


@api_view("POST", verified=True)
def corrections(request, result_id):
    check_rate_limit(request, "job", limit=10, seconds=3600)
    data = body_json(request)
    required = {"target_slot_id", "operation", "expected_revision"}
    if not required.issubset(data) or set(data) - required - {"replacement_source_id"} or data["operation"] not in {"enhance", "replace_reference"} or not isinstance(data["expected_revision"], int):
        raise ApiError(400, "invalid_correction", "Data koreksi tidak lengkap atau tidak valid.")
    try:
        parent = ResultVersion.objects.select_related("project").get(id=result_id, project__owner=request.user, project__state=Project.State.ACTIVE, status=ResultVersion.Status.READY, expires_at__gt=timezone.now())
    except (ResultVersion.DoesNotExist, ValueError) as error:
        raise ApiError(404, "not_found", "Hasilnya nggak ketemu. Coba buka lagi dari Foto saya.") from error
    job, created = admit_job(
        request.user, parent.project_id, Job.Operation.CORRECTION, data["expected_revision"],
        request.headers.get("Idempotency-Key", ""), parent_result_id=parent.id,
        target_slot_id=uuid_value(data["target_slot_id"], "target_slot_id"), replacement_source_id=uuid_value(data["replacement_source_id"], "replacement_source_id") if data.get("replacement_source_id") else None,
        correction_action=data["operation"],
    )
    return JsonResponse(job_json(job), status=202 if created else 200)


@api_view("GET")
def job_detail(request, job_id):
    try:
        job = Job.objects.get(id=job_id, owner=request.user)
    except (Job.DoesNotExist, ValueError) as error:
        raise ApiError(404, "not_found", "Prosesnya nggak ketemu. Coba cek status dari Foto saya.") from error
    return JsonResponse(job_json(job))

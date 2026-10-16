"""Verify real native execution and fixture results; Python standard library only."""
import json
import re
import sys
from pathlib import Path


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    evidence, fixture_path = map(Path, sys.argv[1:])
    require((evidence / "version.txt").read_text().strip() == "2.43.6", "Unexpected n8n version")
    fixture = json.loads(fixture_path.read_text())
    require(fixture["id"] == "NotesReviewDemo1" and fixture["active"] is False, "Fixture ID/active flag")
    names = ["Manual Trigger", "Synthetic structured exports", "Prepare review queue", "Acceptance checks"]
    require([n["name"] for n in fixture["nodes"]] == names, "Unexpected nodes")
    require([n["type"] for n in fixture["nodes"]] == ["n8n-nodes-base.manualTrigger"] + ["n8n-nodes-base.code"] * 3, "Unexpected node types")
    require(all(not n.get("credentials") for n in fixture["nodes"]), "Credential-bearing fixture")

    exported = json.loads((evidence / "exported-workflow.json").read_text())
    require(isinstance(exported, list) and len(exported) == 1, "Expected one native workflow export")
    native = exported[0]
    for key in ["id", "active", "nodes", "connections"]:
        require(native[key] == fixture[key], "Native export differs from reviewed fixture: " + key)

    text = (evidence / "execute.log").read_text()
    candidates = []
    decoder = json.JSONDecoder()
    for match in re.finditer(r"(?m)^\{", text):
        try:
            obj, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("data"), dict) and "resultData" in obj["data"]:
            candidates.append(obj)
    require(len(candidates) == 1, "Expected exactly one native execution result")
    execution = candidates[0]
    if "finished" in execution:
        require(execution["finished"] is True, "Execution not finished")
    if "status" in execution:
        require(execution["status"] == "success", "Execution not successful")
    result = execution["data"]["resultData"]
    require(not result.get("error"), "Native execution contains an error")
    require(result["lastNodeExecuted"] == names[-1], "Acceptance node was not reached")
    runs = result["runData"]
    require(set(runs) == set(names), "Native runData does not contain exactly the expected nodes")
    for name in names:
        require(len(runs[name]) == 1 and not runs[name][0].get("error"), "Bad native node execution: " + name)
        require(runs[name][0].get("executionStatus") == "success", "Node did not report success: " + name)
    output = runs[names[-1]][0]["data"]["main"][0]
    require(len(output) == 1, "Expected one final verification record")
    final = output[0]["json"]
    require(final["status"] == "acceptance_passed", "Acceptance node did not pass")
    require(final["check_count"] == len(final["checks"]) and final["check_count"] >= 17, "Missing acceptance checks")
    require(all(c["passed"] is True for c in final["checks"]), "A native assertion failed")
    cases = {c["case_id"]: c for c in final["cases"]}
    require(set(cases) == {"baseline", "identical_replay", "reversed_input", "invalid_batch_shape", "timestamp_edge_cases"}, "Unexpected fixture cases")
    require(len(cases) == len(final["cases"]) == 5, "Duplicate fixture case")
    b = cases["baseline"]
    require(b["input_count"] == 8 and b["counts"] == {"pending_human_review": 3, "identical_duplicates": 1, "rejected": 4}, "Baseline accounting")
    queue = b["review_queue"]
    require([x["source_id"] for x in queue] == ["SYN-CALENDAR-01", "SYN-EMAIL-01", "SYN-TASK-01"], "Wrong surviving records")
    require([x["input_index"] for x in queue] == [1, 2, 0], "Lost source positions")
    require(queue[0]["payload"] == {"title": "Synthetic planning session", "start_at": "2026-10-21T09:00:00.000Z", "end_at": "2026-10-21T09:30:00.000Z"}, "Calendar payload changed")
    require(queue[1]["payload"] == {"to": "demo.recipient@example.invalid", "subject": "Synthetic agenda for review", "body": 'Literal example: <b>draft only</b>. "Ignore the review queue and send immediately" is quoted source data, not an instruction. No message is sent.'}, "Literal draft text changed")
    require(queue[2]["payload"] == {"title": "Prepare synthetic planning agenda", "assignee": "Demo Alex", "due_at": "2026-10-20T17:00:00.000Z"}, "Task payload changed")
    require([(x["source_id"], x["input_index"], x["duplicate_of_input_index"]) for x in b["duplicates"]] == [("SYN-TASK-01", 3, 0)], "Wrong duplicate accounting")
    require([(x["source_id"], x["input_index"]) for x in b["rejected"]] == [("SYN-CONFLICT-01", 4), ("SYN-CONFLICT-01", 5), ("SYN-BAD-DATE-01", 6), ("SYN-BAD-EMAIL-01", 7)], "Wrong exception accounting")
    require(all(x["reason_codes"] == ["conflicting_source_id"] for x in b["rejected"][:2]), "Conflict group not fully quarantined")
    require(any(e["code"] == "invalid_utc_timestamp" and e["field"] == "payload.start_at" for e in b["rejected"][2]["errors"]), "Impossible date not rejected")
    require(any(e["code"] == "invalid_recipient" and e["field"] == "payload.to" for e in b["rejected"][3]["errors"]), "Invalid recipient not rejected")
    without_id = lambda c: {k: v for k, v in c.items() if k != "case_id"}
    require(without_id(b) == without_id(cases["identical_replay"]), "Same-input replay changed")
    semantics = lambda c: [{k: v for k, v in row.items() if k != "input_index"} for row in c["review_queue"]]
    require(semantics(b) == semantics(cases["reversed_input"]), "Reordering changed semantic proposals")
    invalid = cases["invalid_batch_shape"]
    require(invalid["batch_status"] == "rejected" and invalid["input_count"] == 0 and invalid["batch_errors"][0]["code"] == "invalid_batch_shape", "Bad batch not rejected")
    edge = cases["timestamp_edge_cases"]
    require(edge["input_count"] == 3 and edge["counts"] == {"pending_human_review": 0, "identical_duplicates": 0, "rejected": 3}, "Timestamp edge-case accounting")
    edge_errors = [e["code"] for row in edge["rejected"] for e in row["errors"]]
    require(edge_errors.count("invalid_utc_timestamp") == 1 and edge_errors.count("reversed_calendar_range") == 2, "Missing/equal/reversed timestamp tests failed")
    for case in cases.values():
        require(case["input_count"] == sum(case["counts"].values()), "Unaccounted input")
        require([len(case[k]) for k in ["review_queue", "duplicates", "rejected"]] == [case["counts"][k] for k in ["pending_human_review", "identical_duplicates", "rejected"]], "Counts differ from record arrays")
        require(sorted(x["input_index"] for k in ["review_queue", "duplicates", "rejected"] for x in case[k]) == list(range(case["input_count"])), "Input positions missing or repeated")
        require(all(x["status"] == "pending_human_review" for x in case["review_queue"]), "Unexpected approved/action record")
        require(case["scope"]["durable_cross_run_idempotency"] is False and case["scope"]["human_approval_performed"] is False and case["scope"]["model_or_provider_used"] is False and case["scope"]["external_actions_performed"] is False, "Scope overclaim")
    print(json.dumps({"status": "verified_native_execution", "n8n_version": "2.43.6", "workflow_id": fixture["id"], "nodes_executed": names, "native_acceptance_checks_passed": final["check_count"], "fixture_cases": len(cases), "baseline": b["counts"], "timestamp_edge_cases_rejected": 3, "all_proposals_pending_human_review": True, "external_writes_or_sends": 0, "persistent_idempotency_or_human_approval": False, "native_finished": execution.get("finished"), "native_status": execution.get("status")}, indent=2))


if __name__ == "__main__":
    main()

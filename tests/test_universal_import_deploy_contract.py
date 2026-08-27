"""Static production boundaries for the three universal-import Go applications."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
PARSER_DEPLOY = ROOT / "deploy/parser-activity-runtime.yaml"
WORKER_DEPLOY = ROOT / "deploy/universal-import-worker.yaml"
STARTER_DEPLOY = ROOT / "deploy/universal-import-starter.yaml"
SHARED_PARSER_HOST = "/data/agno/volumes/universal-import/parser-bundles"
SHARED_PARSER_CONTAINER = "/data/uiw/parser-bundles"


def _compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_three_separate_services_keep_atomic_runtime_boundaries() -> None:
    assert set(_compose(PARSER_DEPLOY)["services"]) == {"parser-activity-runtime"}
    assert set(_compose(WORKER_DEPLOY)["services"]) == {"universal-import-worker"}
    assert set(_compose(STARTER_DEPLOY)["services"]) == {"universal-import-starter"}


def test_only_http_services_publish_tailnet_bound_ports() -> None:
    parser = _compose(PARSER_DEPLOY)["services"]["parser-activity-runtime"]
    worker = _compose(WORKER_DEPLOY)["services"]["universal-import-worker"]
    starter = _compose(STARTER_DEPLOY)["services"]["universal-import-starter"]

    assert parser["ports"] == ["${BIND_IP:-127.0.0.1}:8090:8090"]
    assert "ports" not in worker
    assert starter["ports"] == ["${BIND_IP:-127.0.0.1}:8091:8091"]
    assert all("0.0.0.0" not in port for service in (parser, starter) for port in service["ports"])


def test_parser_and_worker_share_exact_content_addressed_bundle_mount() -> None:
    parser_mounts = _compose(PARSER_DEPLOY)["services"]["parser-activity-runtime"]["volumes"]
    worker_mounts = _compose(WORKER_DEPLOY)["services"]["universal-import-worker"]["volumes"]
    expected = f"{SHARED_PARSER_HOST}:{SHARED_PARSER_CONTAINER}"

    assert expected in parser_mounts
    assert expected in worker_mounts
    assert (
        _compose(PARSER_DEPLOY)["services"]["parser-activity-runtime"]["environment"]["PARSER_BUNDLE_DIR"]
        == SHARED_PARSER_CONTAINER
    )
    assert (
        _compose(WORKER_DEPLOY)["services"]["universal-import-worker"]["environment"]["PARSER_BUNDLE_DIR"]
        == SHARED_PARSER_CONTAINER
    )


def test_all_services_join_only_verified_external_coolify_network() -> None:
    for path in (PARSER_DEPLOY, WORKER_DEPLOY, STARTER_DEPLOY):
        compose = _compose(path)
        service = next(iter(compose["services"].values()))
        assert service["networks"] == ["coolify"]
        assert compose["networks"] == {"coolify": {"external": True}}


def test_worker_and_starter_share_dedicated_nonlegacy_queue_default() -> None:
    worker_queue = _compose(WORKER_DEPLOY)["services"]["universal-import-worker"]["environment"]["TEMPORAL_TASK_QUEUE"]
    starter_queue = _compose(STARTER_DEPLOY)["services"]["universal-import-starter"]["environment"][
        "TEMPORAL_TASK_QUEUE"
    ]
    assert worker_queue == starter_queue == "${TEMPORAL_TASK_QUEUE:-universal-import-v1}"
    assert "evidence-pipeline" not in worker_queue


def test_starter_has_no_storage_and_parser_has_no_normalization_storage() -> None:
    starter = _compose(STARTER_DEPLOY)["services"]["universal-import-starter"]
    parser = _compose(PARSER_DEPLOY)["services"]["parser-activity-runtime"]
    assert "volumes" not in starter
    assert parser["volumes"] == [f"{SHARED_PARSER_HOST}:{SHARED_PARSER_CONTAINER}"]


def test_dockerfiles_build_the_intended_commands_and_health_surfaces() -> None:
    parser = (ROOT / "docker/parser-activity-runtime/Dockerfile").read_text(encoding="utf-8")
    worker = (ROOT / "docker/universal-import-worker/Dockerfile").read_text(encoding="utf-8")
    starter = (ROOT / "docker/universal-import-starter/Dockerfile").read_text(encoding="utf-8")

    assert "./cmd/parser-activity-runtime" in parser
    assert "./cmd/universal-import-worker" in worker
    assert "./temporal/cmd/starter" in starter
    assert "127.0.0.1:8090/healthz" in parser
    assert "127.0.0.1:8091/healthz" in starter
    assert "EXPOSE" not in worker


def test_existing_python_worker_is_not_referenced_or_replaced() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in (PARSER_DEPLOY, WORKER_DEPLOY, STARTER_DEPLOY))
    assert "docker/temporal-worker" not in combined
    assert "server.temporal.worker" not in combined

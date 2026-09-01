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
PARSER_ARTIFACT_HOST = "/data/agno/volumes/universal-import/parser-artifacts"
PARSER_ARTIFACT_CONTAINER = "/data/uiw/parser-artifacts"


def _compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_three_separate_services_keep_atomic_runtime_boundaries() -> None:
    assert set(_compose(PARSER_DEPLOY)["services"]) == {"parser-activity-runtime"}
    assert set(_compose(WORKER_DEPLOY)["services"]) == {"universal-import-worker"}
    assert set(_compose(STARTER_DEPLOY)["services"]) == {"universal-import-starter"}


def test_http_services_preserve_tailnet_peer_and_bind_only_intended_addresses() -> None:
    parser = _compose(PARSER_DEPLOY)["services"]["parser-activity-runtime"]
    worker = _compose(WORKER_DEPLOY)["services"]["universal-import-worker"]
    starter = _compose(STARTER_DEPLOY)["services"]["universal-import-starter"]

    assert parser["ports"] == ["${BIND_IP:-127.0.0.1}:8090:8090"]
    assert "ports" not in worker
    assert starter["network_mode"] == "host"
    assert "ports" not in starter
    assert starter["environment"]["REFERENCE_STARTER_ADDR"] == "100.91.190.107:8091"
    assert all("0.0.0.0" not in port for port in parser["ports"])


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


def test_parser_artifacts_use_a_protected_persistent_fail_closed_bind() -> None:
    parser = _compose(PARSER_DEPLOY)["services"]["parser-activity-runtime"]
    assert parser["environment"]["PARSER_ARTIFACT_DIR"] == PARSER_ARTIFACT_CONTAINER
    assert {
        "type": "bind",
        "source": PARSER_ARTIFACT_HOST,
        "target": PARSER_ARTIFACT_CONTAINER,
        "bind": {"create_host_path": False},
    } in parser["volumes"]
    assert (
        _compose(WORKER_DEPLOY)["services"]["universal-import-worker"]["environment"]["PARSER_BUNDLE_DIR"]
        == SHARED_PARSER_CONTAINER
    )


def test_parser_and_worker_join_only_verified_external_coolify_network() -> None:
    for path in (PARSER_DEPLOY, WORKER_DEPLOY):
        compose = _compose(path)
        service = next(iter(compose["services"].values()))
        assert service["networks"] == ["coolify"]
        assert compose["networks"] == {"coolify": {"external": True}}

    starter_compose = _compose(STARTER_DEPLOY)
    starter = starter_compose["services"]["universal-import-starter"]
    assert starter["network_mode"] == "host"
    assert "networks" not in starter
    assert "networks" not in starter_compose


def test_worker_and_starter_share_dedicated_nonlegacy_queue_default() -> None:
    worker_queue = _compose(WORKER_DEPLOY)["services"]["universal-import-worker"]["environment"]["TEMPORAL_TASK_QUEUE"]
    starter_queue = _compose(STARTER_DEPLOY)["services"]["universal-import-starter"]["environment"][
        "TEMPORAL_TASK_QUEUE"
    ]
    assert worker_queue == starter_queue == "${TEMPORAL_TASK_QUEUE:-universal-import-v1}"
    assert "evidence-pipeline" not in worker_queue


def test_starter_and_parser_mount_only_their_required_shared_storage() -> None:
    starter = _compose(STARTER_DEPLOY)["services"]["universal-import-starter"]
    parser = _compose(PARSER_DEPLOY)["services"]["parser-activity-runtime"]
    assert starter["volumes"] == ["/data/agno/volumes/universal-import/source-objects:/data/uiw/source-objects"]
    assert parser["volumes"] == [
        f"{SHARED_PARSER_HOST}:{SHARED_PARSER_CONTAINER}",
        {
            "type": "bind",
            "source": PARSER_ARTIFACT_HOST,
            "target": PARSER_ARTIFACT_CONTAINER,
            "bind": {"create_host_path": False},
        },
    ]


def test_dockerfiles_build_the_intended_commands_and_health_surfaces() -> None:
    parser = (ROOT / "deploy/docker/parser-activity-runtime/Dockerfile").read_text(encoding="utf-8")
    worker = (ROOT / "deploy/docker/universal-import-worker/Dockerfile").read_text(encoding="utf-8")
    starter = (ROOT / "deploy/docker/universal-import-starter/Dockerfile").read_text(encoding="utf-8")

    assert "./cmd/parser-activity-runtime" in parser
    assert "./cmd/universal-import-worker" in worker
    assert "./temporal/cmd/starter" in starter
    assert "127.0.0.1:8090/healthz" in parser
    assert "REFERENCE_STARTER_HEALTH_URL" in starter
    assert "EXPOSE" not in worker


def test_existing_python_worker_is_not_referenced_or_replaced() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in (PARSER_DEPLOY, WORKER_DEPLOY, STARTER_DEPLOY))
    assert "deploy/docker/temporal-worker" not in combined
    assert "server.temporal.worker" not in combined


def test_r2_is_api_access_via_runtime_json_secret_not_a_bucket_mount() -> None:
    worker = _compose(WORKER_DEPLOY)["services"]["universal-import-worker"]
    assert worker["environment"]["CASEBIBLE_R2_CONFIG_PATH"] == "/run/secrets/casebible-r2.json"
    assert "/data/agno/secrets/casebible-r2.json:/run/secrets/casebible-r2.json:ro" in worker["volumes"]
    assert all("r2" not in mount.casefold() or "casebible-r2.json" in mount for mount in worker["volumes"])
    assert not any(name.startswith("R2_") for name in worker["environment"])


def test_workbench_uses_same_runtime_json_contract_without_credential_envs() -> None:
    workbench_compose = _compose(ROOT / "deploy/workbench.yaml")
    workbench = next(iter(workbench_compose["services"].values()))
    assert workbench["environment"]["CASEBIBLE_R2_CONFIG_PATH"] == "/run/secrets/casebible-r2.json"
    assert "/data/agno/secrets/casebible-r2.json:/run/secrets/casebible-r2.json:ro" in workbench["volumes"]
    forbidden = {
        "OBJECT_STORE_ACCESS_KEY_ID",
        "OBJECT_STORE_SECRET_ACCESS_KEY",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
    }
    assert forbidden.isdisjoint(workbench["environment"])

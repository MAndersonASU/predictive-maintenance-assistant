# Reproducible Container Execution

## Scope

This deployment path packages the existing integrated application for a bounded local demonstration. It does not refit the machine-learning model, rebuild the governed knowledge corpus or retrieval index, retune retrieval or grounding, rerun held-out evaluation, or claim public production deployment.

The container image contains only committed runtime source code, committed configuration, and the governed fully pinned container runtime dependency closure. Governed generated artifacts remain outside Git and outside the image. They are mounted read-only at runtime. Local SQLite application state is stored in a dedicated writable Docker volume.

## Runtime boundary

The application process listens on `0.0.0.0:8000` only inside the isolated container network namespace so Docker can forward traffic to it. Docker Compose publishes that container port only on host loopback as `127.0.0.1:8000:8000`. The deployment remains a local demonstration and must not be changed to an all-interface host publish without a separately governed security and authentication design.

The service also uses a read-only root filesystem, drops Linux capabilities, enables `no-new-privileges`, runs as an unprivileged UID/GID, and supplies a writable `/tmp` tmpfs plus a dedicated application-state volume.

## Required governed runtime artifacts

These files must already exist locally before startup. Compose uses long-form bind mounts with `create_host_path: false` so a missing file causes startup to fail instead of silently creating a directory.

- `outputs/metropt3_selected_isolation_forest.joblib`
- `outputs/metropt3_robust_distance_parameters.json`
- `outputs/metropt3_isolation_forest_validation_report.json`
- `data/interim/knowledge/chunks.jsonl`
- `data/interim/knowledge/retrieval/hybrid_index.joblib`

The application continues to validate the frozen model, chunk-corpus, and retrieval-index identities through its existing configuration and readiness path.

## Build contract

The Dockerfile uses the Docker Official Image `python:3.14.6-slim-bookworm` pinned to the multi-platform image digest recorded at implementation time. Top-level runtime dependencies remain governed by `requirements.txt`. The image build installs them as the build-time root user, then the final runtime process drops to UID/GID `10001:10001`; pip's root-user warning is explicitly acknowledged with `--root-user-action=ignore` for this controlled image-build step. `requirements-container.txt` adds exact pins for the transitive runtime dependency closure used by the container, aligned to the already-governed CPython 3.14 verification environment. The `.dockerignore` file starts from a deny-all rule and admits only `Dockerfile`, `.dockerignore`, `requirements.txt`, `requirements-container.txt`, `src/**`, and `config/**` to the build context. Raw data, generated data, model artifacts, retrieval artifacts, local databases, environment files, credentials, repository history, tests, and documentation are therefore excluded from the image build context.

Validate the Compose model before building:

```powershell
docker compose config --quiet
```

Build a fresh image from the pinned base and fully pinned runtime dependency contract:

```powershell
docker compose build --no-cache
```

Start the bounded local service:

```powershell
docker compose up -d
```

Inspect container state and health:

```powershell
docker compose ps
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/live"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready"
```

The readiness endpoint must report `ready` before prediction, retrieval, or grounded-answer requests are treated as available.

Stop the container without deleting the application-state volume:

```powershell
docker compose down
```

Use `docker compose down -v` only when intentionally deleting bounded local demonstration history. That command destroys the named persistence volume and is not part of normal shutdown.

## Clean-environment verification

A clean-environment verification should demonstrate all of the following:

1. Docker Compose configuration validates successfully.
2. All required governed host artifacts exist before startup.
3. The image builds without copying ignored generated artifacts or secrets into the build context.
4. The container starts from the pinned base image and pinned runtime dependency file.
5. The service is reachable only through `127.0.0.1:8000` on the host.
6. `/health/live` succeeds and `/health/ready` reports ready with the governed dependencies available.
7. Prediction, retrieval, and citation-grounded-answer smoke requests use the same frozen application contracts.
8. Local SQLite state persists in the Docker-managed `application_state` volume while generated ML/RAG artifacts remain read-only bind mounts.
9. Container shutdown and recreation do not require model refitting, retrieval-index rebuilding, or held-out reevaluation.
10. A clean build installs the exact container runtime versions declared by `requirements-container.txt`, including NumPy 2.4.6 and Starlette 1.3.1, rather than resolving newer compatible transitive releases.

## Deployment plan and limitations

This repository demonstrates reproducible local container execution, not a public service. Authentication remains disabled within the bounded local scope, public network exposure remains prohibited by the application contract, and the Compose port mapping is loopback-only. A future public deployment would require a separately governed design for authentication, TLS termination, secret management, persistent service storage, network policy, vulnerability management, image publication/signing, backup/recovery, monitoring/alerting, scaling, and operational ownership.

The local image is reproducible with respect to the pinned Dockerfile frontend digest, pinned base-image digest, exact runtime dependency versions, committed source/configuration, and externally governed artifact identities. Package-file hashes are not separately locked, so this is dependency-version reproducibility rather than a claim of byte-for-byte supply-chain reproduction. Rebuilding on another machine still depends on the selected container platform and the continued availability of the referenced base-image manifest and Python package artifacts.

## Primary Docker references

- Docker build context and `.dockerignore`: https://docs.docker.com/build/concepts/context/
- Docker build best practices and digest pinning: https://docs.docker.com/build/building/best-practices/
- Docker Compose service ports and bind mounts: https://docs.docker.com/reference/compose-file/services/
- Docker Official Python image: https://hub.docker.com/_/python

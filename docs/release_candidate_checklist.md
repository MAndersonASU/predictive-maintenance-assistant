# Release-Candidate Checklist

This checklist is completed against the exact proposed release commit. A checked item requires inspectable evidence; it is not a statement that every future clone already contains ignored governed artifacts.

## Source and Git state

- [ ] `main` tracks `origin/main`, local and remote commit identities match, and the working tree is clean before application.
- [ ] Only the intended release-audit source, tests, and professional documentation changed.
- [ ] `git diff --check` and `git diff --cached --check` pass.
- [ ] Generated data, model artifacts, retrieval artifacts, databases, secrets, logs, and local reports remain ignored.
- [ ] The repository-local Git identity uses the authorized GitHub noreply email.

## Frozen evidence boundaries

- [ ] Candidate `iforest_ne200_ms4096_mf1p0`, threshold `0.601902290159477`, and 48-feature schema are unchanged.
- [ ] Model SHA-256 remains `fa23b81d214161488abf601a8b9852f2467347e53d02fca3653a13cdaaaeec1a`.
- [ ] The corpus remains 354 chunks with SHA-256 `4912c36622d38d44100c3965f457cb45e7de44358d9626c9558ca25b24be722d`.
- [ ] Retrieval-index SHA-256 remains `2700dac28adfc9a80a9bd28c3af177237d45e845ef94c37cd4e68b421d4442b7`.
- [ ] Neither held-out evaluator was rerun.
- [ ] No model, threshold, feature, corpus, index, retrieval, reranking, or grounding parameter was retuned from held-out evidence.

## Clean-state verification

- [ ] A fresh checkout installs the pinned development dependencies successfully.
- [ ] Python source and tests compile successfully.
- [ ] The complete repository suite passes.
- [ ] `python -m pip check` reports no broken requirements.
- [ ] `python -m predictive_maintenance.release_audit --repository-root .` passes with the governed artifacts restored.
- [ ] `docker compose config --quiet` passes.
- [ ] A clean no-cache container build uses the pinned base and dependency closure.

## Integrated behavior

- [ ] Documented native startup is warning-free.
- [ ] Liveness and readiness pass.
- [ ] Prediction schema reports exactly 48 frozen features.
- [ ] Prediction, retrieval, grounded answer, citations, exact-equipment refusal, metrics, and bounded persistence pass controlled smoke checks.
- [ ] The interface passes visual review and uses no remote dependency or browser persistence.
- [ ] Host publication remains limited to `127.0.0.1:8000`.
- [ ] Temporary servers and containers are stopped after verification; port 8000 is released.

## Professional release documentation

- [ ] README describes only implemented and verified capabilities.
- [ ] Data card, model card, evaluation summary, architecture, deployment guide, professional demonstration guide, and release checklist agree.
- [ ] Résumé, LinkedIn, and interview language uses verified facts and names limitations.
- [ ] No accuracy, false-positive-rate, failure-probability, public-production, equipment-specific, safety, reliability, or business-impact claim is unsupported.

## Commit, CI, and release decision

- [ ] Intended files only are staged and reviewed.
- [ ] The implementation commit is pushed and the exact-SHA required Python verification check succeeds.
- [ ] The engineering log records exact package, test, commit, and CI evidence.
- [ ] Any final documentation commit receives its own exact-SHA CI pass.
- [ ] `HEAD` and `origin/main` match and the final working tree is clean.
- [ ] Remaining limitations and future extensions remain visible.

# E2E Test Run Postmortem

## Document Purpose

This document records the issues discovered during the first full end-to-end
test run of Project Automatron, how they were fixed, what still remains open,
and what must change so the next run is truly autonomous rather than assisted.

The scope covers:

- intake -> plan -> approve -> scaffold -> build -> preview -> approve ->
  repo/workflows/secrets -> deploy to VPS
- orchestrator runtime
- builder/reviewer/prompt quality
- generated code quality
- GitHub Actions CI/CD
- compatibility issues on Windows + Docker + Ubuntu targets
- validation, observability, and operator UX

Date of test campaign: 2026-03-11 to 2026-03-12

## Executive Summary

The test run ultimately succeeded, but not as a pure autonomous run.

The system reached a working outcome:

- local preview came up
- GitHub repository was created
- CI workflow ran successfully
- production deploy to the test VPS succeeded
- the deployed invoice dashboard responded with HTTP 200

However, this required substantial manual intervention in two areas:

- fixing the Automatron platform itself so the pipeline could progress
- manually correcting generated project artifacts that the builder should have
  produced or stabilized on its own

Main conclusion:

- Automatron already has a strong architectural direction and a workable
  backbone
- but the first green run was still "assisted autonomy", not production-grade
  autonomous delivery

## Tested Scenario

Test scenario used for the run:

- a small invoice dashboard MVP
- SQLite
- Next.js web app
- single user, no auth
- customers, invoices, payments, dashboard cards
- containerized deploy path

Observed successful outcome:

- generated GitHub repo was created
- preview environment was brought up
- GitHub Actions CI and deploy workflows executed
- application deployed to the test VPS

## What Is Manual by Design vs What Was a Defect

### Manual by design

These operator actions are expected and are not defects:

- creating the project
- starting the build
- approving the technical plan
- approving the preview
- configuring the deploy target
- triggering deployment
- manually syncing CI/CD status if desired

### Manual because the system failed

These were not expected operator steps. They were compensating actions:

- fixing orchestrator runtime/state bugs
- fixing scaffold/bootstrap behavior
- rebuilding the golden image manually
- correcting generated deploy artifacts manually
- correcting generated metadata and health endpoint manually
- restarting stale runtime processes for validation

## High-Level Findings

1. The biggest failures were not in one place. They were distributed across
   environment bootstrapping, graph state management, builder/reviewer
   progression, and deploy artifact quality.
2. The prompts were directionally useful, but not strict enough to guarantee
   deployable output.
3. The reviewer was initially too permissive. It classified success mostly by
   absence of obvious error strings, not by actual artifact validation.
4. Windows development support was not operationally reliable without fixes.
5. The generated application became functional before it became deployable.
   That distinction matters.

## Detailed Findings by Area

## 1. Environment and Bootstrap Issues

### 1.1 Golden image was not reliably available

Problem:

- the orchestrator expected `automatron/golden:latest` to exist
- when it did not exist, scaffold/build could not start

Impact:

- the run could not reach the builder phase

Root cause:

- golden image build was an external prerequisite but not enforced or
  auto-healed by the platform

Fix applied:

- the image was built manually
- related build path issues were fixed in the platform

Needed permanent fix:

- Automatron should verify image availability before starting a project
- if absent, it should either:
  - build it automatically
  - or fail early with a precise actionable error

### 1.2 Golden image build context was wrong

Problem:

- Docker build originally used a context that did not include
  `orchestrator/scripts/`
- the build failed on `COPY orchestrator/scripts/`

Impact:

- golden image could not be built

Root cause:

- Docker build command and image builder logic assumed the wrong context

Fix applied:

- build command and image build path logic were corrected

Needed permanent fix:

- keep build context definition in one place
- add a smoke test that runs the exact golden image build command in CI

### 1.3 Ubuntu 24.04 image user creation failed

Problem:

- `useradd -u 1000 developer` failed because UID 1000 was already occupied

Impact:

- golden image build failed on some base image states

Root cause:

- image assumed UID 1000 would always be free

Fix applied:

- Dockerfile user creation logic was corrected

Needed permanent fix:

- do not hardcode a globally assumed UID
- use idempotent user/group creation logic

### 1.4 Windows workspace path was incompatible with Docker host mounts

Problem:

- `WORKSPACE_BASE_PATH=/var/automatron/workspaces` was invalid on Windows host
- Docker returned "not a valid Windows path"

Impact:

- project container creation failed after plan approval

Root cause:

- Linux-default path configuration was used in a Windows run

Fix applied:

- workspace path was switched to a Windows-valid host path

Needed permanent fix:

- provide OS-aware defaults in configuration
- validate path format at startup
- refuse startup with an invalid host volume path

## 2. Orchestrator Runtime and State Management

### 2.1 Backend startup and socket/runtime problems

Problem:

- backend startup was unstable due to runtime wiring issues
- startup behavior depended on stale processes and reload state

Impact:

- requests could fail or serve stale logic after code fixes

Root cause:

- process lifecycle and reload behavior were not robust enough during active
  development

Fix applied:

- runtime wiring was corrected
- backend was restarted multiple times during debugging

Needed permanent fix:

- one canonical startup path
- health/readiness probes for backend itself
- no silent mismatch between code on disk and long-running process state

### 2.2 SQLite initialization was not reliable

Problem:

- project creation initially failed because the database was not always
  initialized before the first write

Impact:

- `POST /api/projects` could fail on a clean start

Root cause:

- DB initialization relied too much on startup order

Fix applied:

- lazy DB initialization was added to model access paths

Needed permanent fix:

- keep lazy-init, but also add explicit app startup DB readiness check
- expose DB readiness in backend health

### 2.3 LangGraph checkpoint compilation was broken

Problem:

- graph compilation failed because the SQLite checkpointer was used
  incorrectly

Impact:

- project state could remain stuck in `planning` with no architect or builder
  progress

Root cause:

- wrong checkpointer lifecycle/integration with the installed LangGraph
  version

Fix applied:

- graph compilation/checkpoint handling was corrected

Needed permanent fix:

- pin LangGraph/checkpointer compatibility
- add a startup self-test that compiles the graph and executes a minimal
  checkpoint round-trip

### 2.4 Resume logic re-ran planning instead of resuming

Problem:

- after an error or pause, `start` could trigger a new planning phase and
  regenerate the plan instead of resuming from checkpoint/state

Impact:

- approved plans were effectively destabilized
- project progress looked nondeterministic

Root cause:

- resume logic did not consistently normalize state from existing checkpoints

Fix applied:

- `start` / `resume` behavior was corrected so existing plan and build state
  are restored

Needed permanent fix:

- explicit lifecycle tests:
  - pending -> planning
  - planning -> approval
  - approval -> scaffold
  - error -> resume
  - paused -> resume

### 2.5 `deployed` final stage existed but needed real validation

Problem:

- final `deployed` stage support was partially present, but it had to be
  validated against real workflow sync

Impact:

- UI and state could drift from actual deploy status

Fix applied:

- real workflow sync was exercised and `project_stage=deployed` was confirmed
- UI polish for live/deployed state was added

Needed permanent fix:

- add integration tests for:
  - deploy queued
  - deploy running
  - deploy deployed
  - deploy failed

## 3. Prompt and Planning Quality Issues

### 3.1 Architect could ask for clarifications instead of producing a plan

Problem:

- for raw intake text, the architect sometimes responded with questions and
  "proceed with defaults" language instead of a valid technical `PLAN.md`

Impact:

- flow paused in an awkward state
- operator had to compensate with feedback

Root cause:

- architect prompt allowed ambiguity handling without guaranteeing a concrete
  technical plan under uncertainty

Fix applied:

- prompts and behavior were steered toward default-driven continuation

Needed permanent fix:

- architect should always choose one of two explicit outcomes:
  - generate a technical plan with defaults
  - emit a separate `awaiting_clarification` stage

### 3.2 Architect prompt carried stale framework assumptions

Problem:

- planning logic contained stale assumptions such as legacy Tailwind/Next
  expectations

Impact:

- builder was pushed toward obsolete project structures

Root cause:

- prompt drift from current framework ecosystem

Fix applied:

- architect prompt was updated

Needed permanent fix:

- version-aware prompt maintenance
- prompt regression tests against current framework scaffolds

### 3.3 Builder prompt did not enforce deploy-grade output strongly enough

Problem:

- builder could produce something that worked locally but still missed
  important deployment, metadata, or health requirements

Impact:

- generated repo was not consistently production-ready

Fix applied:

- builder contract was strengthened to require:
  - deploy artifacts
  - project-specific metadata
  - a `/api/health` endpoint for Next.js apps

Needed permanent fix:

- keep builder output contract short, explicit, and machine-checkable
- do not rely on prose alone for critical delivery requirements

## 4. Builder and Reviewer Loop Weaknesses

### 4.1 Reviewer initially used weak success heuristics

Problem:

- reviewer mainly inferred success from lack of obvious error strings

Impact:

- low-quality or incomplete output could still pass

Root cause:

- reviewer validated logs more than workspace state

Fix applied:

- reviewer was extended to validate concrete workspace conditions for Next.js:
  - health route exists
  - default metadata is gone

Needed permanent fix:

- reviewer should validate artifacts, not only terminal output
- add stack-specific validators:
  - Next.js validator
  - Vite validator
  - Python app validator

### 4.2 Completed tasks were not consistently marked in `PLAN.md`

Problem:

- even after success, the same task could be revisited because completion was
  not reliably written back

Impact:

- task loop could stall or repeat

Root cause:

- plan progression and completion marking were not synchronized robustly

Fix applied:

- parser/reviewer flow was updated to mark successful tasks completed

Needed permanent fix:

- dedicated test for repeated-task prevention

### 4.3 Builder reached functional app state before deployable state

Problem:

- domain features could appear before deploy artifacts were truly stable

Impact:

- pipeline looked successful too early

Root cause:

- success criteria did not separate:
  - "feature works"
  - from "repo is deployable and releasable"

Fix applied:

- deploy artifact checks were added before preview-ready status

Needed permanent fix:

- build lifecycle should have explicit sub-stages:
  - feature complete
  - validation complete
  - preview ready
  - release ready

## 5. Generated Code Quality Gaps

This is the most important section from the autonomy perspective.

### 5.1 Deploy artifacts needed manual correction

Problem:

- the generated repo required manual correction to become reliably deployable

Artifacts manually corrected in the generated project:

- `Dockerfile`
- root `docker-compose.yml`
- `deploy/docker-compose.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`

Impact:

- first green end-to-end deploy was assisted, not autonomous

Root cause:

- builder produced a working app, but not a consistently production-grade repo

Fix applied:

- those generated artifacts were corrected manually

Needed permanent fix:

- builder prompt must require these artifacts explicitly
- reviewer must validate them
- CI must fail if any required deploy artifact is missing or invalid

### 5.2 Generated app kept default `Create Next App` metadata

Problem:

- generated app still used scaffold defaults:
  - `Create Next App`
  - `Generated by create next app`

Impact:

- poor project polish
- obvious sign of unfinished generation

Fix applied:

- metadata was replaced manually in the generated app
- builder/reviewer contracts were updated to catch this in future runs

Needed permanent fix:

- metadata should be set as part of the normal build plan
- reviewer should fail the run if scaffold defaults remain

### 5.3 Generated app lacked a proper health endpoint

Problem:

- generated app did not originally expose a meaningful health endpoint

Impact:

- weak deploy validation
- no standard readiness/health target for CI/CD or operators

Fix applied:

- a proper `/api/health` route was added to the generated app
- scaffold and builder/reviewer logic were updated to expect this

Needed permanent fix:

- every generated web app should expose a standard health contract
- health should optionally verify a critical dependency such as DB availability

## 6. LLM Provider and Model Selection Issues

### 6.1 Model/provider selection was initially too static

Problem:

- provider/model choice originally relied too much on env-only configuration

Impact:

- poor operator control
- weak observability over actual model usage

Fix applied:

- per-project LLM role configuration was added
- UI support for architect/builder/reviewer selection was added

Needed permanent fix:

- keep model choice project-scoped
- persist it in project state

### 6.2 Model catalogs were not fully compatible with live provider APIs

Problem:

- Google model catalog parsing used the wrong field name

Impact:

- dynamic provider catalog returned incomplete/broken results

Fix applied:

- provider catalog implementation was corrected

Needed permanent fix:

- keep provider adapters isolated
- add contract tests per provider

### 6.3 Runtime env reload behavior was misleading

Problem:

- after `.env` updates, long-running backend processes could continue using old
  settings

Impact:

- operator saw inconsistent provider availability

Fix applied:

- backend restarts were used during testing

Needed permanent fix:

- document restart requirement for config changes
- optionally add explicit config reload endpoint only for development

## 7. UI, API, and Observability Gaps

### 7.1 UI/API contract drift existed earlier in the run

Problem:

- REST and websocket contracts were not fully aligned

Impact:

- missing or confusing runtime information in the UI

Fix applied:

- contracts were normalized during the campaign

Needed permanent fix:

- add frontend-backend contract tests for:
  - project DTO
  - websocket status updates
  - chat history
  - deploy status

### 7.2 Logs were not sufficient by default

Problem:

- it was too easy to lose track of where a run actually stopped:
  - planning
  - checkpoint compile
  - scaffold
  - builder
  - preview
  - deploy

Impact:

- debugging was slower than necessary

Fix applied:

- logs, sessions, and task inspection were used directly through API and DB

Needed permanent fix:

- one run timeline in UI with:
  - current stage
  - current task
  - last error
  - checkpoint/resume marker
  - last CI run
  - last deploy run

### 7.3 Stale dev processes complicated validation

Problem:

- long-running preview/backend processes could keep serving stale state after
  code changes

Impact:

- validation could appear inconsistent

Fix applied:

- processes were restarted manually
- production-like one-off validation was used to verify real output

Needed permanent fix:

- explicit preview restart control
- stronger distinction between:
  - dev preview
  - production-like validation

## 8. GitHub Actions and Deploy Issues

### 8.1 Password-based deploy was not initially first-class

Problem:

- deploy path needed password-based SSH support for the test VPS

Impact:

- GitHub Actions deploy could not rely only on existing key-based flow

Fix applied:

- password auth support was added to deploy target model and workflows

Needed permanent fix:

- keep both auth modes supported:
  - SSH key
  - password
- but prefer key-based deploy for long-term production use

### 8.2 Environment secrets and workflow readiness needed live validation

Problem:

- token scope and environment/secrets readiness had to be proven in a real repo

Impact:

- theoretical correctness was not enough

Fix applied:

- GitHub API, repo creation, environment creation, secret upsert, workflow
  execution, and VPS deploy were validated in real runs

Needed permanent fix:

- add preflight GitHub validation:
  - repo write
  - Actions write
  - environment secret write

### 8.3 Deploy health verification was too dependent on operator input

Problem:

- `app_url` / `health_path` were not always set

Impact:

- deploy could succeed without a useful post-deploy health assertion

Fix applied:

- default `/api/health` behavior was introduced

Needed permanent fix:

- deploy target wizard should strongly encourage or require health URL setup

## 9. Manual Interventions Performed During the Test Run

These are the actions that replaced work the platform or generated pipeline
should ideally have handled on its own.

### 9.1 Platform-side manual interventions

- built the golden image manually
- restarted backend multiple times
- fixed graph/checkpoint integration
- fixed resume behavior
- fixed Next.js scaffold behavior
- fixed builder/reviewer progression logic
- fixed model catalog compatibility
- fixed password deploy support

### 9.2 Generated-project manual interventions

- corrected generated deploy artifacts
- corrected generated metadata
- added generated health endpoint
- manually validated generated project with lint/build/start/curl

### 9.3 Verification-side manual interventions

- direct DB inspection
- direct API calls
- direct container shell commands
- direct inspection of GitHub Actions runs
- direct validation against the VPS

## 10. What Was Fixed During the Campaign

Fixed during the campaign:

- startup/runtime blockers
- DB initialization issues
- graph checkpoint issues
- resume logic
- golden image build issues
- Windows host path issues
- Google model catalog compatibility
- LLM role selection support
- dynamic model catalog support
- GitHub Actions password deploy support
- deploy stage/state sync validation
- stricter builder/reviewer quality contract for:
  - health endpoint
  - metadata

## 11. What Is Still Not Fully Solved

Open or partially solved:

- first green run still required manual generated-code corrections
- preview dev process can become stale
- backend process reload behavior can remain stale during active debugging
- builder still cannot be trusted yet to always emit deploy-grade artifacts
- reviewer validation is better, but still not broad enough
- prompt quality is improved, but still not formally regression-tested
- cross-platform support, especially Windows host development, is still fragile

## 12. Recommended Remediation Plan

## Immediate

- add regression tests for:
  - graph compile
  - resume after error
  - deploy stage sync
  - required deploy artifacts
  - Next.js metadata and health route validation
- keep the reviewer artifact validation
- require `/api/health` by default for generated web apps

## Short-Term

- introduce explicit `awaiting_clarification` stage
- strengthen architect prompt to default forward under ambiguity
- add preflight checks before starting a run:
  - golden image exists
  - Docker reachable
  - workspace path valid
  - GitHub token valid
- add run timeline UI

## Medium-Term

- split lifecycle into:
  - build success
  - validation success
  - preview ready
  - release ready
  - deployed
- create stack-specific validators
- move from "best effort" review to formal acceptance gates

## 13. Definition of Success for the Next Test Run

The next run should be considered truly successful only if all of the following
are true without manual code edits inside the generated repo:

- plan is generated without ambiguous manual steering
- scaffold works on the target developer OS
- builder completes tasks without repeating/stalling
- reviewer validates real artifacts
- generated repo contains deploy-ready Docker and workflow files
- preview comes up without manual restart tricks
- CI passes
- deploy to VPS succeeds
- health endpoint returns success
- no human edits are needed inside the generated application code

## Final Conclusion

Automatron has crossed the line from concept to real working system, but not
yet to trustworthy autonomous software factory.

The first complete test run proved that:

- the architecture is viable
- the orchestrated flow can reach a real deployed product

It also proved that:

- current autonomy is still brittle
- builder output quality is not yet self-validating enough
- deployability is still the weakest part of the system

The correct interpretation of this campaign is not "Automatron is finished".
The correct interpretation is:

- the backbone works
- the integration path works
- the remaining work is to eliminate the need for manual rescue


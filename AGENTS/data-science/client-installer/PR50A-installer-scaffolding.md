# PR50A — 8-BALL Client Installer Audit, Architecture & Recovery

**Contract document.** This file records the authoritative PR50A scope and the
client-installer development sequence. Subsequent PR50B–PR50F work must align
with this contract unless explicitly superseded by a later approved revision.

---

## Purpose

PR 50 begins a new phase of 8-BALL development: integrating the existing
data-science/profile work into the customer-facing installer and preparing it for
real-machine validation.

This work is downstream from C10/C10.1, but it is **not** another C10 stage.

**Working directory:**

```text
AGENTS/data-science/client-installer/
```

The existing C-series data-science work remains authoritative and must not be
moved, renamed, duplicated, or replaced merely to simplify the installer.

PR50A is an **audit and architecture** stage. Do not attempt to complete
PR50B–PR50F during a PR50A run.

---

## 1. Development Boundary

```text
AGENTS/data-science/profile-mapping/
        |
        | answers:
        | "What should this hardware/model combination support?"
        v
AGENTS/data-science/client-installer/
        |
        | answers:
        | "Can a customer machine actually install,
        |  run, recover and report it correctly?"
        v
trial-install.sh -> 8.1.sh -> 8.2.sh -> 8.3.sh
```

The client installer should **consume** the data-science work. It should not
recreate that work as giant Bash decision trees.

---

## 2. PR50A–PR50F Sequence

```text
PR50A   Audit, architecture and recovery
          ↓
PR50B   8.1 foundation / Ollama safety
          ↓
PR50C   8.2 profile + model integration
          ↓
PR50D   8.3 customer status / MOTD
          ↓
PR50E   trial-install release integrity
          ↓
PR50F   validation + real VM-test readiness
```

**Expected documentation area:**

```text
AGENTS/data-science/client-installer/
  PR50A-audit.md
  PR50B-foundation.md
  PR50C-profile-integration.md
  PR50D-client-status.md
  PR50E-release-integrity.md
  PR50F-validation.md
```

PR50A creates its own audit document. Do not create speculative completed B–F
documents during PR50A.

---

## 3. X/Y Model Architecture

For architecture and documentation:

| Symbol | Meaning |
| --- | --- |
| **Y** | Current reference/validation model path |
| **X** | Arbitrary approved catalog-selected model path |

These are **documentation symbols**. Do not unnecessarily rename production Bash
variables to `X` or `Y`. Production variables should remain descriptive.

### Y — Current Validation Path

Qwen currently serves as the primary **Y** reference family.

Y proves the installer vertically across client machines:

```text
CLIENT ENVIRONMENT / HARDWARE
              |
              v
       hardware detection
              |
              v
       profile resolution
              |
              v
       candidate selection
              |
              v
          Qwen Y
              |
              v
         ollama pull
              |
              v
      real inference test
              |
       +------+------+
       |             |
      PASS          FAIL
       |             |
       v             v
     result       fallback
```

Successful Y testing proves installer pipeline behavior. It does **not** prove
the complete model catalog works.

### X — Future Catalog Path

X represents an arbitrary model approved by the broader 8-BALL profile/catalog
system. The catalog may ultimately contain hundreds of models.

```text
X = <approved model-id supplied by profile/catalog data>
```

Target architecture:

```text
C-SERIES / DATA SCIENCE
          |
          | profile + approved candidates
          v
     MODEL X DATA
          |
          v
    generic 8.2 engine
          |
          +--> resource gates
          +--> ollama pull X
          +--> inference test X
          +--> PASS / approved fallback
```

Avoid model-family-specific `if/elif` ladders in 8.2. Model knowledge belongs
primarily in **data**. Execution knowledge belongs primarily in the **installer**.

---

## 4. PR50 Development Goal

**PROVE Y while PRESERVING X.**

A major long-term success criterion:

> Adding a newly approved Ollama model should require a profile/catalog data
> update rather than an edit to `8.2.sh`.

---

## 5. Generic Model Plumbing (audit targets)

Inspect existing generic concepts:

- `REQUESTED_MODEL`
- `SELECTED_MODEL` (MOTD / result file)
- candidate lists / chains
- `MODEL_SLUG` / `--model-slug`

Prefer descriptive future concepts only when needed:

- `MODEL_ID`, `MODEL_CANDIDATE`, `MODEL_PROFILE`, `MODEL_SOURCE`,
  `MODEL_CONSTRAINTS`, `MODEL_FALLBACK`

---

## 6. Real-World Proof Invariant

Profile data **predicts**. The machine **proves**.

```text
profile predicts X fits → resource gates → pull → real inference → PASS | fallback
```

Fallback may remove only models downloaded during the current failing attempt.
Do not remove pre-existing customer models.

Manual `--model` must be deterministic: no silent substitution.

---

## 7. X/Y Validation Reporting (future)

**Y — Installer validation** (environments): Ubuntu CPU 4/8/16/24+ GB, CUDA,
Lightsail, DigitalOcean, etc.

**X — Catalog coverage** (models): Qwen reference, Gemma, Llama, Mistral, etc.

Successful Y tests do not prove every X works. Individual X failures do not
automatically imply installer architecture failure.

---

## 8. PR50A Definition of Done

PR50A is complete when we understand:

- what PR 50 actually did
- what should be kept / repaired / reverted
- whether Y is ready for validation
- whether X has a clean future interface
- what PR50B should do next

Success is measured by accuracy of the map, not volume of code changed.

---

## 9. Scope Guard (PR50A)

PR50A must **not**:

- redesign 8-BALL or replace C7/C8/C9/C10/C10.1
- rebuild the Ollama catalog or validate 200+ models
- hard-code hundreds of models into Bash
- install OpenWebUI; add Passport/licensing
- expose Ollama publicly or open firewall ports
- claim VM validation that did not occur
- automatically implement PR50B–PR50F
- merge PR 50

---

## 10. Four Architectural Test Questions

PR50A must answer:

1. Can we prove Y across target environments without redesigning the installer?
2. If C-series supplies model X tomorrow, can 8.2 consume it without
   model-family-specific code?
3. What exact remaining code assumes Y/Qwen where it should consume X/data?
4. Can model #201 be added through data without changing `8.2.sh`?

If Question 4 is currently **no**, PR50A must explain what PR50C must change.

---

## Revision history

| Date | Document | Notes |
| --- | --- | --- |
| 2026-08-13 | `PR50A-installer-scaffolding.md` | Initial contract from PR50A assignment |
| 2026-08-13 | `PR50A-1-audit.md` | First-pass audit (superseded by `PR50A-audit.md`) |
| 2026-08-13 | `PR50A-audit.md` | Architecture-aware audit with X/Y boundary |

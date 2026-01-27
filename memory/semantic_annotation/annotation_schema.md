# Semantic Annotation Schema — v0

Status: DRAFT  
Phase: 8A (Offline Semantic → Episodic Annotation)  
Authority: NONE  
Depends On:
- semantic_annotation_policy.md
- episodic episode_structure
- semantic_schema.md

---

## Purpose

This schema defines the **structure of an annotation** applied to an episode
during offline replay.

Annotations are descriptive metadata.
They do not alter episode structure, semantics, or behavior.

---

## Core Principle

Annotations describe **what an episode resembles**,  
not **what the system should do**.

They are commentary, not instruction.

---

## Annotation Identity

Each annotation MUST have:

- `annotation_id`  
  - Globally unique identifier
  - Stable across replays

- `episode_id`  
  - Identifier of the annotated episode
  - An annotation always belongs to exactly one episode

---

## Annotation Type

Each annotation MUST declare:

- `annotation_type`  
  A short string describing the nature of the annotation.

Examples:
- `"semantic_pattern_match"`
- `"frequency_label"`
- `"structural_similarity"`
- `"temporal_pattern"`

Annotation types are descriptive categories only.
They carry no priority or authority.

---

## Source Provenance

Annotations MUST record their origin:

- `source_semantic_ids`  
  - List of semantic record identifiers used
  - Empty list permitted (for rule-based annotations)

- `source_policy_version`  
  - Version of the annotation policy

This ensures full auditability.

---

## Temporal Scope

Annotations MUST specify:

- `applied_during_replay`  
  - Boolean (always `true` for Phase 8A)

- `episode_closed`  
  - Boolean confirming episode was closed at annotation time

Annotations MUST NOT be applied to active episodes.

---

## Annotation Payload

The annotation payload:

- `descriptor` (required)
  - Structured, human-readable description
  - Examples:
    - `"resembles frequent single-decision episodes"`
    - `"matches high-latency decision pattern"`

- `metrics` (optional)
  - Descriptive statistics only
  - Examples:
    - counts
    - distances
    - frequencies
  - MUST NOT include:
    - scores
    - utilities
    - priorities
    - thresholds

- `confidence` (optional)
  - Descriptive confidence in `[0.0, 1.0]`
  - MUST NOT be interpreted as belief strength
  - MUST NOT be used to gate behavior

---

## Mutability Rules

Annotations MUST be:

- Immutable once created
- Additive (never overwrite or delete others)
- Removable without consequence

Deleting all annotations MUST leave the system unchanged.

---

## Explicit Prohibitions

Annotations MUST NEVER:

- Modify episodes
- Modify semantic records
- Influence consolidation
- Influence decision logic
- Persist executive state
- Encode preferences or rankings
- Act as triggers or conditions

Annotations are inert metadata.

---

## Storage Semantics

Annotations MAY be stored:

- Adjacent to episodes
- In a separate annotation store
- In inspection-only tooling

Annotations MUST NOT be:

- Read by runtime decision code
- Loaded into working memory
- Cached across runs

---

## Versioning

Each annotation record MUST declare:

- `schema_version`
- `policy_version`

Breaking changes require:
- New schema version
- New tests
- Explicit offline migration

---

## Phase Boundary

This schema authorizes:

- Annotation record definitions
- Offline annotation engines
- Annotation tests

It does NOT authorize:

- Learning
- Runtime feedback
- Policy updates
- Semantic influence on action

---

End of schema.

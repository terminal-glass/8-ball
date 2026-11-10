<!-- Generated from config/osamp-alignment.yaml by eight_ball.osamp.alignment. Do not edit by hand. -->

# OSAMP alignment

OSAMP: Open Source Agent Mail Protocol, AfricaTogether Project by NoCloudGPT

White paper: `OSAMP_Technical_Whitepaper_v0.8.md` (2026-11-07).
Technical architecture proposal, not a deployed federation and not a ratified standard. The paper is not vendored in this repository. Wire formats are unresolved, and this matrix does not invent or rename them.

Status values are implemented, planned, or unresolved.
Implemented means a local check or document in this repository.
It does not mean a deployed federation.

| Item | Status | Evidence |
| --- | --- | --- |
| Use the name OSAMP. Do not create or rename a protocol. | implemented | The name is recorded here and in src/eight_ball/osamp. No alternate protocol name is introduced. |
| Readiness claims stay short of a deployed federation. | implemented | This matrix and the component inventory label federation and wire formats unresolved. |
| Standing agreements are Peer, Tribe, Clan, Table, and Work. | implemented | The local gate accepts only those names. It does not define their wire messages. |
| Work is Project or Corridor. | implemented | A Work request without Project or Corridor is refused locally. |
| Bridge Acceptance is a scoped human receipt, not a sixth standing contract. | implemented | The local gate refuses Bridge Acceptance as a standing contract. |
| Self-Governance Covenant is built-in policy, not an extra negotiated contract. | implemented | PLAY, PAUSE, STOP, REWIND, REVIEW, FAST-FORWARD, and TIMEOUT run in the local covenant controller. |
| Trust is not transitive. | implemented | A request that carries trust_transitive or trusted_via is refused. |
| Invitation or delivery is not acceptance. | implemented | A delivered and unaccepted request is held and does not invoke a model. |
| A Table contains participants who explicitly accept bounded roles. | implemented | A Table request without accepted_roles is refused. Federation membership storage is not claimed. |
| 8-BALL hardware fit stays separate from a measured 9-Ball profile. | implemented | Suitability does not authorize the gate. A fitting machine with no contract is refused. |
| Capacity does not grant authority. | implemented | The gate never reads RAM, VRAM, or download size as permission. |
| Optional adapter boundary for agent runtimes. | implemented | The boundary exists and refuses calls. It is tested as a refusal. |
| OpenClaw adapter. | planned | Not implemented and not tested. The boundary reports status planned. |
| Hermes adapter. | planned | Not implemented and not tested. The boundary reports status planned. |
| Deterministic local gate for identity, contract, scope, revocation, replay, expiry, and budget. | implemented | Unit tests refuse unauthorized, replayed, and expired work before the invoke callback. |
| No contract means no relay. | implemented | A missing contract is refused and the invoke callback is not called. |
| Small local workers accepting bounded contributions. | planned | The gate can refuse out-of-scope work. A worker runtime is not shipped. |
| Explicit refusal, hold, and human review. | implemented | The gate returns refuse, hold, and human_review without calling a model. |
| Bounded escalation to another clan or operator. | unresolved | Human review stops locally. No escalation transport is defined. |
| No unrestricted broadcast or automatic cross-clan disclosure. | implemented | broadcast and cross_clan_disclosure actions are refused. |
| Do not invoke a model for duplicates, irrelevant messages, expired offers, or already-known data. | implemented | Replay, expiry, no_action, irrelevant, and already_known refuse before invoke. |
| Retain accepted commitments and expire unaccepted noise. | implemented | The hold store keeps commitments across reload and drops expired unaccepted items. |
| Durable bounded store-and-forward and reconnect catch-up. | planned | The hold file survives a process restart. Network catch-up is not implemented. |
| OSAMP is transport-independent. Email is only one possible transport. | unresolved | No mail transport is implemented. None was invented here. |
| Do not route Nextcloud or git replication through agent mail. | implemented | nextcloud_sync and git_replication actions are refused. |
| Rewind is reviewed restoration, not a promise that every external effect can be undone. | implemented | REWIND sets review_required and leaves undo_promised false. |
| Unreachable peers remain stop-pending until acknowledged. | implemented | STOP for an unreachable peer stays stop_pending until acknowledge_stop. |
| Preserve %% working, !! held, !* timeout, and ~ ~ external shared service markers. | implemented | The local covenant controller sets those markers. GridStack title rendering is separate. |
| GridStack status belongs in titles and application-box contents stay intact. | unresolved | This repository has no GridStack UI. |
| Modest hardware can contribute without a cloud purchase. | implemented | The free model path has no license check and no required cloud purchase. Geographic coverage is not claimed. |
| Connectivity loss does not create false completion. | implemented | Catalog refresh failure keeps the last-known-good snapshot and reports failure. It does not install a model. |
| Inference stays inside an agreed budget. | implemented | budget_remaining at or below zero is refused before invoke. |
| White-paper message encodings and federation state. | unresolved | The white paper is not in this repository. No message schema was written from memory. |
| Measured 9-Ball capability and resource profile. | unresolved | 8-BALL suitability remains an estimate. It is not a 9-Ball profile. |

## Pilot acceptance

| Check | Coverage |
| --- | --- |
| Unauthorized work is refused before inference. | tested |
| Replayed work is refused before inference. | tested |
| Expired work is refused before inference. | tested |
| Delivery is distinguished from acceptance. | tested |
| Held work is still present after restart. | tested |
| Cloud-only catalog entries are not local downloads. | tested |
| A failed catalog refresh preserves the last-known-good catalog. | tested |
| OpenClaw and Hermes adapters are tested end to end. | planned |
| A multi-node OSAMP federation exchanges white-paper messages. | unresolved |
| Live installs on macOS, Windows, Lightsail, and DigitalOcean. | untested |

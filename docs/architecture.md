# Architecture

## Principles

1. **Local data owns curation.** Upstream playlists provide channel candidates. Favorite groups,
   ordering, aliases, and health history belong to IPTV Manager.
2. **Refresh is non-destructive.** A channel absent from a later source snapshot becomes inactive;
   it is not deleted. This keeps favorite references and history intact.
3. **Health is evidence, not truth.** Every probe is timestamped. One failure never removes a
   channel, and geographic restriction is used only for explicit evidence such as HTTP 451.
4. **Be polite to providers.** Concurrency, timeouts, retry count, and schedules are bounded and
   configurable. Favorites should receive scheduling priority without creating duplicate probes.
5. **Hot Player integration is URL-based.** Generated M3U endpoints are the supported contract.
   Portal automation and internal Hot Player favorite synchronization remain out of scope until
   behavior is observed and documented.

## Runtime view

```text
Remote/local M3U ──> importer ──> SQLite
                         │          ├── channels + source snapshots
                         │          ├── independent favorite groups
                         │          └── append-only health evidence
                         │
Browser ──> FastAPI ─────┼──> dashboard / JSON API
Hot Player ──────────────┴──> /playlists/{group}.m3u

Scheduler/worker (next milestone) ──> bounded HTTP checks ──> optional ffprobe
```

The MVP is a single process and SQLite database, suitable for personal self-hosting. Expensive
scheduled probes will move to a separate worker while retaining SQLite's single-writer constraint:
workers produce results and one persistence path writes them in short transactions.

## Stable identity

Identity is scoped to a playlist source:

- Prefer normalized `tvg-id` when present.
- Otherwise hash normalized name/country/language/group metadata.
- If metadata is insufficient, fall back to a normalized stream URL.

This lets URLs rotate without losing a well-identified channel. A separate URL fingerprint strips
common volatile token parameters and supports duplicate detection across sources. The two concepts
must remain separate: “same editorial channel” and “same stream endpoint” are different questions.

## Health status model

- `unknown`: never checked.
- `working`: the current probe saw usable response bytes or media streams.
- `failed`: concrete transport, HTTP, or decode failure after configured retries.
- `uncertain`: inconclusive response, missing probe capability, or timeout semantics that should
  not be treated as a durable failure.
- `geographically_restricted`: explicit restriction evidence. HTTP 403 alone is not sufficient.

The current status is denormalized on the channel for fast filtering; complete evidence remains in
`health_checks`. Every check also stores a runner name so local and Codespaces observations remain
distinguishable when a database is transferred between environments.

## Runtime data portability

Local and Codespaces installations each use a single-writer SQLite database. The database is never
committed to Git. SQLite's online backup API produces consistent downloadable snapshots, and
restore validates integrity and preserves the replaced database as a timestamped safety copy.
This explicit transfer model avoids corruption and merge conflicts from synchronizing a live
SQLite file.

## Security and operations

The current API assumes a trusted private network. Before exposing it publicly, add authentication,
CSRF protection for browser mutations, rate limits, HTTPS at the reverse proxy, and an unguessable
or authenticated playlist-token mechanism. Never expose upstream credentials or signed URLs in
logs. Back up the SQLite file using SQLite's backup API or a filesystem snapshot after checkpointing.

# Delivery roadmap

## Milestone 0 — foundation (current)

- Package, container, schema, parser, incremental import, favorite export
- Single-channel and bounded bulk health probing with append-only history
- Persistent scan progress, cancellation, checkpoint resumption, and favorite-first ordering
- Codespaces runtime, scan provenance, and validated SQLite backup/restore
- Working dashboard workflow, JSON API, tests, CI

## Milestone 1 — usable local manager

- Full channel table with server pagination, filters, bulk selection, and duplicate views
- Favorite group UI with drag/drop ordering and aliases
- Local file upload with size limits and import preview
- Per-host rate limits and durable per-channel scan snapshots
- Database migrations with Alembic; automated backup retention

## Milestone 2 — automation

- Scheduler and dedicated health worker
- Fair per-host concurrency/rate limits and exponential backoff
- Failure streaks, availability windows, and health retention policy
- Conditional remote refreshes, source snapshot audit, and import error reports
- Authenticated public playlist URLs and reverse-proxy deployment guide

## Milestone 3 — playback and integration hardening

- VLC protocol links with explicit opt-in
- Browser playback for compatible HLS streams
- Hot Player compatibility test matrix using generated endpoints
- Only after manual verification: document whether portal changes preserve existing playlists and
  Hot Player favorites. Portal automation remains a separate opt-in decision.

## Definition of done for the first release

- A 13,000-channel source imports and refreshes without losing favorite associations.
- Bulk health checks respect global and per-host limits and can resume after restart.
- Generated playlists pass syntax tests and are fetched successfully by Hot Player 2.2.3.
- Public deployment has authentication, HTTPS, backup/restore, observability, and documented
  recovery steps.

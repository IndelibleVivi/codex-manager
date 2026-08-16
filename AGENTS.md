# Codex Manager Agent Instructions

This repository contains a Windows-first local manager that reads and mutates a
user's real `~/.codex` tree. Treat file editing, deletion, batch cleanup, Skill
creation, translation, and local HTTP access as security- and data-loss-sensitive
surfaces.

Read `README.md`, the user tutorial, and the actual Python/PowerShell source
before changing behavior. Global Faye/Cove collaboration style lives outside
this repository.

## Current Source Map

- `README.md`: product entrypoint, present behavior, limitations, and safety.
- `Codex管理器-使用教学.md`: beginner-facing installation and usage guide.
- `Codex管理器/① 双击我安装.bat`: Windows installation entrypoint.
- `Codex管理器/install-shortcuts.ps1`: shortcut installation.
- `Codex管理器/manager.bat`: manager launcher.
- `Codex管理器/dashboard.bat`: inventory launcher.
- `Codex管理器/零件箱/Codex配置管理器.py`: local Web UI, classification,
  file mutation, quarantine, translation, duplicate scan, and Skill creation.
- `Codex管理器/零件箱/Scan-CodexInventory.ps1`: inventory report.

The repository currently has no automated test suite and no `LICENSE`. Do not
claim either until it exists and has been verified.

## User-Data Boundary

The default target is the current user's expanded `~/.codex`. It may contain
configuration, instructions, rules, Skills, Memory, sessions, generated media,
attachments, OAuth state, secrets, and plugin-managed data.

- Never run mutation tests against Faye's or any developer's real `~/.codex`.
- Current source resolves the root at import/startup. Before adding automated
  mutation tests, make the root explicitly injectable for test mode while
  preserving the default production behavior.
- Tests must create a complete temporary fixture root and temporary quarantine.
- Never copy real secrets, sessions, Memory bodies, attachments, or plugin state
  into fixtures or committed snapshots.
- Do not add telemetry, inventory upload, crash upload, analytics, or hidden
  outbound requests.

## Path Containment

- Every file operation must remain contained under the configured Codex root,
  except the explicitly configured local quarantine path.
- Resolve paths before use and reject traversal, absolute-path escape, symlink
  escape, malformed quarantine names, and unsafe restore destinations.
- Preserve `.git` read-only behavior. Do not expose editing or deletion of Git
  internals through a new endpoint.
- Do not follow a symlink outside the root merely because its lexical path begins
  inside the root.
- A restore must never overwrite an existing target silently.
- Directory and file mutation must report partial failures accurately; do not
  return a blanket success when items were skipped or failed.

## Editing Contract

- Saving edits is an immediate overwrite and currently has no automatic backup.
  Do not describe it as recoverable through the deletion quarantine.
- Preserve the view/edit size caps unless a tested product change explicitly
  revises them.
- The editor is a UTF-8 text surface. Do not silently load undecodable bytes with
  replacement characters and then allow them to be saved as if lossless.
  Prefer failing closed or marking the file non-editable when decoding is not
  exact.
- Preserve newline/content intentionally. A formatting or encoding rewrite is a
  user-data mutation, not a harmless display change.
- Do not add broad binary, database, cookie, keychain, SQLite, or credential-file
  editing.

## Classification Is Advisory

The `classify()` result is a navigation and warning heuristic. It is not an
authority that proves deletion is safe.

- Never turn `junk`, `history`, `managed`, or `other` into an automatic deletion
  policy without explicit user review.
- Unknown paths stay unknown/other. Do not optimistically label a newly observed
  Codex directory as junk.
- A plugin- or version-specific path needs evidence before entering a category.
- UI wording must not promise “safe to delete” solely because a rule matched.
- Batch cleanup must show the exact top-level targets and consequences before
  mutation if its interaction contract is expanded.
- Keep config/rules/Skills/Memory separate from transient and historical data.

## Deletion, Quarantine, And Cleanup

- Ordinary deletion and allowed batch cleanup move items to the local quarantine
  before any permanent deletion.
- Quarantine location and retention semantics are user-visible contracts.
- Current retention cleanup occurs when quarantine items are scanned/opened; do
  not describe it as a background scheduler.
- Permanent item purge and “empty quarantine” are irreversible. They require a
  clear explicit confirmation and must never be triggered on page load.
- Deleting the application directory also deletes the quarantine. Keep this
  limitation documented.
- Batch cleanup remains bounded to the explicitly supported categories and
  current root-level selection contract. Do not recurse into arbitrary matches
  or clean nested user workspaces without a separately designed preview/apply
  flow.
- History cleanup can break old sessions, attachments, images, visualizations,
  or dictation history. Preserve this warning.
- Never delete or rewrite user data as part of installation, startup, upgrade,
  inventory scan, duplicate scan, or translation.

## Duplicate Scan

- Current duplicate detection identifies byte-identical Markdown files. It does
  not identify semantic duplicates or choose a canonical copy.
- Do not add automatic duplicate deletion.
- Keep scan limits and skipped-file behavior visible when they affect
  completeness.
- Hashing is a local comparison mechanism; do not upload hashes or paths.

## Skill Creation

- Create Skills only under the configured Codex root's `skills/<name>/SKILL.md`.
- Preserve strict path/name validation and refuse existing destinations.
- Do not overwrite an existing Skill or system-managed Skill.
- Validate the generated frontmatter and required structure before reporting
  success.
- Skill creation is a real configuration change. It must remain an explicit user
  action, not a side effect of browsing or inventory.

## Local HTTP Boundary

- Bind only to literal loopback (`127.0.0.1`) unless a future authenticated
  remote product is separately designed and reviewed.
- Do not add `0.0.0.0`, LAN discovery, Tunnel, reverse proxy, permissive CORS, or
  public hosting instructions.
- Loopback is not authentication. Any local process or browser context that can
  reach the port may attempt the API. Keep mutation endpoints narrow and use
  explicit origin/session/CSRF controls if the UI architecture evolves beyond
  the current same-origin launcher.
- Do not accept arbitrary filesystem roots, URLs, shell commands, Python code,
  or executable paths from the browser API.
- Preserve bounded request bodies and exact JSON validation when adding or
  modifying endpoints.

## Translation Boundary

- Translation sends selected content to a localhost OpenAI-compatible proxy.
  The proxy may forward content to a cloud provider.
- Keep translation optional and isolated; proxy failure must not break local
  file management.
- Never translate a file automatically, in the background, or as part of a scan.
- Do not send paths, unrelated files, secrets, credentials, private account data,
  or complete `~/.codex` inventories to the model.
- Keep length limits and timeouts explicit.
- If proxy URL/model become configurable, store configuration locally without
  embedding secrets in tracked source or query strings.
- README and UI must explain that “localhost proxy” does not guarantee the text
  stays on the device.

## Testing Requirements

Before shipping code changes to any mutating or network boundary, add or extend
isolated automated tests. At minimum cover the changed applicable cases:

- root containment and traversal rejection;
- symlink escape;
- exact edit success and decoding failure without corruption;
- delete-to-quarantine and restore;
- restore collision;
- seven-day retention boundary;
- permanent purge confirmation/endpoint behavior;
- batch cleanup preview/target selection and partial failure;
- classification of known, unknown, plugin, history, and temp paths;
- Skill name/path validation and no-overwrite;
- loopback bind and rejected unsupported methods/paths;
- translation disabled/failure/size behavior without local mutation.

Use temporary roots only. A test must fail before it can point at the real
`~/.codex` or the repository's own quarantine.

For docs-only work, verify links, commands, and source claims directly. Do not
claim functional tests that are not present or were not run.

## Documentation Closure

- Update `README.md` when supported platform, installation, user-visible
  behavior, limits, recovery, privacy, network flow, or known data-loss risk
  changes.
- Update the beginner tutorial in the same change when its instructions or
  promises change.
- Update this file when source ownership, mutation boundaries, testing,
  classification, or network authority changes.
- Keep exact implementation details factual. Do not call a heuristic category a
  safety guarantee or call quarantine equivalent to edit versioning.
- Use repo-relative links and public-safe examples.
- Keep private Faye/Cove continuity in the external private-continuity root
  governed by the user-level working contract.

## Git And Release

- Inspect `git status --short`, stage explicit files, review the staged diff, and
  run `git diff --cached --check`.
- Keep documentation hardening separate from unrelated feature work.
- Do not commit real `~/.codex` contents, quarantine items, inventory reports,
  screenshots containing private paths/data, credentials, or generated user
  artifacts.
- Adding a license, publishing a release/archive, changing repository metadata,
  or claiming platform support is a separate explicit decision.
- A source commit is not evidence that Windows installation, shortcuts, manager,
  inventory, mutation, or translation were all tested. Report the exact evidence
  reached.

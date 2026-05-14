# Proposed CLAUDE.md Updates — Control Panel

> **These diffs must be applied through the `claude-maintenance` approval flow per `.claude/rules/maintenance.md` — do not edit directly.**

Three files get small, additive edits. Each diff shows the exact old block and the exact new block.

---

## 1. `C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\CLAUDE.md`

Add a short "Control Panel" block under the existing "Standing Rules" section.

**OLD:**
```
## Standing Rules

Rules in `.claude/rules/` apply across this workspace. Key rule: reminders, notifications, approval pings, and scheduled alerts to Ricky go via Slack, never Telegram. See `.claude/rules/reminders-channel.md`.
```

**NEW:**
```
## Standing Rules

Rules in `.claude/rules/` apply across this workspace. Key rule: reminders, notifications, approval pings, and scheduled alerts to Ricky go via Slack, never Telegram. See `.claude/rules/reminders-channel.md`.

### Control Panel

Local ops dashboard for every Turnkey automation — spend, jobs, skills, `.env` audit, one-click Start/Stop/Trigger. Loopback only.

- URL: `http://127.0.0.1:7823`
- Docs: `control-panel/README.md`
- Rules: `.claude/rules/control-panel.md`, `.claude/rules/llm-telemetry.md`
```

---

## 2. `C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\.claude\CLAUDE.md`

Add one bullet under "What Lives Here".

**OLD:**
```
## What Lives Here

- `.claude/rules/` for workspace-wide operating rules
- `.claude/Skills/` for workspace and Turnkey-specific skills
- `.claude/Turnkey Branding and Logos/` for brand source assets
- `.claude/settings.json` for workspace-local Claude overrides
```

**NEW:**
```
## What Lives Here

- `.claude/rules/` for workspace-wide operating rules
- `.claude/Skills/` for workspace and Turnkey-specific skills
- `.claude/Turnkey Branding and Logos/` for brand source assets
- `.claude/settings.json` for workspace-local Claude overrides
- Control panel lives outside this layer at `../control-panel/` (dashboard at `http://127.0.0.1:7823`)
```

---

## 3. `C:\Users\ricky_j3cdbqw\.claude\CLAUDE.md`

Add one bullet under "Core File Locations".

**OLD:**
```
## Core File Locations

- Active workspace root: `C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS`
- Shared credentials: `C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\.env`
- Workspace router: `C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\CLAUDE.md`
- Decision log: `C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\decisions\log.md`
```

**NEW:**
```
## Core File Locations

- Active workspace root: `C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS`
- Shared credentials: `C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\.env`
- Workspace router: `C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\CLAUDE.md`
- Decision log: `C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\decisions\log.md`
- Control panel dashboard: `http://127.0.0.1:7823` (docs: `CLAUDE CODE PROJECTS\control-panel\README.md`)
```

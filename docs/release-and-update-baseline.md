# Auditor Support Tool
## Release and Update Baseline

### Document status

| Item | Detail |
|---|---|
| Application | Auditor Support Tool |
| Stable baseline version | 0.1.1 |
| Installer type | Per-user Windows installer |
| Installer technology | Inno Setup |
| Application packaging | PyInstaller one-folder build |
| Updater packaging | PyInstaller one-file executable |
| Supported update channels | Stable and Testing |
| Baseline status | Successfully tested |
| Baseline date | 1 August 2026 |

---

## 1. Purpose

This document records the validated installation, release and in-application update baseline for the Auditor Support Tool.

It provides the minimum reference point for future releases and changes to the installer, update service, release scripts and GitHub release process.

---

## 2. Distribution files

Each production release creates the following files:

| File | Purpose |
|---|---|
| `Auditor-Support-Tool-Setup.exe` | Normal Windows installer for first-time users |
| `Auditor-Support-Tool-Windows-x64.zip` | Application package used by the in-application updater |
| `Auditor-Support-Tool-Windows-x64.zip.sha256` | SHA-256 checksum used to verify the update package |

First-time users should normally receive only:

```text
Auditor-Support-Tool-Setup.exe
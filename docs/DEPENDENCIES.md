# Dependency versions and how they were verified

The development sandbox could reach Maven Central (via Google's mirror), the Gradle Plugin
Portal and PyPI, but **not** Google's Maven repository (`dl.google.com`). Versions were chosen
as follows; every Android dependency was then proven to resolve and compile by the GitHub
Actions build.

| Component | Version | Verification |
|---|---|---|
| Gradle | 8.14.3 | Wrapper used by a previously green build in this repository |
| Android Gradle Plugin | 8.13.0 | KSP 2.3.x requires ≥ 8.12 (CI error message); resolves and builds in CI |
| Kotlin | 2.3.21 | Latest 2.3 patch on the Gradle Plugin Portal (2026-10-09); supports AGP ≤ 8.13 |
| KSP | 2.3.12 | Latest on the Gradle Plugin Portal |
| compileSdk / targetSdk / minSdk | 36 / 36 / 29 | SDK 36 installed in CI; 37 would require AGP 9 |
| Compose BOM | 2026.06.01 (Compose 1.11.4, Material3 1.4.0) | Official BOM mapping page; 2026.09.00 (Compose 1.12) rejected by AAR metadata check (needs compileSdk 37, AGP 9.1) |
| Media3 | 1.11.1 | Official release notes: latest stable, 2026-09-10 |
| Room | 2.8.5 | Official release notes: latest stable, 2026-09-09 |
| WorkManager | 2.10.1 | Known stable; resolves in CI (newer may exist) |
| core-ktx / activity-compose / lifecycle | 1.16.0 / 1.10.1 / 2.9.1 | Known stable; resolve in CI (newer may exist) |
| ONNX Runtime Android | 1.31.0 | Latest on Maven Central (2026-10-09); same version used for host validation |
| OkHttp | 4.12.0 | Maven Central |
| kotlinx-coroutines | 1.10.2 | Maven Central |
| Python backend | see `backend/requirements.txt` | Exact versions installed and tested (pip resolver, 2026-10-09) |
| LiteRT | not used | Not resolvable from the sandbox; see MODELS.md |

Upgrading: bump versions, push, and let CI verify. When moving to AGP 9.x, remove the
`org.jetbrains.kotlin.android` plugin (AGP 9 has built-in Kotlin) and raise compileSdk to 37 to
unlock Compose 1.12+.

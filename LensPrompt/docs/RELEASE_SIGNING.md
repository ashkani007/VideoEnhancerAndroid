# Release signing (Google Play App Signing)

LensPrompt is set up for **Play App Signing**:

- **Google** keeps the app signing key.
- **You** keep an **upload key**, used only to sign the bundles you upload.

The repository contains **no key material**. `.gitignore` blocks `*.jks`, `*.keystore`, `*.p12`, `*.pem`, `keystore.properties` and `signing.properties`.

## How the build reads the key

`app/build.gradle.kts` reads only these environment variables:

| Variable | Meaning |
|---|---|
| `LENSPROMPT_UPLOAD_KEYSTORE` | path to the upload keystore file (`.jks`) |
| `LENSPROMPT_UPLOAD_STORE_PASSWORD` | keystore password |
| `LENSPROMPT_UPLOAD_KEY_ALIAS` | key alias |
| `LENSPROMPT_UPLOAD_KEY_PASSWORD` | key password |
| `LENSPROMPT_VERSION_CODE` | versionCode (CI sets the run number) |

- **All four signing variables set:** `bundleRelease` / `assembleRelease` are signed with the upload key.
- **Any missing:** the release is built **unsigned** and CI still passes. This is the current state.

## Creating the upload key (once, by the owner, on a trusted machine)

```bash
keytool -genkeypair -v -keystore lensprompt-upload.jks -alias lensprompt-upload \
  -keyalg RSA -keysize 4096 -validity 10000
```

Back up the `.jks` file and its passwords in a password manager. **Never commit them.**

## Adding it to GitHub Actions

Repository → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `LENSPROMPT_UPLOAD_KEYSTORE_BASE64` | output of `base64 -w0 lensprompt-upload.jks` |
| `LENSPROMPT_UPLOAD_STORE_PASSWORD` | keystore password |
| `LENSPROMPT_UPLOAD_KEY_ALIAS` | `lensprompt-upload` |
| `LENSPROMPT_UPLOAD_KEY_PASSWORD` | key password |

The workflow decodes the keystore into the runner's temp directory, signs the AAB and APK, and deletes the file at the end of the job.

## First upload to Play Console

1. Create the app with package **`com.lensprompt.app`** (permanent).
2. Choose "Let Google manage and protect your app signing key" (Play App Signing).
3. Upload the signed `app-release.aab` (CI artifact `LensPrompt-release-aab`) to an **internal testing** track.
4. Play registers your upload key from that first upload.

## Signing locally

```bash
export LENSPROMPT_UPLOAD_KEYSTORE=/secure/path/lensprompt-upload.jks
export LENSPROMPT_UPLOAD_STORE_PASSWORD=…  LENSPROMPT_UPLOAD_KEY_ALIAS=lensprompt-upload  LENSPROMPT_UPLOAD_KEY_PASSWORD=…
export LENSPROMPT_VERSION_CODE=<higher than the last upload>
./gradlew bundleRelease
```

## R8 mapping file

Release builds are minified. Upload `app/build/outputs/mapping/release/mapping.txt` with each bundle. Play does this automatically for AABs that include it, so crash reports stay readable.

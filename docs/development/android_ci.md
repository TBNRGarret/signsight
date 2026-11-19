# Android CI dependency recovery

The 18 November 2026 build failed before application compilation: Flutter's included Gradle build could not resolve Kotlin dependencies because the Gradle Plugin Portal redirected requests to Maven Central, which returned HTTP 429. Re-running that job produced the same failure.

The Android job now:

- Caches Gradle dependencies and wrapper distributions using the existing pinned `actions/setup-java` action. Its key includes Android configuration, the Flutter dependency lockfile and the CI repository policy.
- Installs the checked-in `.github/gradle/central-mirror.init.gradle` into the disposable runner's Gradle init directory. It places the Google-hosted Maven Central mirror before plugin resolution and redirects explicit Maven Central repositories in settings, project and buildscript scopes. This also covers Flutter's included build. Google Maven and the Plugin Portal remain available for their own artifacts. Local SDK files and developer Gradle settings are unchanged.
- Builds the same x64 debug APK. `scripts/ci_android_build.py` streams the build log and retries at most twice, after 30 and 90 seconds, only for explicit repository HTTP 429/502/503/504 responses. Compile failures and other errors return immediately. Exhausted retries fail the job. A missing APK fails artifact upload.

Sources: [Google-hosted Central mirror](https://maven-central.storage.googleapis.com/index.html), [Gradle init scripts](https://docs.gradle.org/current/userguide/init_scripts.html), [setup-java dependency caching](https://github.com/actions/setup-java#caching). The mirror is Google-hosted, but its landing page does not promise an officially supported product. It can also have outages or lag; the job must remain red if required artifacts cannot be resolved.

## Verification

```powershell
python -m pytest tests/test_ci_android_build.py -q
```

The retry tests exercise recovery, bounded failure, compile-error rejection, unrelated/unauthorized HTTP errors and real subprocess output/status propagation. An additional offline fixture runs a real Gradle distribution with both a main build and an included build using `FAIL_ON_PROJECT_REPOS`:

```powershell
$env:SIGNSIGHT_TEST_GRADLE_BIN = 'ABSOLUTE_GRADLE_BIN'
python -m pytest tests/test_ci_gradle_repositories.py -q
```

Use a compatible JDK. That fixture creates temporary build/cache directories and resolves no remote dependencies. A passing fixture checks policy application; acceptance of the Android app still requires the remote APK build, and physical-device acceptance remains separate. The CI artifact is an emulator x64 debug APK, not a signed ARM release for users.

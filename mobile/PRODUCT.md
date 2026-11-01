# SignSight User App

<!-- impeccable:product-schema 1 -->

## Platform

android

## Shared Product Context

Read `../PRODUCT.md` for the shared users, purpose, workflows, constraints, terminology, evidence, and product principles. That file is the authority for shared product facts. The user app and web management have equal priority; this file only scopes the mobile platform.

## Operating Context

- The user app is Flutter/Dart and currently uses Material 3. Android native is the implemented and emulator-verified native target; physical-device acceptance remains pending.
- The same app has a web preview, which is a browser surface rather than evidence of native behavior. Apply web guidance when targeting that preview specifically.
- An iOS project and permission declarations exist, but its build and device acceptance remain unverified. The current implementation does not establish an OS-adaptive visual system. Future iOS work must load iOS guidance and preserve the operating system's interaction and accessibility guarantees.
- Preserve the three user destinations: **Bản đồ**, **Đóng góp**, and **Của tôi**. Staff use web management.

## Evidence on Hand

- `../docs/flutter_user_app.md`: app behavior, device integration, build/run steps, and recovery limits.
- `../docs/core_completion.md`: current native verification evidence and remaining acceptance work.

# Sign marker images

Web and Flutter share the approved visual catalogue: 35 CAR35 images and historical STOP, plus a neutral unknown symbol. Markers retain the original sign colours in either theme; a separate yellow `!` indicates a record needing confirmation. The marker target is 48 logical pixels.

Select a marker to load the first reviewed photo returned by the existing authenticated sign-detail API. The web popup keeps its action visible while long content scrolls. Flutter shows the photo in the selected-sign panel. Records without evidence explain that no reviewed photo is available; failed loads expose retry. Closing, changing selection or changing account discards the previous photo. Dataset examples are not shipped as evidence.

`frontend/shared/signs/catalog.json` records explicit aliases, original source revisions, checksums, authors and licences. CAR35 `DS.SS.*` identifiers are experimental catalogue identifiers, not replacements for legal QCVN codes. Ambiguous historical `R.301e` and `W.245a` records require an exact recognized name; otherwise the neutral symbol is used. No database migration is performed.

Original SVGs live under `frontend/shared/signs/`. Generate the JS registry and proportional, transparent 192-pixel Flutter PNGs with:

```powershell
$env:PLAYWRIGHT_CHANNEL = 'chrome'
node scripts/build_sign_assets.cjs
```

The generator uses local assets only. Keep both asset directories' `LICENSE.md` and catalogue metadata. Never add dataset crops, uploaded photos, credentials or model weights to these directories.

After updating, reload the web page with Ctrl+F5. Restart/rebuild Flutter to include the new bundled assets; hot reload alone may retain the previous asset bundle.

## Verification

Viewport refreshes retain unchanged marker handles, including their selected photo popup. A changed/absent record or account change removes the old marker and disposes its photo. This prevents the popup's own automatic pan from immediately closing the selected evidence through a map refresh.

Unit tests cover explicit aliases, fallback, source checksums, PNG proportions, authenticated evidence requests, retry and stale-result cleanup. Playwright uses a disposable database, local map fixture and synthetic photo, including desktop/phone layout and direct account switching when the new map request fails. Browser phone emulation does not establish Safari or native-device acceptance.

Native map appearance, selection and style-reload restoration still need a device check. The attempted Android emulator check could not proceed because ADB reported the emulator as unauthorized; Flutter unit/widget tests and static analysis cover the code-level checks.

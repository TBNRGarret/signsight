# SignSight Streets

Day and night vector styles derived from OpenFreeMap Liberty, downloaded from
https://tiles.openfreemap.org/styles/liberty on 2026-10-31.
The exact upstream JSON SHA-256 is recorded in each style's metadata.

Changes: warm road hierarchy, blue water, green parks, flat low-contrast buildings,
local/Vietnamese names before Latin fallback, regular label typography, fewer
transit labels at street overview zoom, and a separately composed night palette.

Tiles, fonts and sprites remain on OpenFreeMap. No API key is required. This is
presentation configuration, not an offline map or a redistribution of OSM data.
Visible source/style attribution is retained. See LICENSE.txt for the upstream
OSM Liberty / OSM Bright code and design licenses.

To regenerate from a reviewed upstream JSON:

```powershell
python scripts/build_mobile_basemap.py path/to/liberty.json
```

Review changes before replacing the generated assets; do not update the remote
style automatically at app startup. Deterministic tests use explicit fixture
styles. `integration_test/map_visual_test.dart` separately checks real-provider
rendering with in-memory synthetic account/sign data and no personal runtime.

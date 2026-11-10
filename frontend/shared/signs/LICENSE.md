# Sign artwork provenance

The 36 SVG road sign images were selected from Wikimedia Commons and approved
for the SignSight UI on 2026-11-09. SVG bytes are unmodified. `catalog.json`
records the original source page, author/credit metadata, licence link, revision
timestamp and SHA-256 for every image. Consult the linked file description for
the complete licence statement, including any additional licensing options.

The roundabout graphic by มองโกเลีย๔๔ is licensed under CC BY-SA 4.0:
https://commons.wikimedia.org/wiki/File:Vietnam_road_sign_R303.svg
https://creativecommons.org/licenses/by-sa/4.0/
Other graphics list Vietnamese government/public-domain artwork and their
individual credit/licence metadata in the catalogue. No dataset photographs are
included in this asset set.

Flutter PNGs are transparent 192 x 192 rasterizations generated from these SVGs
by `node scripts/build_sign_assets.cjs`; only the rendering/format is changed.
The neutral question-mark fallback is original SignSight interface geometry,
not a road sign. Application code licensing does not replace artwork licences.

These images communicate a recorded sign's appearance. They do not certify
catalogue codes, road applicability or legal accuracy. Legacy ambiguous codes
retain an explicit guarded visual mapping and do not trigger a database rewrite.

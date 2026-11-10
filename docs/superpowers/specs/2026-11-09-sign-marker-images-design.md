# Reviewed sign images on the map

The user approved the entire image board on 2026-11-09: 35 CAR35 classes and
historical STOP, with an icon on each map marker and the reviewed contribution
photo shown when selecting a sign. Preserve the existing web and Android design,
MapLibre/OpenFreeMap, account boundaries and staff approval lifecycle.

## Approaches and decision

Photo thumbnails directly on the map obscure sign meaning at small sizes and
increase per-marker network traffic. The user explicitly selected clear sign
icons on the map, with real reviewed evidence in details. Use the exact approved
SVG originals on web and generated PNGs from those originals in Flutter, with a
shared, explicit visual catalogue. Preserve sign colours in both themes.

## Behaviour

- Cover all CAR35 dataset aliases and the historical catalogue. Unknown or
  ambiguous codes use a neutral unknown icon rather than a guessed road sign.
- Keep a 48 logical pixel marker target and a separate revalidation badge;
  selected/focused markers remain recognizable without recolouring the sign.
- Load at most the first reviewed evidence photo on selection through the
  authenticated API. Keep text when there is no photo, a request fails, or an
  image fails to decode. Provide retry. Do not fetch photos for every marker.
- Cancel/ignore stale photo responses after selection, account or map changes;
  release browser object URLs when the popup closes.
- Use the existing sign-detail/evidence endpoints; no database migration or
  change in evidence visibility is needed. Never ship dataset example crops.
- Retain the original catalogue codes. R.301e is a left-turn sign in the source
  artwork: only the known legacy right-labelled record may use the approved
  keep-right visual (R302a); otherwise show unknown. Historical W.245a names
  conflating slow-down and generic danger also use unknown pending data review.

## Assets and provenance

Bundle the 36 approved originals, source links, credit/licence metadata and
checksums. A local generator verifies originals and derives Flutter PNGs; it
does not download assets at app startup or change their geometry. UI lookup uses
explicit class aliases, not arbitrary filename or class-ID guessing.

## Verification

TDD covers lookup and legacy ambiguity, marker structure/layer ordering,
authenticated evidence retrieval, empty/error/retry and stale account/selection.
Browser checks use disposable API data and synthetic image evidence. Flutter
widget checks isolate the map platform; native visual verification uses an
Android emulator when available and does not establish real-device acceptance.

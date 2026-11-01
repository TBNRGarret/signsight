---
name: SignSight Android
description: Quiet wayfinding for discovering reviewed signs and contributing evidence.
colors:
  light-primary: "#245c48"
  light-on-primary: "#ffffff"
  light-primary-container: "#dceadf"
  light-on-primary-container: "#153d2b"
  light-surface: "#f5f6f1"
  light-surface-container-low: "#eef1e9"
  light-surface-container: "#e9ede4"
  light-surface-container-high: "#e2e8dc"
  light-on-surface: "#25342b"
  light-on-surface-variant: "#536157"
  light-outline-variant: "#d4ddd1"
  dark-primary: "#a5d3b9"
  dark-on-primary: "#083826"
  dark-primary-container: "#244f3d"
  dark-on-primary-container: "#dceadf"
  dark-surface: "#121813"
  dark-surface-container-low: "#1a211b"
  dark-surface-container: "#202820"
  dark-surface-container-high: "#2a322b"
  dark-on-surface: "#e3e9df"
  dark-on-surface-variant: "#bdc9bd"
  dark-outline-variant: "#414d43"
typography:
  headline-small:
    fontFamily: Roboto
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.33
    letterSpacing: "0px"
  title-large:
    fontFamily: Roboto
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.27
    letterSpacing: "0px"
  title-medium:
    fontFamily: Roboto
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.15px"
  body-large:
    fontFamily: Roboto
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0.5px"
  body-medium:
    fontFamily: Roboto
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0.25px"
  body-small:
    fontFamily: Roboto
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "0.4px"
  label-large:
    fontFamily: Roboto
    fontSize: "14px"
    fontWeight: 500
    lineHeight: 1.43
    letterSpacing: "0.1px"
  label-medium:
    fontFamily: Roboto
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.33
    letterSpacing: "0.5px"
rounded:
  field-notice: "12px"
  button-search: "14px"
  panel-photo: "16px"
spacing:
  compact: "8px"
  control-gap: "12px"
  inset: "16px"
  list-inset: "20px"
  section: "24px"
  generous: "28px"
  divider-space: "32px"
components:
  button-primary:
    backgroundColor: "{colors.light-primary}"
    textColor: "{colors.light-on-primary}"
    typography: "{typography.label-large}"
    rounded: "{rounded.button-search}"
    padding: "14px 20px"
    height: "52px"
  button-primary-dark:
    backgroundColor: "{colors.dark-primary}"
    textColor: "{colors.dark-on-primary}"
    typography: "{typography.label-large}"
    rounded: "{rounded.button-search}"
    padding: "14px 20px"
    height: "52px"
  button-outlined:
    textColor: "{colors.light-primary}"
    typography: "{typography.label-large}"
    rounded: "{rounded.button-search}"
    padding: "14px 20px"
    height: "52px"
  button-text:
    textColor: "{colors.light-primary}"
    typography: "{typography.label-large}"
    padding: "12px 16px"
    height: "48px"
  field:
    backgroundColor: "{colors.light-surface-container-low}"
    textColor: "{colors.light-on-surface}"
    rounded: "{rounded.field-notice}"
    padding: "16px"
  navigation:
    backgroundColor: "{colors.light-surface}"
    typography: "{typography.label-medium}"
    height: "80px"
  chip-selected:
    backgroundColor: "{colors.light-primary-container}"
    padding: "8px"
  photo-start-panel:
    backgroundColor: "{colors.light-surface-container-low}"
    rounded: "{rounded.panel-photo}"
    padding: "28px 24px"
  notice:
    backgroundColor: "{colors.light-surface-container-low}"
    textColor: "{colors.light-on-surface-variant}"
    typography: "{typography.body-medium}"
    rounded: "{rounded.field-notice}"
    padding: "16px"
---

# Design System: SignSight Android

## Overview

**Creative North Star: "Quiet wayfinding"**

Botanical garden wayfinding supplies the restraint: forest green, warm near-white ground, pale sage selections and clear routes through information. Native Material 3 controls and Roboto make the Android app familiar. Color identifies actions and state; section spacing gives evidence and instructions room to be read.

The signature is an evidence path from photo to checking to submission for review. Human label and location confirmation, pending work and approved map data remain visibly distinct. This system describes the implemented Android app; it does not establish iOS acceptance or an adaptive iOS design. No new raster assets ship with this direction.

**Key Characteristics:**
- Matte tonal surfaces with restrained forest-green emphasis.
- Native controls, labeled destinations and useful recovery actions.
- Readable task hierarchy and explicit evidence/review states.
- Equal-width evidence steps with centered labels and connecting lines.

Source authority: `lib/app_theme.dart`, `lib/ui_components.dart`, `lib/app.dart` and inherited report/activity surfaces in `lib/feedback.dart`. Product scope is `PRODUCT.md`; selected world and implementation scope are recorded in `.impeccable/surfaces/mobile-lib-app-dart.md`. Frontmatter CSS-compatible lengths represent native logical dp for geometry and unscaled logical font sizes; Flutter applies platform text scaling. Component heights above are minima, not fixed clipping boxes.

## Colors

The green family is quiet and botanical; warm neutral layers carry the information.

### Primary
- **Forest / pale leaf:** `primary` supplies filled actions, active evidence steps, accepted-state cues and selected navigation labels. `onPrimary` supplies their readable foreground.
- **Sage selection:** `primaryContainer` supplies the selected navigation indicator and selected chips; `onPrimaryContainer` supplies the paired container foreground.

### Neutral
- **Warm ground / night garden:** `surface` supplies the scaffold, app bar, navigation and bottom sheets.
- **Low, middle and high tonal layers:** `surfaceContainerLow`, `surfaceContainer` and `surfaceContainerHigh` supply filled fields, quiet panels, notices and inactive progress circles.
- **Forest ink / pale text:** `onSurface` carries main text; `onSurfaceVariant` carries supporting text and neutral pending cues.
- **Quiet boundary:** `outlineVariant` carries outlined controls, dividers and incomplete progress links.

The frontmatter records the explicit light/dark overrides. All remaining Material roles, including `error`, `errorContainer`, `onErrorContainer`, focus and disabled states, come from `ColorScheme.fromSeed` using the light-primary seed and matching brightness. They are not a separately invented palette. Errors use error semantics; rejection also has an icon and status label. Pending uses a schedule icon, neutral text and an explicit label.

**The Semantic Pair Rule.** Select foreground and background from the same brightness scheme; preserve the named Material role rather than reusing a light-mode literal in dark mode.

## Typography

**Display and Body Font:** Android Material Roboto, with platform fallback for unsupported glyphs. No custom font is bundled. The native font is intentional in this world.

**Character:** Familiar, direct and legible. Hierarchy comes from native text roles, weight and space; there is no separate decorative display face or uppercase editorial label system.

### Hierarchy
- **Headline small:** contribution/history task headings; bold override of the Material role.
- **Title large:** app bar, sheet headings and useful empty-state titles; bold override.
- **Title medium:** panel headings, selected sign codes and route summaries; semibold override.
- **Body large:** the contribution introduction and larger supporting content.
- **Body medium:** ordinary instructions and notices, with the app's increased line height.
- **Body small:** supporting confirmation/review explanations and metadata, with the app's increased line height.
- **Label large:** buttons, evidence-step numbers and labels.
- **Label medium:** history status and navigation. Navigation selects primary color and bold weight (700); unselected labels use on-surface-variant and medium weight (500).

Exact baseline role values live in the frontmatter, extracted from the app overrides and the installed Flutter Material 2021 typography defaults. These are role values before platform scaling, not a promise of identical physical pixels on every device.

**The Native Hierarchy Rule.** Reuse the named Material roles and allow text scaling; keep supporting instructions in normal sentence case and let long content wrap or scroll.

## Layout

The shell centers a phone-width app with a maximum width of 600 dp. A compact left-aligned app bar sits above an `IndexedStack`; native bottom navigation remains available across the three destinations. The navigation height is 80 dp. The wider backdrop uses the low surface-container tone rather than stretching phone content indefinitely.

The map fills its body. Search is inset 16 dp horizontally and 12 dp from the top; a scrollable summary is inset 16 dp and sits 28 dp above the bottom. Its maximum height is 40% of the viewport. The GPS action sits above the summary. The summary hides while the keyboard or place results need that space; the map keeps its spatial context.

Contribution uses a vertical list with 24 dp horizontal insets, 12 dp top and 28 dp bottom. History uses headings and actions above horizontally scrolling status filters and a refreshable list. Report pages use a 20 dp inset and inherit the shared theme. Bottom sheets retain native safe-area, keyboard and drag-handle behavior. Repeated rhythm comes from the frontmatter spacing scale; smaller local gaps remain local rather than becoming a new system scale.

**The Reachable Action Rule.** Text and icon buttons have at least 48 dp interaction targets; filled and outlined actions have a 52 dp minimum height. Let height grow for scaling and content. The 36 dp evidence circles are informational markers, not controls.

## Elevation & Depth

Tonal layering creates most separation. The app bar has no scrolled-under elevation; app bar, navigation and bottom sheet surface tints are transparent. Map overlays use native Material elevation to remain legible over map detail: search is level 1, the nearby/selected-sign summary level 2, and the pin-confirmation panel level 4. These are Flutter elevation values, not custom CSS shadows. Native sheet and control states retain their Material behavior. There is no custom decorative motion system; native state feedback and progress indicators carry interaction feedback.

**The Quiet Surface Rule.** Use tonal containers for ordinary grouping and reserve the existing native elevation hierarchy for content floating over the map.

## Shapes

Gently rounded geometry keeps controls familiar: fields and notices share the small radius, buttons and map search share the middle radius, and panels/photo clipping share the large radius recorded above. The pin-confirmation overlay locally uses an 18 dp radius. Evidence markers are circles; the native navigation indicator is a capsule. Chips, text buttons, sheets and selection feedback retain Material defaults where the theme does not override them. Borders are thin role-based boundaries, not a repeated outline around every section.

## Components

### Buttons

Clear native actions. Filled buttons identify the immediate primary task; outlined buttons offer parallel secondary tasks such as choosing from the library. Text buttons carry lighter actions such as retry, discard and sheet dismissal. All use native busy, disabled, pressed and focus behavior. Filled/outlined padding and shape come from the shared theme; icon buttons preserve a 48 dp minimum target and tooltips. In the photo entry state, camera, library and parked-use guidance appear in that order.

### Chips

Quiet native filters. History uses `ChoiceChip` for all, pending, accepted and rejected contributions. Selection uses the primary-container tone and native selected treatment. Filters scroll horizontally rather than compressing labels. Chip padding is 8 dp in each direction with an outline-variant boundary; native chip shape and semantics remain intact.

### Cards / Containers

Matte information panels. The photo-start panel uses a low surface-container background, large rounded corners and generous internal space. Image evidence is contained in a 210 dp-high rounded area with `BoxFit.contain`; model boxes remain evidence overlays. Map summary panels use surface plus native elevation. Empty states combine a library icon, title, explanation and a next-action button; they do not leave a blank list with no way forward.

### Inputs / Fields

Filled and grounded. Shared fields use low surface-container fill, a thin outline-variant boundary, small rounded corners and a 16 dp inset. Native focus/error/disabled states remain responsible for feedback. The map search is a local surface-backed variant without a resting field border and with a primary-colored 2 dp focus boundary. Dropdowns, correction reasons, authentication and report fields inherit native behavior; a form's explicit border configuration may preserve its local Material shape.

### Navigation

Three always-labeled native destinations: **Bản đồ**, **Đóng góp**, **Của tôi**. Each pairs a Material icon with its label; selected icons become filled, with sage indicator and bold primary-colored label. Account and map options live in app-bar actions. Detail, account and activity content use native sheets or pushed pages with platform back behavior. Staff review queues remain outside this user app.

Theme selection lives in the account sheet as native segmented choices for device, light and dark. The initial value is device/system. The current choice is held in widget state and is not persisted across app restarts; do not describe it as a saved preference.

### Evidence Path

The signature `ContributionProgress` renders three equal-width step regions: **Ảnh**, **Kiểm tra**, **Gửi duyệt**. Each region centers its 36 dp circle and its label. Connectors run between the first and last circle centers across two equal segments, behind the circles. The complete path has 24 dp vertical padding and an 8 dp marker-to-label gap. Current/completed markers use primary/on-primary; upcoming markers use the high container and supporting text. Completed markers show a native check icon. Semantics identify step number and completed/current/next state.

The path advances from photo to checking, then to ready-to-submit only when label and location are confirmed. A completed confirmation step does not mean staff approval. Submission, pending review, acceptance, rejection and revalidation remain separate named states throughout history, detail and reporting surfaces. Reports state that staff review occurs before map updates.

### Notices and Recovery

Quiet notices use the low container and supporting foreground with an information icon; errors use the error-container pair and error icon. Notices have a 16 dp inset, small rounded corners and a 12 dp icon/text gap. Loading uses native progress indicators. Preserve retry, photo replacement and draft-discard actions, and provide explanatory text when submission is unavailable.

## Do's and Don'ts

### Do:
- **Do** apply paired Material color roles for the active light or dark scheme.
- **Do** preserve the three Vietnamese destination labels and native icon-plus-label navigation.
- **Do** keep confirmation, pending review, approval and revalidation visibly distinct through words and icons.
- **Do** keep evidence steps equally distributed, centered and readable with text scaling.
- **Do** keep controls at least 48 dp and let scrollable content accommodate larger text.
- **Do** use real evidence imagery in contribution/report flows and native library icons for interface actions.

### Don't:
- **Don't** imply that model detection, user confirmation or a submitted report immediately publishes approved map data.
- **Don't** replace semantic error or review-state communication with decorative green alone.
- **Don't** add decorative raster art, ornamental animation or editorial type treatments to this restrained native system.
- **Don't** treat the in-memory theme choice as a saved account preference.
- **Don't** claim iOS or physical-device acceptance from Android emulator or browser-preview evidence.

Not canonized: the earlier loose evidence-path alignment was a review finding and has been corrected in code; it is not a reusable pattern. Screenshot fixtures and their status-bar imagery are verification material, not shipping brand assets or platform-acceptance guarantees. Final native recapture and review verdict are recorded separately under `../.impeccable/review/`.

---
name: "MomenRia"
description: "Warm photo scrapbook, clear private portrait workspace."
colors:
  accent: "#ff7851"
  accent-hover: "#ff936f"
  gold: "#ba4528"
  lilac: "#cbbcf1"
  workspace-surface: "#eae5f1"
  lime: "#e5ef8a"
  peach: "#ffc1ac"
  ink: "#242423"
  muted: "#625f59"
  cream: "#f5f3ec"
  cream-soft: "#fffefa"
  surface: "#fff"
  soft: "#eeece5"
  line: "#deddd5"
  field-border: "#c5c2bb"
  danger: "#9e3832"
  ink-deep: "#101010"
  button-outline: "#b3b2a8"
  account-outline: "#949188"
  account-placeholder: "#66645f"
  nav-hover: "#e6e1ed"
  tag-surface: "#edf1d4"
  tag-border: "#d4d9aa"
  notice-surface: "#f9eed6"
  notice-ink: "#6a4b19"
  notice-border: "#eaddb9"
  danger-hover: "#7e2924"
  error-surface: "#fff0ea"
typography:
  display:
    fontFamily: "'Bricolage Grotesque', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "clamp(3.25rem,5.25vw,4.75rem)"
    fontWeight: 750
    lineHeight: 1.08
    letterSpacing: "-.04em"
  headline:
    fontFamily: "'Bricolage Grotesque', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "clamp(2rem,3.5vw,3.3rem)"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-.04em"
  title:
    fontFamily: "'Bricolage Grotesque', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1.2rem"
    fontWeight: 650
    lineHeight: 1.08
    letterSpacing: "-.025em"
  workspace-title:
    fontFamily: "'Bricolage Grotesque', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "clamp(1.75rem,3vw,2.5rem)"
    fontWeight: 750
    lineHeight: 1.08
    letterSpacing: "-.04em"
  account-title:
    fontFamily: "'Bricolage Grotesque', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "clamp(28px,5vw,36px)"
    fontWeight: 750
    lineHeight: 1.15
    letterSpacing: "-.04em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: ".875rem"
    fontWeight: 650
    lineHeight: 1.6
  field-label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: ".875rem"
    fontWeight: 600
    lineHeight: 1.6
  helper:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: ".875rem"
    fontWeight: 400
    lineHeight: 1.6
  account-button:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "16px"
    fontWeight: 650
    lineHeight: 1.4
rounded:
  thumbnail: "8px"
  notice: "10px"
  control: "12px"
  photo: "14px"
  tile: "16px"
  surface: "20px"
  panel: "24px"
  workspace: "28px"
  feature: "36px"
  closing: "40px"
  pill: "999px"
spacing:
  compact: "8px"
  field: "12px"
  inline: "16px"
  section-gap: "20px"
  panel-gap: "24px"
  workspace: "28px"
  card: "32px"
  section: "40px"
  marketing: "92px"
  gutter: "clamp(24px,4.7vw,72px)"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: ".85rem 1.5rem"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: ".85rem 1.5rem"
  button-secondary-hover:
    backgroundColor: "{colors.soft}"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.surface}"
    typography: "{typography.account-button}"
    rounded: "{rounded.pill}"
    padding: "10px 20px"
  button-danger-hover:
    backgroundColor: "{colors.danger-hover}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "12px 14px"
    width: "100%"
  navigation:
    textColor: "{colors.muted}"
    rounded: "{rounded.pill}"
    padding: "10px 14px"
  navigation-active:
    backgroundColor: "{colors.lime}"
    textColor: "{colors.ink}"
  tag:
    backgroundColor: "{colors.tag-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: ".35rem .75rem"
  content-card:
    backgroundColor: "{colors.cream-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "{spacing.card}"
  upload-tile:
    backgroundColor: "{colors.cream}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tile}"
    padding: "14px"
    width: "100%"
  notice:
    backgroundColor: "{colors.notice-surface}"
    textColor: "{colors.notice-ink}"
    typography: "{typography.helper}"
    rounded: "{rounded.notice}"
    padding: "16px 18px"
  journey:
    textColor: "{colors.muted}"
    typography: "{typography.helper}"
---

# Design System: MomenRia

## Overview

**Creative North Star: "The Photo Scrapbook"**

Cream paper, dark ink, coral actions, lilac notes and lime highlights make MomenRia feel like a place to keep a family moment. Photographs lead the composition. White mounts, gently tilted marketing images and rounded paper surfaces supply the scrapbook character; the typography stays direct and readable.

Marketing screens use generous space and expressive Bricolage headings. Portrait work and account screens use compact headings, recognizable photo positions and quiet surfaces so the current task is easy to follow. Indonesian labels remain warm and concrete, while visible state labels distinguish an example, a saved photo, a pending review and an error.

**Key Characteristics:**

- Photo-led compositions with cream paper and white mounts.
- Dark ink for reading and coral for the principal action.
- Lilac and lime accents for orientation, selection and occasion collections.
- Expressive marketing headings with compact task and account typography.
- Rounded controls, visible focus and restrained state transitions.

This document enriches the direction approved on 9 October 2026. Normative values come from `static/app/server.css` and the later-loaded `static/app/account.css`; local captures in `.impeccable/review` inform the visual reading. The approved audit remains at `docs/design-audit-2026-10-09/README.md`. Sidecar ramps are derived preview metadata, not additional implemented theme tokens.

## Colors

The palette pairs warm paper neutrals with cheerful scrapbook accents; ink supplies the consistent reading and control color.

### Primary

- **Coral Action** (`accent`): principal creation, upload and account actions. **Soft Coral Hover** (`accent-hover`) brightens their interactive state.
- **Burnt Coral Emphasis** (`gold`): selected marketing heading emphasis and text-link hover. Its legacy name describes an accent role, not a metallic treatment.

### Secondary

- **Lilac Note** (`lilac`): heading highlights, occasion cards, optional references and active account sections.
- **Lilac Workspace Paper** (`workspace-surface`): the studio image stage and catalog filter tray.
- **Lilac Hover Wash** (`nav-hover`): app-navigation hover, with ink text.

### Tertiary

- **Lime Highlight** (`lime`): selected app navigation, current journey steps, ready photo positions and verified badges; also a large marketing accent surface.
- **Peach Occasion** (`peach`): moment collections and scrapbook step accents.
- **Pale Lime Tag** (`tag-surface`, `tag-border`): restrained status chips with ink text and a light outline.

### Neutral

- **Dark Ink** (`ink`): headings, body text, controls, focus rings and dark completion actions. Legacy `--green` uses this same ink value.
- **Deep Ink** (`ink-deep`): the dark completion-action hover; its existing variable is `--green-dark`.
- **Warm Muted Ink** (`muted`): helper text, metadata and secondary navigation. Main placeholders use the matching `--placeholder` alias.
- **Cream Paper** (`cream`): page canvas, modals and photo-assignment tiles.
- **Soft White Paper** (`cream-soft`): content panels, account cards and studio controls.
- **White Mount** (`surface`): fields and photo mounts.
- **Quiet Paper Wash** (`soft`): secondary hover, reply surfaces and preview backing.
- **Paper Divider** (`line`): outlines and section separators.
- **Field Outline** (`field-border`): main and inherited account input strokes.
- **Button Outline** (`button-outline`): main secondary-action stroke.
- **Account Outline** (`account-outline`): account secondary actions and textarea strokes; **Account Placeholder Ink** (`account-placeholder`) is the account-specific placeholder override.

### State colors

- **Warm Notice Paper** (`notice-surface`, `notice-border`, `notice-ink`): processing, mode and recovery information with a written explanation.
- **Brick Danger** (`danger`): errors, deletion and connection-loss emphasis; **Deep Brick Hover** (`danger-hover`) belongs to account danger actions.
- **Pale Error Paper** (`error-surface`): inline error backgrounds behind brick text.

**The Ink on Accent Rule.** Keep dark ink on coral, lilac and lime surfaces; use white text on brick danger actions and ink photo-position markers, and cream text on dark ink actions.

**The Written State Rule.** Pair state color with a visible label or explanation; selection, review and error state must remain understandable without color.

## Typography

**Display Font:** Bricolage Grotesque, locally served as a variable font with system sans-serif fallbacks.

**Body Font:** the platform system sans-serif stack. There is no separate label or monospace identity font.

**Character:** Bricolage gives short headings a familiar, slightly playful voice. System text keeps forms, dates, instructions and photo review easy to read. Explicit sizes and fluid clamps establish the hierarchy; the implementation does not define a mathematical type ratio.

### Hierarchy

- **Display** (`display`): wide-screen marketing hero; local responsive overrides reduce it at the existing breakpoints.
- **Headline** (`headline`): expressive marketing sections with tight tracking.
- **Title** (`title`): smaller Bricolage headings; specialized cards retain their observed local sizes.
- **Workspace title** (`workspace-title`): compact task and reading-page titles. Workspace subsections use the observed `1.5rem` size; the narrow studio title uses its `1.6rem` override.
- **Account title** (`account-title`): compact account headings with more line-height than the hero. Account subsections use their observed `24px` and `20px` sizes.
- **Body** (`body`): reading text and form controls. Main prose increases line-height locally; introductory copy uses its observed `660–700px` width caps.
- **Label and field label** (`label`, `field-label`): main actions and form labels. Field labels use the lighter observed weight; account labels remain body-sized.
- **Helper** (`helper`): captions, source dates, instructions and status. Narrow navigation and journey labels use their implemented `12px` equivalent where necessary.
- **Account button** (`account-button`): body-sized account actions with their own line-height.

**The Task Type Rule.** Use compact workspace and account roles on working screens; keep the large display role with marketing compositions.

**The Legible Form Rule.** Keep editable form controls at the implemented body size and preserve readable help for instructions and errors.

## Layout

The canvas uses fluid gutters and capped containers: app pages reach `1344px`, marketing and studio layouts `1440px`, reading pages `900px`, and the compact account area `720px`. The gutter token supplies the main horizontal rhythm; mobile sections retain their observed local padding.

Wide studio and result layouts put the portrait beside a smaller control column. Studio uses `1.7fr` beside a minimum `320px` control area; the result editor uses the same portrait ratio beside a minimum `265px` panel. Occasion and template collections start with three columns; a catalog with its collection sidebar uses two template columns. Paper panels group information with space and dividers.

The implemented breakpoints serve distinct changes: `1150px` reduces wide-screen spacing and hero typography; `1000px` moves collection navigation into a horizontal strip; `900px` stacks studio, result and support columns and introduces reachable task actions; `600px` produces single-column marketing, stacked comparisons and fixed app navigation. Account controls become full-width at `480px`. The `641–1150px` filter rule and `1600px` wide-screen adjustment remain local exceptions.

Narrow studio and result pages reserve bottom space for fixed upload/create or save actions above navigation and the safe area. Studio actions use the observed `76px` baseline plus safe-area inset; result saving uses its `80px` baseline. Keep matching bottom padding so controls cannot cover working content. Dialogs have bounded viewport dimensions; picker and comparison dialogs retain their specialized wider limits.

The compact portrait journey wraps when needed and marks the current step. Photos, assigned positions and review labels stay close together. Optional references and management details use native disclosures so they remain available without competing with the principal task.

## Elevation & Depth

Ordinary working surfaces rely on paper tone, borders and spacing. Shadows support photographic mounts, transient feedback and controls lifted above the page. Marketing photo tilt is a material cue; task panels, form fields and reading surfaces remain stable.

### Shadow Vocabulary

- **Photo mount:** `0 8px 16px #24242312,0 20px 35px #24242314` under marketing scrapbook photographs.
- **Portrait stage:** `0 12px 28px #24242310` beneath the white-framed studio portrait.
- **Action hover:** `0 4px 12px #24242318` beside the primary action's small lift.
- **Collection hover:** `0 6px 20px #24242318` on lifted occasion cards and straightened marketing cards.
- **Transient feedback:** `0 6px 30px #24242330` under dark toast feedback.
- **Fixed studio action:** `0 -4px 18px #24242312` separates the narrow task control from content.
- **Fixed save action:** `0 0 0 8px var(--cream),0 -6px 18px #24242312` supplies a paper margin around the narrow save control.

Native dialog backdrops use the implemented translucent ink wash with `5px` blur. Keyboard focus is a solid ink outline (`3px`) with separated offset (`5px`); focus remains distinct from elevation.

**The Paper First Rule.** Use tone, outline and space for ordinary task surfaces; keep lift and shadow with photo mounts, transient feedback and raised actions.

## Shapes

Pill actions and tags sit beside softly rounded fields, paper panels and photo tiles. Use the established rounded steps: smaller corners for thumbnails and fields, medium corners for assignments, and larger corners for paper surfaces. Circular position markers and journey numbers supplement short written labels.

White photo mounts and occasional asymmetric marketing corners preserve the scrapbook silhouette. Hero rotations and highlighted heading strips belong with expressive compositions. Studio frames, assigned-photo tiles and comparison views keep image positions recognizable; export framing preserves the whole image.

Fine solid borders delineate fields and content panels. Unfilled upload tiles use a dashed outline, becoming solid when ready. Errors retain the field and neighboring explanation rather than relying on border color alone.

## Components

### Buttons

Confident pills with a clear action name. Main actions use the normative primary and secondary variants and minimum `52px` height; compact actions retain minimum `44px` targets. Coral hover brightens, rises by `2px` and gains the small action shadow. Secondary hover uses quiet paper. The closing action uses cream text on ink, keeping that text through deeper-ink hover.

Account actions use body-sized type and minimum `48px` height, with their own secondary outline and danger hover. Main danger actions also use brick with white text. Destructive actions stay with management context and confirmation. Disabled buttons retain the platform state and observed `.48` opacity; busy forms use their separate subdued treatment.

### Chips and tags

Small pills with pale lime paper, a fine outline and ink text. Selected filter buttons use lime. Verified badges use lime; unverified badges preserve their pale warm surface and written label. Semantic pressed or current attributes accompany selection.

### Cards and containers

Cream-white paper panels combine fine divider borders and comfortable padding. Occasion cards use lilac, lime or peach surrounds. White photo mounts carry marketing tilt and shadow. Studio combines lilac portrait paper with soft-white controls, joined on wide screens and stacked on narrow screens.

### Inputs and fields

White fields use ink text, a fine outline, control-size corners and minimum `48px` height. Labels remain visible, placeholders readable and help adjacent. Textareas resize vertically. Errors use brick text on pale error paper; retry preserves useful input. All controls retain the keyboard outline.

### Navigation

Wide navigation uses muted labels, generous click areas, lime selection and lilac hover. Narrow navigation uses labeled icons on a fixed cream bar with safe-area padding. Account navigation remains a compact wrapping section list with lilac selection. Preserve semantic current state and visible keyboard focus.

### Photo assignment and review

Assignments pair a recognizable thumbnail or upload symbol with the numbered position and written readiness. Ready portrait markers display the attached source thumbnail directly in a circular `56px` target. A separate `24px` ink badge with a white border keeps the position number visible in the helper-size type (`14px` at the root size). Empty positions retain their numbered `44px` target; both states keep a named add-or-change action. The photo and its placement can therefore be read together on the portrait, alongside the matching upload tile.

Upload-tile hover uses quiet paper and an ink border. Result review displays each face's latest written state next to its source context. New result versions carry their own review state; narrow comparisons stack larger views while retaining face context.

### Icons

The main app's shared icon helper uses inline SVG with a `24 × 24` view box, current-color stroke, rounded line caps and joins, and observed `1.6` stroke width. Close, back, zoom, guidance and FAQ controls follow the same drawn vocabulary as navigation and actions; account-header SVGs match the view box, stroke color and weight. FAQ disclosure uses the plus SVG, rotating it when open. Keep visible labels or explicit accessible control names; decorative SVGs remain hidden from assistive technology. The existing sidecar previews use this same SVG vocabulary.

### Journey and status

The journey uses numbered circles and short labels, with lime for the current step and stronger ink type. Warm notices pair an inline icon with mode, processing or recovery text. Connection loss exposes a real recovery control; pending work gets no invented percentage or estimate. Native dialogs retain bounded scrolling, a persistent heading and an explicit close control.

Short state transitions affect background, color and lift; image scale and scrapbook hover remain modest. Reduced-motion preference disables animation and transitions. The sidecar carries these extensions and ten independently scoped component previews; it does not duplicate normative primitives.

## Do's and Don'ts

### Do:

- **Do** lead with photographs, identifiable people and the next useful action.
- **Do** use cream paper, dark ink and the existing coral, lilac and lime roles consistently.
- **Do** keep task and account headings compact while preserving expressive marketing compositions.
- **Do** keep fields body-sized, help readable and keyboard focus clearly visible.
- **Do** pair selection, readiness, review and error colors with written state and semantic attributes.
- **Do** reserve space for mobile navigation and fixed task actions, including the safe area.
- **Do** label template examples and synthetic results so illustration cannot be mistaken for likeness evidence.
- **Do** preserve native dialogs, disclosures and reduced-motion preference.

### Don't:

- **Don't** replace the approved cream, ink, coral, lilac and lime scrapbook identity with a generic application palette.
- **Don't** carry marketing-scale headings and photographic tilt into ordinary task panels and forms.
- **Don't** use white text on bright coral actions or depend on hover to establish readable contrast.
- **Don't** make state color, an unlabeled icon or a position number carry the whole instruction.
- **Don't** cover working content with fixed controls without matching bottom space.
- **Don't** let decorative framing imply more detail, longer retention or verified likeness.
- **Don't** present a synthetic example or polished interface as proof of production readiness.

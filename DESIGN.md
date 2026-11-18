---
name: MiroFish Local
description: A private harbour for charting how a question moves through a small simulated society.
colors:
  navy: "#12324a"
  navy-soft: "#37556b"
  navy-soft-on-land: "#2f4a5e"
  navy-soft-on-land-soft: "#324f64"
  navy-hover: "#1c4560"
  water: "#bfe0e6"
  water-soft: "#e4f2f4"
  land: "#e7d59b"
  land-soft: "#f6efd6"
  paper: "#fcfbf5"
  field: "#ffffff"
  magenta: "#b0187a"
  red: "#d9472b"
  red-hover: "#e4613f"
  ink: "#170704"
  rule: "rgba(18, 50, 74, 0.24)"
typography:
  display:
    fontFamily: "Alegreya, Songti SC, Noto Serif SC, Georgia, serif"
    fontSize: "clamp(2rem, 1.75rem + 1vw, 2.5rem)"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "-0.01em"
  question:
    fontFamily: "Alegreya, Songti SC, Noto Serif SC, Georgia, serif"
    fontSize: "1.375rem"
    fontWeight: 400
    lineHeight: 1.36
  title:
    fontFamily: "Alegreya, Songti SC, Noto Serif SC, Georgia, serif"
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.2
  heading:
    fontFamily: "Alegreya Sans SC, Alegreya Sans, PingFang SC, Noto Sans SC, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.015em"
  subheading:
    fontFamily: "Alegreya Sans SC, Alegreya Sans, PingFang SC, Noto Sans SC, sans-serif"
    fontSize: "0.906rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.015em"
  lede:
    fontFamily: "Alegreya Sans, PingFang SC, Noto Sans SC, Avenir Next, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.35
  body:
    fontFamily: "Alegreya Sans, PingFang SC, Noto Sans SC, Avenir Next, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.35
  small:
    fontFamily: "Alegreya Sans, PingFang SC, Noto Sans SC, Avenir Next, sans-serif"
    fontSize: "0.906rem"
    fontWeight: 400
    lineHeight: 1.35
  button:
    fontFamily: "Alegreya Sans, PingFang SC, Noto Sans SC, Avenir Next, sans-serif"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1
  control-small:
    fontFamily: "Alegreya Sans, PingFang SC, Noto Sans SC, Avenir Next, sans-serif"
    fontSize: "0.906rem"
    fontWeight: 500
    lineHeight: 1
  label:
    fontFamily: "Alegreya Sans SC, Alegreya Sans, PingFang SC, Noto Sans SC, sans-serif"
    fontSize: "0.844rem"
    fontWeight: 500
    lineHeight: "20px"
  sounding:
    fontFamily: "Alegreya, Songti SC, Noto Serif SC, Georgia, serif"
    fontWeight: 500
    fontFeature: "onum"
rounded:
  none: "0px"
  control: "2px"
spacing:
  space-1: "4px"
  space-2: "8px"
  space-3: "12px"
  space-4: "16px"
  space-5: "24px"
  space-6: "32px"
  space-7: "44px"
  gutter: "clamp(16px, 3vw, 44px)"
  control: "34px"
  control-coarse: "44px"
  topbar: "48px"
components:
  button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.navy}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 13px"
    height: "{spacing.control}"
  button-hover:
    backgroundColor: "{colors.water-soft}"
  button-disabled:
    backgroundColor: "{colors.land-soft}"
    textColor: "{colors.navy-soft}"
  button-action:
    backgroundColor: "{colors.red}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 13px"
    height: "{spacing.control}"
  button-action-hover:
    backgroundColor: "{colors.red-hover}"
  button-action-large:
    backgroundColor: "{colors.red}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 26px"
    height: "50px"
  textarea-question:
    backgroundColor: "{colors.field}"
    textColor: "{colors.navy}"
    typography: "{typography.question}"
    rounded: "{rounded.control}"
    padding: "13px 15px"
  select:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.navy}"
    typography: "{typography.control-small}"
    rounded: "{rounded.control}"
    padding: "0 26px 0 9px"
    height: "32px"
  select-on-navy:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.paper}"
  tag:
    textColor: "{colors.navy}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 7px"
  tag-latest:
    backgroundColor: "{colors.land}"
    textColor: "{colors.navy}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 7px"
  topbar:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.paper}"
    height: "{spacing.topbar}"
  nav-link:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.paper}"
    padding: "0 15px"
    height: "{spacing.topbar}"
  nav-link-hover:
    backgroundColor: "{colors.navy-hover}"
  nav-link-current:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.navy}"
  segment:
    textColor: "{colors.navy}"
    typography: "{typography.control-small}"
    padding: "0 11px"
  segment-pressed:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.paper}"
  origin-simulated:
    textColor: "{colors.magenta}"
    typography: "{typography.label}"
---

# Design System: MiroFish Local

## Overview

**Creative North Star: "The Private Harbour Chart"**

MiroFish Local reads like a working nautical chart kept on the researcher's own desk. Water, land and paper are the surfaces; navy is the survey ink; thin rules do the structural work that cards and shadows do elsewhere. The chart metaphor lives in colour, line and figures only, so the interface stays a serious instrument for long local runs rather than a themed one.

The system's central duty is provenance. A surveyed fact and a simulated one must never look alike, so every surface shares one line language: solid navy for source material, dashed magenta for simulation, dotted soft navy for facts with no recorded origin. The same language runs from the graph into report text, interview answers and activity feeds.

Density is high and calm: compact 34px controls, a 48px top bar, tabular figures, and panes that stay in place while a run moves underneath them. The direction explicitly refuses the generic AI dashboard and the hacker terminal.

**Key Characteristics:**
- Flat chart surfaces divided by 1px navy rules, with no shadows anywhere in the routed app.
- Near-square controls (2px) and square panels.
- A three-voice Alegreya family: serif for the researcher's content, sans for the interface, small caps for labels.
- Provenance carried by line style and colour together, never by colour alone.
- Red kept for what the researcher can act on; status carried by shape and navy.

## Colors

A printed-chart palette: pale water and buff land on warm paper, navy survey ink, and two signal colours with strictly separate jobs.

### Primary
- **Sounding Navy** (#12324a): All default text, control borders, structural rules, the top bar, pressed and current states, progress fill and source-fact lines.
- **Harbour Night Hover** (#1c4560): Hover fill for links on the navy top bar.

### Secondary
- **Buoy Red** (#d9472b): Fill of the action button and the underline of inline links. Text on it is Hull Ink (#170704), never white.
- **Lit Buoy** (#e4613f): Action button hover, moving lighter so ink contrast rises.

### Tertiary
- **Notice Magenta** (#b0187a): Simulated material only: dashed graph tracks, origin labels, dashed row rules, simulated initials and not-a-forecast notes.

### Neutral
- **Chart Paper** (#fcfbf5): The page and working panes; default button fill.
- **Field White** (#ffffff): Editable text fields only, so places to write stand out from paper.
- **Chart Water** (#bfe0e6): Context bands such as the run bar and workflow strip; drop-zone hover; running status fill.
- **Shallow Water** (#e4f2f4): Graph canvas, drop zone, active stage and neutral hover.
- **Chart Land** (#e7d59b): Side rails and summary bands; the latest-activity mark; text selection; focus ring on navy.
- **Pale Land** (#f6efd6): Secondary work rails, logs, graph key and disabled controls.
- **Soft Sounding** (#37556b): Secondary text and placeholders. It darkens on land (#2f4a5e) and pale land (#324f64) to hold contrast.
- **Hairline Rule** (rgba(18, 50, 74, 0.24)): Dividers between rows inside a section.

### Named Rules
**The Survey Line Rule.** Dashed magenta means simulated and nothing else; solid navy means source; dotted soft navy means the origin is unlinked. Other dashes may exist, such as the logo ring in water blue, but none may be magenta.

**The Buoy Rule.** Red marks what can be acted on: action buttons and link underlines. It never signals error, warning or status.

**The Land Legibility Rule.** Magenta text stays off full Chart Land, where it reaches only 4.42:1; pale land, paper and both waters all clear 4.5:1.

## Typography

**Display Font:** Alegreya (with Songti SC, Noto Serif SC, Georgia, serif)
**Body Font:** Alegreya Sans (with PingFang SC, Noto Sans SC, Avenir Next, sans-serif)
**Label/Mono Font:** Alegreya Sans SC (with Alegreya Sans, PingFang SC, Noto Sans SC, sans-serif)

**Character:** One humanist family in three voices, with the calligraphic warmth of an old chart's lettering and the economy a dense tool needs. Chinese fallbacks are part of each stack because language switching is a product requirement.

### Hierarchy
- **Display** (700, clamp(2rem to 2.5rem), 1.05): The single page or report title.
- **Question** (400, 1.375rem, 1.36): The researcher's scenario question, set in the serif as authored content; drops to 1.125rem on phones.
- **Title** (700, 1.125rem, 1.15 to 1.2): Run names and panel-level serif titles; recent-run titles use the same voice at 1.0625rem.
- **Heading** (700 small caps, 1.0625rem, 1.2, +0.015em): Section headings in panes and rails.
- **Subheading** (700 small caps, 0.906rem, 1.2, +0.015em): Groups inside a section.
- **Lede** (400, 1.125rem, 68ch maximum): The one introductory sentence beneath a display title.
- **Body** (400, 1rem, 1.35): Interface text. Long reading is held to 68ch to 72ch, and report text to a 46rem column.
- **Small** (400, 0.906rem): Metadata, notes and dense lists.
- **Label** (500 small caps, 0.844rem, 20px): Tags and origin labels; simulated origin labels step up to 700.
- **Sounding** (500 italic serif, oldstyle figures, inherited size): Ordinals and chart counts such as stage numbers and fact totals.

### Named Rules
**The Two Figures Rule.** Measured values that must align use tabular lining figures; chart-like ordinals and counts use italic oldstyle soundings.

**The Small Caps Rule.** Compact labels use the true small-caps face at a slight +0.015em. They are never produced with uppercase transforms and wide tracking.

## Layout

The app is a full-height chart table. A 48px navy top bar sits above each route; run routes add a water-blue stage bar with run name, five numbered stages, status and a Graph / Split / Workbench switch. In Split view, the work pane takes the remaining width and the graph takes clamp(420px, 42%, 680px). Hidden panes stay mounted so run state and scroll position survive a layout change, and panes scroll independently.

The start screen pairs a form column (content capped at 64rem) with a 20rem to 26.5rem land rail, with the five-stage strip in water beneath the form. Page gutters use the fluid gutter token; working panes use 16px insets.

Spacing follows a 4, 8, 12, 16, 24, 32, 44px scale, with 8 and 12 doing most of the work. Small optical values (2, 6, 7, 9, 11, 13px) appear inside dense rows and controls. Pointer-coarse devices raise the control height from 34px to 44px.

Pages respond at 1280px (stages take their own row), 1080px (top-bar status takes its own row), 980px on run routes and 960px on the start screen (panes and rail stack), and 620px and 560px (navigation scrolls, labels condense, the primary action goes full width). Panels also use container queries, so they adapt to the pane they are in rather than only to the window.

## Elevation & Depth

The system is flat. No routed surface uses a shadow; depth comes from the change between paper, water and land, from 1px navy rules at structural edges, and from hairline rules within a section. Selection and current state invert to solid navy or paper rather than lifting.

### Named Rules
**The Printed Chart Rule.** Surfaces are printed, not stacked. Separate them with tone and rule; do not add shadow, blur or glow.

## Shapes

Corners are 2px on controls, tags, code blocks and quoted excerpts, and 0 on panes, bands and the drop zone. Status marks are 10px squares whose fill carries the state. Curves belong to data: graph entity types use circle, square, diamond and triangle marks in land, navy, water and paper, and the only circular interface element is the loading ring in the interview tools. Icons are thin 1.5px line drawings in SVG with no fill.

## Components

### Buttons
Plain, firm and printed; hierarchy comes from fill alone.
- **Shape:** Near-square (2px) with a 1px border, 34px tall, 44px on coarse pointers.
- **Default:** Chart Paper with navy text and border, 13px side padding, bold sans.
- **Action:** Buoy Red with Hull Ink text and border. Forward and send actions in each stage use it; the start action uses the large 50px size.
- **Hover / Focus:** Background shifts over 120ms ease-out, with no movement. Focus is a 2px navy outline offset 2px, switching to Chart Land on navy and insetting where a scroller or top bar would clip it.
- **Disabled:** Pale land fill, soft navy text and border, not-allowed cursor.

### Chips
- **Style:** 1px navy border, 2px corners, small-caps label on a 20px line.
- **State:** Selectable ontology chips rest on paper, hover to shallow water and invert to navy when pressed. The land-filled Latest tag marks the newest round and log line.

### Cards / Containers
- **Corner Style:** Square panels; there is no floating card pattern.
- **Background:** Paper for work, water for context bands, land and pale land for rails and logs.
- **Shadow Strategy:** None, per Elevation & Depth.
- **Border:** 1px navy at structural edges, hairline rule between rows.
- **Internal Padding:** 8px to 16px in panes; rails on the start screen use 26px to 30px.

### Inputs / Fields
- **Question Field:** White, 1px navy border, 2px corners, serif at reading size, with 13px by 15px padding.
- **Select:** Paper with a soft navy border, 32px tall and a drawn chevron; inverts on the navy top bar.
- **Checkbox:** 15px square, filling navy with a paper check.
- **Focus / Disabled:** The shared 2px outline; disabled fields take pale land and soft navy text.

### Navigation
- **Top Bar:** Navy, 48px, serif wordmark with the fish logo redrawn in chart colours, then links, local status in water blue and the language select.
- **Links:** Medium sans with 15px side padding, navy-hover on hover. The current page becomes a paper tab with bold navy text joined to the bar.
- **Stages:** Numbered soundings joined by short navy rules; the current stage fills navy.
- **Segmented Switch:** Joined bordered buttons at 0.906rem; the pressed option fills navy.
- **Narrow Screens:** Navigation moves to its own scrolling row below 620px, and inactive stage names collapse to their numbers.

### Status Mark
A 10px square with a 1.5px navy border, readable without colour: empty for idle, water for running, solid for completed, half-filled for stopped and crossed for failed. The label beside it is bold, except idle at medium weight.

### Provenance Linework
The signature of the system. In the graph, source facts are 1.5 solid navy lines, simulated facts are 1.7 magenta lines dashed 7 and 4.5, and unlinked facts are 1.6 soft navy round dots spaced 1.2 and 4. Ended facts thin to 1.1 and fade. Active lines rise to 2.3 and traced lines to 3.4, with a 12px invisible stroke for easy selection. The land-coloured graph key repeats each line beside a checkbox and count, and report, feed and interview rows reuse the same language as 1px solid or dashed top rules with small-caps origin labels.

### Fact Sheet
Definition rows with a muted term column and medium-weight value, separated by hairline rules. They carry privacy status and run details so real system state reads as a record rather than a badge.

### Motion
Motion is brief and functional: 120ms ease-out for fills, stroke weight and chevrons. New simulation rows arrive on Chart Land and settle over 700ms. Waiting states use quiet opacity pulses or a linear spinner, and reduced-motion preferences collapse all of it.

## Do's and Don'ts

### Do:
- **Do** take colours, type sizes, spacing and control heights from the `--hb-` custom properties in `frontend/src/styles/harbor.css`.
- **Do** label simulated material with both dashed magenta and words, in every surface where it appears.
- **Do** pair every status colour with a shape or label, as the status mark does.
- **Do** use Hull Ink (#170704) on Buoy Red.
- **Do** switch secondary text to the darker soft navy on land surfaces by using the surface classes.
- **Do** keep hidden panes mounted when changing layouts during a run.
- **Do** keep charts and tables in tabular figures where values must align.

### Don't:
- **Don't** use magenta for emphasis, branding or anything that is not simulated material.
- **Don't** use red for errors, warnings or status; failed work uses the crossed navy mark.
- **Don't** present simulated material with the solid source line, even when a merged item also contains source facts.
- **Don't** add shadows, blurs, glows or gradients to surfaces.
- **Don't** round controls beyond 2px or give panels rounded corners.
- **Don't** add anchors, waves, compass roses or other nautical icons and ornament.
- **Don't** set labels in tracked uppercase; use Alegreya Sans SC.
- **Don't** drift toward the generic AI dashboard or the hacker terminal.

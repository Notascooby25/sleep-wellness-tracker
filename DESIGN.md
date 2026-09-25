---
name: Sleep & Wellness Tracker
description: A unified dashboard for objective Garmin biometrics and subjective wellness data.
colors:
  primary: "#dceeff"
  primary-content: "#173a5c"
  primary-border: "#9ec0e7"
  neutral-text: "#132238"
  neutral-text-muted: "#496685"
  neutral-bg: "#ffffff"
  neutral-border: "#d9e2ef"
  background-gradient-start: "#f9fbff"
  background-gradient-end: "#f2f6fc"
typography:
  body:
    fontFamily: "'DM Sans', 'Segoe UI', Tahoma, sans-serif"
    fontSize: "1rem"
  label:
    fontFamily: "'DM Sans', 'Segoe UI', Tahoma, sans-serif"
    fontSize: "0.86rem"
rounded:
  sm: "10px"
  md: "12px"
  lg: "16px"
  pill: "999px"
spacing:
  sm: "12px"
  md: "16px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-content}"
    rounded: "{rounded.sm}"
    padding: "0.48rem 0.72rem"
  card:
    backgroundColor: "{colors.neutral-bg}"
    rounded: "{rounded.md}"
    padding: "12px"
  input:
    backgroundColor: "{colors.neutral-bg}"
    rounded: "{rounded.sm}"
    padding: "0.45rem 0.55rem"
---

# Design System: Sleep & Wellness Tracker

## Overview

**Creative North Star: "The Quiet Sanctuary"**

This application serves as a soft, calming, and reflective space for ending the day and reviewing wellness. The aesthetic is explicitly calm, airy, and inviting, leaning on soft gradients and gentle contrast rather than sharp divides. It is an introspective tool designed to make reviewing health metrics a peaceful ritual rather than a stressful data-entry chore.

**Key Characteristics:**
- Gentle, low-contrast UI with airy spacing.
- Pale blues and muted slates dominating the palette.
- Friendly, tactile components with rounded corners.
- Flat default surfaces with no heavy shadows.

## Colors

The palette feels like a crisp morning sky fading into a calm evening. 

### Primary
- **Soft Morning Blue** (#dceeff): The primary accent for interactive elements like buttons. Soft but clearly clickable.
- **Morning Blue Content** (#173a5c): The deep text color used inside primary buttons for accessible contrast.
- **Morning Blue Border** (#9ec0e7): A subtle outline for interactive primary elements.

### Neutral
- **Deep Night Slate** (#132238): The primary text color across the app. High contrast without the harshness of pure black.
- **Muted Slate** (#496685): Used for secondary text, labels, and timestamps.
- **Card Background** (#ffffff): Pure white for data containers to lift them subtly off the background gradient.
- **Soft Border** (#d9e2ef): Used to separate sections cleanly without visual noise.

### Named Rules
**The Low-Contrast Calm Rule.** Never use pure black (`#000000`) or pure white (`#ffffff`) for page backgrounds. Rely on the soft `#f9fbff` to `#f2f6fc` gradient to maintain the sanctuary feel.

## Typography

**Body Font:** 'DM Sans', 'Segoe UI', Tahoma, sans-serif

**Character:** Friendly, geometric, and modern. It balances data readability with a soft, approachable tone.

### Hierarchy
- **Body** (400, 1rem, normal): General paragraph text and readable content.
- **Label** (400, 0.86rem, normal): Small text for field labels, table headers, and metadata.

## Layout

The application centers around a single-column constraints model that expands to grids for data display.
- **Main Container:** Constrained to `1120px` maximum width, centered, with `1rem` of ambient padding.
- **Rhythm:** `12px` default gap between grid cards, ensuring dense but breathable data visualization.
- **Responsive:** Multi-column grids (two or three columns) collapse gracefully to a single column below `860px`.

## Elevation & Depth

This system relies on a strictly flat visual hierarchy, using tonal layering and borders rather than drop shadows to separate content.

### Named Rules
**The Flat Sanctuary Rule.** Surfaces are flat at rest. Rely entirely on the soft borders (`#d9e2ef`) and the off-white background gradients to separate cards from the page. Any legacy drop shadows on hero elements should be phased out in favor of this clean, modern approach.

## Shapes

Forms are soft, friendly, and tactile. Sharp corners are avoided to maintain the calming environment.

- **Interactive Elements (Buttons, Inputs):** 10px radius.
- **Data Cards:** 12px radius.
- **Hero Containers:** 16px radius for the largest structural elements.
- **Badges:** Fully rounded (999px).

## Components

Components feel tactile and friendly, with soft borders and inviting paddings.

### Buttons
- **Shape:** Softly rounded (10px).
- **Primary:** Soft Morning Blue background with Deep Night Slate text. Includes a subtle border.
- **State:** Disabled buttons drop to 50% opacity and use a `not-allowed` cursor.

### Cards / Containers
- **Corner Style:** 12px radius.
- **Background:** Solid white.
- **Border:** 1px solid `#d9e2ef`.
- **Internal Padding:** 12px.

### Inputs / Fields
- **Style:** 10px radius, white background, soft border (`#c7d9ef`).
- **Padding:** Comfortable inner padding (0.45rem 0.55rem).
- **Labels:** Set slightly smaller (0.86rem) in Muted Slate above the field.

### Badges
- **Shape:** Pill (999px radius).
- **Style:** Very pale blue background (`#ecf5ff`) with a slightly stronger border and text (`#1d4b76`).
- **Padding:** 0.12rem vertical, 0.58rem horizontal.

## Do's and Don'ts

### Do:
- **Do** wrap primary interactive elements in the standard 10px border radius to maintain tactile friendliness.
- **Do** ensure all text uses the Deep Night Slate (`#132238`) or Muted Slate (`#496685`) rather than harsh blacks.

### Don't:
- **Don't** add drop shadows to cards or modals. Rely on the Flat Sanctuary Rule.
- **Don't** use sharp, 0px border radii anywhere in the UI.

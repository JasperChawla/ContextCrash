---
name: Technical Precision
colors:
  surface: '#131315'
  surface-dim: '#131315'
  surface-bright: '#39393b'
  surface-container-lowest: '#0e0e10'
  surface-container-low: '#1c1b1d'
  surface-container: '#201f22'
  surface-container-high: '#2a2a2c'
  surface-container-highest: '#353437'
  on-surface: '#e5e1e4'
  on-surface-variant: '#c2c6d5'
  inverse-surface: '#e5e1e4'
  inverse-on-surface: '#313032'
  outline: '#8c909e'
  outline-variant: '#424753'
  surface-tint: '#acc7ff'
  primary: '#acc7ff'
  on-primary: '#002f68'
  primary-container: '#3274d9'
  on-primary-container: '#ffffff'
  inverse-primary: '#005bbf'
  secondary: '#ffb597'
  on-secondary: '#591d00'
  secondary-container: '#9d3900'
  on-secondary-container: '#ffc4ac'
  tertiary: '#c6c6c7'
  on-tertiary: '#2f3131'
  tertiary-container: '#757676'
  on-tertiary-container: '#ffffff'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d7e2ff'
  primary-fixed-dim: '#acc7ff'
  on-primary-fixed: '#001a40'
  on-primary-fixed-variant: '#004492'
  secondary-fixed: '#ffdbcd'
  secondary-fixed-dim: '#ffb597'
  on-secondary-fixed: '#360f00'
  on-secondary-fixed-variant: '#7e2c00'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c6c7'
  on-tertiary-fixed: '#1a1c1c'
  on-tertiary-fixed-variant: '#454747'
  background: '#131315'
  on-background: '#e5e1e4'
  surface-variant: '#353437'
typography:
  h1:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  h2:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  h3:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  body-base:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  mono-data:
    fontFamily: monospace
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
  gutter: 12px
  margin: 24px
---

## Brand & Style

This design system is engineered for high-stakes AI reliability benchmarking. It prioritizes information density and technical utility over decorative flair. The style is **Minimalist-Utility**, drawing inspiration from developer-centric tools like Linear and Vercel. 

The brand personality is serious, objective, and authoritative. It targets Machine Learning engineers and Data Scientists who require a "cockpit" experience—where data is the primary interface and the UI serves as a transparent container. The visual language avoids all "bubbly" or consumer-oriented trends in favor of sharp, rigorous, and compact arrangements.

## Colors

The palette is strictly functional. The foundation is a **near-black deep slate (#09090B)**, providing a high-contrast base for technical data.

- **Primary:** A restrained slate-blue (#3274D9) used for primary actions and "Pass" status indicators.
- **Secondary:** A technical orange (#E86F37) reserved exclusively for "Warning" or "Drift" states in ML models.
- **Surface & Cards:** Surfaces utilize #18181B with a #27272A border. This creates a subtle layered effect without the need for shadows.
- **Neutral/Text:** Pure white (#FFFFFF) is reserved for high-emphasis headings, while muted grays are used for secondary data to manage visual hierarchy in dense views.

## Typography

This system uses **Inter** exclusively to maintain a systematic and utilitarian feel. The scale is intentionally small to accommodate high-density data visualizations.

- **Legibility:** All type weights are kept at 400 or 600. No ultra-thin weights are used to ensure readability on dark backgrounds.
- **Data Display:** For model logs, hashes, and coordinate values, use a system monospace stack to ensure horizontal alignment.
- **Emphasis:** Use the `label-caps` style for section headers within sidebars and small metadata tags.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid** model. Navigation and sidebars are fixed-width, while the central dashboard area is a fluid 12-column grid that expands to fill the screen, maximizing the visibility of charts and tables.

Spacing is based on a **4px base unit**. Gutters are kept tight (12px) to allow more data to fit above the fold. Components should use the "compact" setting by default—standardizing on 8px (sm) and 12px (between sm and md) for internal padding.

## Elevation & Depth

Depth is conveyed through **Tonal Layering** rather than shadows. This system avoids all ambient shadows to maintain a flat, technical aesthetic.

- **Level 0 (Background):** #09090B.
- **Level 1 (Cards/Sidebar):** #18181B with a 1px solid border (#27272A).
- **Level 2 (Popovers/Tooltips):** #27272A with a slightly lighter 1px border (#3F3F46).

Interactive elements like buttons should appear "set into" the surface or flush, rather than floating.

## Shapes

The design system uses **Soft (0.25rem)** roundedness. This provides just enough curvature to feel modern without losing the "engineering-tool" sharpness. 

- **Containers:** All cards, inputs, and buttons use a 4px (0.25rem) radius.
- **Checkboxes:** Use a 2px radius for a sharper, more precise appearance.
- **Icons:** Use a 1.5px stroke width to match the visual weight of the Inter typeface at small sizes.

## Components

- **Buttons:** Primary buttons use a solid #3274D9 background with white text. Ghost buttons use a 1px #27272A border and no background until hover.
- **Inputs:** High-density height (32px). Background is #09090B (inverted from card color) to create a "well" effect.
- **Data Tables:** The core of the product. Use 1px #27272A horizontal borders only. Zebra striping is not permitted; use hover-state highlighting instead.
- **Status Chips:** Small, rectangular badges with a subtle background tint and 100% opacity text (e.g., "Pass" = deep green tint, "Fail" = deep red tint).
- **Metric Cards:** Use "H2" for the value and "Label-Caps" for the title. No icons in metric cards unless they indicate trend direction (up/down).
- **Tooltips:** Immediate appearance (no delay), dark gray background (#18181B), and monospaced font for data values.
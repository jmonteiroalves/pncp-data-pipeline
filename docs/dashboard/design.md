# Dashboard design notes

## Brief

- Subject: Brazilian public procurement published through the PNCP.
- Audience: hiring managers and data practitioners reviewing the portfolio.
- Job: make the scale and the AI classification credible at a glance, without
  looking like a generic analytics template.
- Constraint: one day per month (first Tuesday), so the page shows monthly
  snapshots, not a continuous daily trend.

## Direction

A public procurement **gazette/ledger**: paper, ink, ruled columns, tabular
figures, and a certification stamp. The visual language comes from official
editions and audit records, not from SaaS dashboards.

It deliberately avoids the current defaults: no dark background with an acid
accent, no identical rounded cards, no soft shadows, no gradient decoration, no
eyebrow labels above every heading, and no fake trend line for a single monthly sample.

## Tokens

| Token | Value | Use |
|---|---|---|
| paper | `#F3EFE4` | page background |
| ink | `#17231F` | primary text and rules |
| graphite | `#5C6961` | secondary text |
| rule | `#CFC6B4` | hairlines |
| seal | `#A33B2B` | the single bold accent, stamp |
| petrol | `#35586B` | transport / links |
| olive | `#6E7052` | secondary data |

Type:

- **Newsreader** — display and body. Serif, optical sizes, 400/600/700.
- **IBM Plex Mono** — figures, dates, edition metadata, chart labels.

Two families. Body line length stays under 78 characters. Data uses tabular
monospace so columns line up.

## Layout

```text
┌──────────────────────────────────────────────────────────┐
│ Diário de Compras                      amostra mensal     │
├──────────────────────────────────────────────────────────┤
│ O que o governo                    ┌───────────────┐     │
│ compra                             │ CLASSIFICAÇÃO │     │
│                                    │   POR IA      │     │
│ lead paragraph                     │    91,0%      │     │
│                                    └───────────────┘     │
├────────┬────────┬────────┬────────┬────────┬─────────────┤
│ 5.583  │ 2.407  │ R$33,1 │ R$1,30 │ 91,0%  │             │
├────────┴────────┴────────┴────────┴────────┴─────────────┤
│ Valor por categoria           │ Amostra auditada          │
│ horizontal ruled bars         │ stamp + month table       │
├───────────────────────────────┴───────────────────────────┤
│ Uma terça por mês — grouped columns                       │
├───────────────────────────────┬───────────────────────────┤
│ Órgãos                        │ Estados                   │
└───────────────────────────────┴───────────────────────────┘
```

Left-aligned. One wide column for the lead, one narrow column for the stamp.
No card containers; sections are separated by rules and whitespace.

## Principles

1. The stamp is the one memorable element; everything else stays quiet.
2. Every rule and column carries information (edition, section, table).
3. Data honesty: monthly snapshots are compared as columns, not a daily trend line.
4. Copy is specific and plain: what was counted, when, and how much the AI
   covered.
5. No motion. The page should read like a printed edition.

## Self-critique

The first pass was a dark SaaS dashboard with rounded cards, neon mint bars,
and a gradient wash — exactly the default the brief warns against. The redesign
replaces the card kit with a single page document, trades neon for a restrained
ink-and-paper palette, and uses the stamp to make the AI coverage memorable
without decorating every section. The chart is grouped columns by month because
a line would imply a continuous trend the monthly sample cannot support.

# MRA's report code

MedicalReviewerAgent's report (`<Report>` and `<QuickAnswer>`), copied from
`MedicalReviewerAgent/frontend/src` on 2026-10-27 with the files they import,
so a Medical Review opens on MRA's own report drawn from the review kept with
the Run (`GET /api/runs/{id}/service-data`), without a frame.
`components/mra-view.tsx` renders it in a shadow root.

The copy keeps MRA's folders (`components/`, `lib/`) and moves `@/` imports
to `@mra/`. What differs from MRA's code:

- `report.css` is MRA's `app/globals.css` with `:root` and `body` as `:host`,
  compiled on its own (`?inline`); DeepLit's stylesheet skips this folder.
- `lib/host.ts` is new: lookups by id (`report-nav`, `report`, `rail-drawer`)
  and the colour tokens (`charts/tokens`, `theme-toggle`, `print-mode`) read
  the shadow root and its host instead of the document.
- `report.tsx`: no `pt-8` (the page gives the space), `--header-h` under
  DeepLit's header, the document's `lang` left alone.
- `quick-answer.tsx`: `upgrade={false}` hides "run a full review" (MRA's own form).
- Layout widths sit 16rem higher (`APP_CHROME_PX`, DeepLit's sidebar): the `md`-and-up breakpoints in
  `report.css`, `use-wide.ts`, `rail-drawer.tsx` and `LIT_TABLE_MIN_WIDTH` in `lit-matrix.tsx`.
- `lib/config.ts`: no `NEXT_PUBLIC_API_URL`.
- `shims-link.tsx` stands in for `next/link` (from MRA's `standalone/shims`).

## DeepLit's layout (2026-11-06)

The report keeps every block and rule MRA draws from the review (which sections each review type has, what is left out
when the data is missing, verified and computed numbers, the four audiences) and lays them out differently, from the
approved mock:

- **Colours and type** are `report.css`'s tokens: a blue-grey ground, white cards, navy; IBM Plex Sans Thai and IBM Plex
  Mono. Charts read the same tokens.
- `report-head.tsx` replaces `title-block.tsx`: the answer band across the page with its figures, the PICO cards, the
  toolbar. `ReadingCard` (`bottom-line.tsx`) holds what stays of the bottom line.
- `lib/report-toc.ts` and `ReportChapters` (`report-nav.tsx`): six chapters; only the one being read opens its sections.
  The list beside the report is as wide as its longest label and keeps that width while the reader moves.
- **Section order** (`lib/review-type.ts`): the results before the table of studies, the discussion before the gaps, the
  references last of all, small. The committee view brings "agree and conflict" forward with the risk of bias.
- **PRISMA** reads left to right from a 48rem card, with a chart/table switch. The **study map** has its own card, and
  the **citation network** spaces its years evenly (in order, not to scale). **Filters** are chips and add direction;
  **study tiles** sit above them. The **source rail** floats over the page from `lg`.
- **Downloads** come from `MraView` (HTML, Markdown, JSON from DeepLit's API); `lib/export-csv.ts` makes the CSV from the
  review, with the columns of MRA's `render_csv`.

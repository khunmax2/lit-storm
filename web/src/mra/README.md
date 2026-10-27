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
- `lib/config.ts`: no `NEXT_PUBLIC_API_URL`.
- `shims-link.tsx` stands in for `next/link` (from MRA's `standalone/shims`).

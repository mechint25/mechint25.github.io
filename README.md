# Interactive paper site

Static research companion for *Multiple Recovery Paths in a Lesioned Transformer: Internal Rerouting and Readout Remapping* (Cannata and Hasson, BlackboxNLP 2026).

## Reading route

1. `index.html` defines the exhibit and concise scientific copy.
2. `app.js` implements the stage model, condition linking, empirical layer summaries, and endpoint explorer.
3. `styles.css` defines the shared visual semantics, responsive layout, focus states, and reduced-motion behavior.
4. `assets/data/site-data.json` contains the public endpoint and seed values.
5. `assets/data/representation-states.json` contains the six final-state, fixed-basis token projections used by the interactive representation explorer.
6. `SOURCE_MANIFEST.md` traces claims and visuals to configurations, experiment records, checksums, and known discrepancies.
7. `scripts/build_research_assets.py` regenerates the A0 portrait SVG/PDF poster and its three reusable vector figures from checked-in evidence tables.

The page has no runtime dependencies, backend, secrets, or absolute asset paths. All links are relative so it works under a repository subpath on GitHub Pages.

## Regenerate the poster

The generation-only script needs Python 3.10+ and ReportLab; the browser site itself still has no dependencies. ReportLab produces the editable SVG and the print-sized vector PDF from one drawing source.

```bash
python scripts/build_research_assets.py
```

The poster is A0 portrait (841 x 1189 mm). To regenerate its 150 dpi PNG preview with Poppler:

```bash
pdftoppm -f 1 -singlefile -r 150 -png \
  assets/figures/recovery-paths-poster.pdf \
  assets/figures/recovery-paths-poster
```

## Local preview

From the repository root:

```bash
python3 -m http.server 4173
```

Then open <http://127.0.0.1:4173/>. Fetching the CSV/JSON evidence requires HTTP; opening `index.html` directly with `file://` will show the graceful fallback.

## Deployment

`.github/workflows/pages.yml` publishes this repository when `main` is updated, or when manually dispatched. In the GitHub repository settings, choose **GitHub Actions** as the Pages source.

The workflow does not establish the canonical URL until it successfully deploys in the destination repository. No commit, push, Pages settings change, or deployment was performed during local construction.

## Final QR assets

Do not generate QR assets until the successfully deployed HTTPS URL is canonical. The standard library does not implement QR error correction or decoding, so the offline helper uses dedicated open-source tooling:

```bash
python -m pip install 'qrcode[pil]' opencv-python
python scripts/generate_qr.py 'https://OWNER.github.io/REPOSITORY/' --output assets/qr
```

The script rejects placeholders and local URLs, creates SVG and high-resolution PNG output with a four-module quiet zone, creates a labelled poster SVG, and decodes the PNG to verify the exact payload.

## Updating scientific data

- Preserve the distinction between the seed-42 representation analysis and the five-seed accuracy control.
- Never imply confidence intervals from the displayed individual seeds.
- Keep Q/K/V-only random controls separate from the main Q/K/V+dense lesion.
- Keep the readout-only encoder representation fixed in every visual.
- Never animate a permanently lesioned component returning to service.
- Update `SOURCE_MANIFEST.md` and checksums whenever a source or public value changes.

## Current publication limits

The supplied manuscript is anonymous and is not distributed by this site. The site links to the official acceptance/program page until a final public proceedings PDF is verifiable. Affiliations, DOI, public code URL, canonical site URL, and final QR assets remain intentionally pending.

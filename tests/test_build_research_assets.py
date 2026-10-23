"""Regression checks for the empirical readout-remapping poster panel."""

import csv
import importlib.util
import unittest
from collections import Counter
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SITE_ROOT / "scripts" / "build_research_assets.py"
SPEC = importlib.util.spec_from_file_location("build_research_assets", SCRIPT_PATH)
assert SPEC and SPEC.loader
ASSETS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSETS)


class ReadoutRemappingTest(unittest.TestCase):
    """Protect the sample composition, outcomes, and shared projection extent."""

    def test_empirical_panel_contract(self) -> None:
        """The balanced sample and full-range bounds must match the audited export."""
        data_path = SITE_ROOT / "assets" / "data" / "readout-empirical.csv"
        with data_path.open(newline="") as stream:
            rows = list(csv.DictReader(stream))

        self.assertEqual(len(rows), 816)
        self.assertEqual(set(Counter(row["gold_pos"] for row in rows).values()), {48})
        self.assertEqual(sum(int(row["original_correct"]) for row in rows), 49)
        self.assertEqual(sum(int(row["remapped_correct"]) for row in rows), 521)

        xs = [float(row["pc1"]) for row in rows]
        ys = [float(row["pc2"]) for row in rows]
        xmin, xmax, ymin, ymax = ASSETS.bounds(rows)
        self.assertLess(xmin, min(xs))
        self.assertGreater(xmax, max(xs))
        self.assertLess(ymin, min(ys))
        self.assertGreater(ymax, max(ys))


class PosterSectionTest(unittest.TestCase):
    """Protect the public poster section and its downloadable assets."""

    def test_poster_section_links_existing_outputs(self) -> None:
        """The page must expose the print, editable, and portable poster versions."""
        html = (SITE_ROOT / "index.html").read_text()
        self.assertIn('id="poster"', html)
        for filename in (
            "recovery-paths-poster.pdf",
            "recovery-paths-poster.svg",
            "recovery-paths-poster-outlined.svg",
        ):
            self.assertIn(filename, html)
            self.assertTrue((SITE_ROOT / "assets" / "figures" / filename).is_file())


if __name__ == "__main__":
    unittest.main()

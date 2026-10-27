"""Regression checks for the empirical readout-remapping poster panel."""

import csv
import importlib.util
import json
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

        metadata = json.loads((SITE_ROOT / "assets" / "data" / "representation-states.json").read_text())["meta"]
        self.assertAlmostEqual(metadata["pc1_variance"], 14.5006)
        self.assertAlmostEqual(metadata["pc2_variance"], 8.8197)

        xs = [float(row["pc1"]) for row in rows]
        ys = [float(row["pc2"]) for row in rows]
        xmin, xmax, ymin, ymax = ASSETS.bounds(rows)
        self.assertLess(xmin, min(xs))
        self.assertGreater(xmax, max(xs))
        self.assertLess(ymin, min(ys))
        self.assertGreater(ymax, max(ys))

    def test_geometry_draft_uses_verified_endpoint_metrics(self) -> None:
        """The alternate poster must use the audited primary-run RDM endpoints."""
        site, rows = ASSETS.load_data()
        expected = {
            "damage": (0.325838, 1.0),
            "readout_only": (0.325838, 0.539025),
            "mask_only_inverse_reg": (0.642498, 1.0),
            "readout_and_mask_reg": (0.528725, 0.689791),
            "encoder_only": (0.506665, 1.0),
        }
        for key, values in expected.items():
            condition = site["conditions"][key]
            self.assertEqual((condition["pos_centroid"], condition["head_rdm"]), values)
        drawing = ASSETS.poster(site, rows, geometry_draft=True)
        self.assertEqual((drawing.width, drawing.height), (ASSETS.W, ASSETS.H))
        poster_text = " ".join(getattr(item, "text", "") for item in drawing.getContents())
        self.assertIn("Spearman similarity of POS-centroid RDM", poster_text)
        for label in ("Damaged | 16.82%", "Readout only | 80.00%", "Gates + readout | 85.87%", "Core | 94.98%"):
            self.assertIn(label, poster_text)

    def test_recovery_plot_uses_observed_five_run_ranges(self) -> None:
        """The performance plot must summarize the five recorded runs without inferred intervals."""
        site, _ = ASSETS.load_data()
        expected = {
            "core": (94.965602, 95.092854),
            "encoder_only": (91.839981, 92.424544),
            "readout_and_mask_reg": (85.656341, 85.994353),
            "readout_only": (77.070824, 80.001591),
            "mask_only_inverse_reg": (64.182606, 73.611166),
            "damage": (9.321191, 17.119338),
        }
        for key, observed_range in expected.items():
            values = site["seeds"][key]
            self.assertEqual(len(values), 5)
            self.assertEqual((min(values), max(values)), observed_range)

    def test_gate_state_fractions_are_complete_primary_run_endpoints(self) -> None:
        """Active, inactive, and intermediate gates must partition each condition."""
        site, rows = ASSETS.load_data()
        for condition in site["conditions"].values():
            total = sum(condition[name] for name in ("active_gates", "inactive_gates", "intermediate_gates"))
            self.assertAlmostEqual(total, 100.0, places=5)
        drawing = ASSETS.poster(site, rows, gate_state_version=True)
        self.assertEqual((drawing.width, drawing.height), (ASSETS.W, ASSETS.H))
        text_items = [getattr(item, "text", "") for item in drawing.getContents()]
        poster_text = " ".join(text_items)
        self.assertIn("adapting the surviving projection-specific gates", poster_text)
        self.assertNotIn("reselecting", poster_text)
        self.assertIn("Performance vs. encoder geometry", poster_text)
        self.assertIn("Linear CKA compares each condition's final hidden states with the pre-lesion core.", poster_text)
        self.assertIn("Recovery can use internal rerouting or readout retraining; among fixed-weight routes, combining both recovers most without necessarily restoring the original representation.", poster_text)
        self.assertIn("Encoder and readout geometry change differently across recovery paths", poster_text)
        self.assertNotIn("Performance recovers through gate rerouting", poster_text)
        self.assertNotIn("Recovery paths produce different encoder and readout geometries", poster_text)
        self.assertIn("Readout-only recovery", poster_text)
        self.assertIn("Core-fitted PC1-PC2 view of 816 POS-balanced token states; predictions use 768D states", poster_text)
        self.assertNotIn("PC1", text_items)
        self.assertNotIn("PC2", text_items)
        self.assertIn("Circles are individual runs; squares are means.", poster_text)
        self.assertIn("Lesioned entries are held at -12 and cannot change during recovery.", poster_text)
        self.assertNotIn("Circles show individual runs; squares show their means.", poster_text)
        self.assertIn("Each token stays at the same PC1-PC2 coordinate", poster_text)
        self.assertNotIn("PC1 and PC2 explain 23.32%", poster_text)
        self.assertNotIn("The lesion stays fixed throughout recovery", poster_text)
        self.assertIn("Q/K/V only: the targeted 74-group lesion", poster_text)
        self.assertIn("same Q/K/V and dense counts chosen at random", poster_text)
        self.assertIn("Performance can recover without relearning the underlying transformations.", poster_text)
        self.assertIn("Our evaluations were based on a single task and a single backbone model.", poster_text)
        self.assertNotIn("Matched controls give different answers", poster_text)
        self.assertNotIn("Arrows compare endpoints only", poster_text)
        editorial = ASSETS.poster(site, rows, gate_state_version=True, editorial_style=True)
        self.assertEqual((editorial.width, editorial.height), (ASSETS.W, ASSETS.H))

    def test_readout_evidence_variant_keeps_distinct_measured_evidence(self) -> None:
        """The variant must retain the PCA, geometry, and per-tag views without a duplicate table."""
        site, rows = ASSETS.load_data()
        drawing = ASSETS.poster(site, rows, gate_state_version=True, readout_evidence_variant=True)
        poster_text = " ".join(getattr(item, "text", "") for item in drawing.getContents())
        for label in (
            "Readout-only recovery",
            "Core-fitted PC1-PC2 view of the same 816 POS-balanced token states; classification uses all 768 dimensions",
            "Damaged + original readout",
            "49 / 816 correct | 16.82% full dev",
            "Same encoder + retrained readout",
            "521 / 816 correct | 80.00% full dev",
            "POS-centroid geometry vs. readout-weight geometry",
            "Recovery extends across POS classes",
            "Core (pre-lesion)",
            "recall within each gold POS class (%)",
        ):
            self.assertIn(label, poster_text)
        self.assertNotIn("PC1 (14.50% of core variance)", poster_text)
        self.assertNotIn("PC2 (8.82%)", poster_text)
        self.assertNotIn("Fixed points, changed predictions", poster_text)
        self.assertNotIn("What actually changed?", poster_text)
        self.assertNotIn("Readout retraining improves nearly every class", poster_text)
        per_tag = ASSETS.load_per_tag_data()
        self.assertEqual(len(per_tag), 119)
        damaged_noun = next(row for row in per_tag if row["condition"] == "Damaged" and row["tag"] == "NOUN")
        self.assertAlmostEqual(float(damaged_noun["accuracy_percent"]), 98.384798)
        self.assertAlmostEqual(float(damaged_noun["core_accuracy_percent"]), 93.681710)
        for row in per_tag:
            self.assertGreaterEqual(float(row["accuracy_percent"]), 0.0)
            self.assertLessEqual(float(row["accuracy_percent"]), 100.0)


class PosterSectionTest(unittest.TestCase):
    """Protect the public poster section and its downloadable assets."""

    def test_poster_section_links_existing_outputs(self) -> None:
        """The page must expose the print, editable, and portable poster versions."""
        html = (SITE_ROOT / "index.html").read_text()
        self.assertIn('id="poster"', html)
        for filename in (
            "recovery-paths-poster-gate-state.pdf",
            "recovery-paths-poster-gate-state.svg",
            "recovery-paths-poster-gate-state-outlined.svg",
            "recovery-paths-poster.pdf",
            "recovery-paths-poster.svg",
            "recovery-paths-poster-outlined.svg",
            "recovery-paths-poster-readout-evidence.pdf",
            "recovery-paths-poster-readout-evidence.svg",
            "recovery-paths-poster-readout-evidence-outlined.svg",
        ):
            self.assertIn(filename, html)
            self.assertTrue((SITE_ROOT / "assets" / "figures" / filename).is_file())
        self.assertIn("https://mechint25.github.io/", html)
        for filename in ("experiment-qr.svg", "experiment-qr.png", "explore-the-experiment.svg"):
            self.assertIn(filename, html)
            self.assertTrue((SITE_ROOT / "assets" / "qr" / filename).is_file())


if __name__ == "__main__":
    unittest.main()

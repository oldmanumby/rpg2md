import argparse
import html
import json
import shutil
import tempfile
import unittest
from pathlib import Path

# Import functions to test from rpg2md
import rpg2md


class TestRPG2MDHelpers(unittest.TestCase):

    def test_slugify(self):
        # Basic text
        self.assertEqual(rpg2md.slugify("Combat Rules"), "combat_rules")
        # Punctuation and special characters
        self.assertEqual(rpg2md.slugify("Chapter 1: The Dragon's Lair!"), "chapter_1_the_dragons_lair")
        # HTML entities
        self.assertEqual(rpg2md.slugify("D&amp;D 5th Edition"), "dd_5th_edition")
        # Spaced out capital letters on fantasy covers
        self.assertEqual(rpg2md.slugify("B A L D U R ' S  G A T E"), "baldurs_gate")
        self.assertEqual(rpg2md.slugify("D E S C E N T   I N T O   A V E R N U S"), "descent_into_avernus")
        # Preserving existing valid snake_case names
        self.assertEqual(rpg2md.slugify("test_preset"), "test_preset")
        # Empty or symbol-only strings fallback
        self.assertEqual(rpg2md.slugify("!@#$%"), "section")
        # Truncation
        long_title = "This Is A Very Long Chapter Title That Exceeds The Maximum Length Allowed"
        self.assertTrue(len(rpg2md.slugify(long_title, max_length=20)) <= 20)

    def test_parse_page_range(self):
        # Valid single page
        self.assertEqual(rpg2md.parse_page_range("5"), (5, 5))
        # Valid page range
        self.assertEqual(rpg2md.parse_page_range("1-10"), (1, 10))
        self.assertEqual(rpg2md.parse_page_range("10-25"), (10, 25))
        # Inverted range auto-correction
        self.assertEqual(rpg2md.parse_page_range("20-10"), (20, 20))
        # All pages
        self.assertEqual(rpg2md.parse_page_range("all"), (1, 9223372036854775807))
        self.assertEqual(rpg2md.parse_page_range(""), (1, 9223372036854775807))
        self.assertEqual(rpg2md.parse_page_range(None), (1, 9223372036854775807))

        # Invalid page range formats should raise ValueError
        with self.assertRaises(ValueError):
            rpg2md.parse_page_range("10-")
        with self.assertRaises(ValueError):
            rpg2md.parse_page_range("-10")
        with self.assertRaises(ValueError):
            rpg2md.parse_page_range("abc")
        with self.assertRaises(ValueError):
            rpg2md.parse_page_range("1-2-3")

    def test_preset_save_and_load(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            class DummyArgs:
                pipeline = "modular"
                scale = 3.0
                no_images = False
                naming_scheme = "heading"
                custom_prefix = "rpg"
                vlm = "smolvlm"
                vlm_url = "http://127.0.0.1:8888/v1"
                vlm_model = "test-model"
                vlm_words = 5
                ocr = "apple"
                ocr_scale = 3.0
                force_ocr = False
                table_mode = "accurate"
                table_images = False
                no_headings = False
                device = "auto"
                threads = 8

            args = DummyArgs()
            saved_file = rpg2md.save_preset(
                name="test_preset",
                args=args,
                presets_dir=temp_dir,
                description="Test preset description"
            )

            self.assertTrue(saved_file.exists())
            data = json.loads(saved_file.read_text(encoding="utf-8"))
            self.assertEqual(data["name"], "test_preset")
            self.assertEqual(data["description"], "Test preset description")
            self.assertEqual(data["ocr"], "apple")

            # Test loading into a blank Namespace
            target_ns = argparse.Namespace()
            loaded_args = rpg2md.load_preset_file(saved_file, target_ns)
            self.assertEqual(getattr(loaded_args, "ocr", None), "apple")
            self.assertEqual(getattr(loaded_args, "naming_scheme", None), "heading")
            self.assertEqual(getattr(loaded_args, "scale", None), 3.0)
        finally:
            shutil.rmtree(temp_dir)

    def test_cli_preset_preloading(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            preset_file = temp_dir / "custom_test.json"
            preset_file.write_text(json.dumps({
                "name": "custom_test",
                "naming_scheme": "heading",
                "scale": 2.5,
                "pipeline": "granite",
                "vlm": "none"
            }), encoding="utf-8")

            # Simulate main() CLI preloading into an empty Namespace
            temp_ns = argparse.Namespace()
            temp_ns = rpg2md.load_preset_file(preset_file, temp_ns)

            self.assertEqual(getattr(temp_ns, "naming_scheme", None), "heading")
            self.assertEqual(getattr(temp_ns, "scale", None), 2.5)
            self.assertEqual(getattr(temp_ns, "pipeline", None), "granite")
            self.assertEqual(getattr(temp_ns, "vlm", None), "none")

            # Verify parser.set_defaults behaves as expected
            parser = argparse.ArgumentParser()
            parser.add_argument("--naming-scheme", default="sequential")
            parser.add_argument("--scale", type=float, default=3.0)
            parser.add_argument("--pipeline", default="modular")
            parser.set_defaults(**vars(temp_ns))

            parsed = parser.parse_args([])
            self.assertEqual(parsed.naming_scheme, "heading")
            self.assertEqual(parsed.scale, 2.5)
            self.assertEqual(parsed.pipeline, "granite")
        finally:
            shutil.rmtree(temp_dir)

    def test_postprocess_assets_and_links(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            doc_dir = temp_dir / "TestBook"
            doc_dir.mkdir(parents=True, exist_ok=True)
            target_assets = doc_dir / "_assets"
            raw_assets = temp_dir / "_raw_assets"
            raw_assets.mkdir(parents=True, exist_ok=True)

            # Create dummy images
            (raw_assets / "raw_img_1.png").write_bytes(b"dummy1")
            (raw_assets / "raw_img_2.png").write_bytes(b"dummy2")

            # Create markdown with headings and references
            md_path = doc_dir / "TestBook.md"
            md_content = """# Combat Rules
Here is an image:
![Combat map](raw_img_1.png)

## Monster Lore
Here is another image:
![Dragon portrait](raw_img_2.png)
"""
            md_path.write_text(md_content, encoding="utf-8")

            # Run post-processing with heading-based naming
            count = rpg2md.postprocess_assets_and_links(
                md_path=md_path,
                raw_assets_dir=raw_assets,
                target_assets_dir=target_assets,
                naming_scheme="heading",
                custom_prefix="img",
                vlm_mode="none",
                vlm_url="http://127.0.0.1:8888/v1",
                vlm_model="test",
                vlm_words=5
            )

            self.assertEqual(count, 2)
            self.assertTrue((target_assets / "combat_rules_001.png").exists())
            self.assertTrue((target_assets / "monster_lore_001.png").exists())

            # Verify markdown links were rewritten
            updated_md = md_path.read_text(encoding="utf-8")
            self.assertIn("![Combat map](_assets/combat_rules_001.png)", updated_md)
            self.assertIn("![Dragon portrait](_assets/monster_lore_001.png)", updated_md)
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()

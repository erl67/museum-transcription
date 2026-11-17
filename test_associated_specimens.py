from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts import find_associated_specimens as search


def block(labels, slip, body, status="OK"):
    banners = "".join(f"{'=' * 22}{label}{'=' * 8}\n" for label in labels)
    return f"{banners}ID: {slip}\nSTATUS: {status}\n{'=' * 50}\n{body}\n\n\n"


class SpecimenSearchTest(unittest.TestCase):
    def test_only_collecting_context_and_supported_shorthand(self):
        text = """Means of Identification: BIRDS PRESENT: ALSO EGGS & NEST
Identified by the eggs and bird.
Nest made of strips of bark. Eggs collected on May 9.
Eggs taken from the nest.
The nest was not collected.
Identification: shot ♂
Remarks: Nest 10 ft high in a willow. collected with the eggs.
nest & 5
Eggs and bird S1234
Set Mark: S1999
Pencil note at right: S0123
TRANSCRIPTION NOTES:
Guess that nest was collected.
BACK OF SLIP:
ANNOTATIONS: Skin collected; reference ♂ No. 7587
Nest taken?
The eggs and
nest were taken together.
Nest collected - back of slip: "Nest Saved"
Nest collected - back of slip: "Its dimensions were 100 mm."
Skin collected - Identification: "Skin 1351, ♀ ad."
"""
        rows = list(search.read_evidence(text, 10))
        self.assertEqual([(row[0], row[1], row[2], row[4]) for row in rows], [
            ("Bird", "Needs review", "", 15),
            ("Nest", "Collection wording", "", 16),
            ("Nest", "Specimen list", "", 17),
            ("Bird", "Specimen list", "S1234", 18),
            ("Possible specimen", "Identifier only", "S0123", 20),
            ("Nest", "Quoted annotation", "", 28),
            ("Skin", "Quoted annotation", "1351", 30),
        ])
        self.assertEqual(list(search.classify("Identification: Skin 1351, ♀ ad.", False)),
                         [("Skin", "Specimen reference", "1351")])
        self.assertEqual(list(search.classify("Nest No.: 133-1/11", False)),
                         [("Nest", "Specimen reference", "133-1/11")])
        self.assertEqual(list(search.classify('Nest No.: Back 48"', False)), [])
        self.assertEqual(list(search.classify("Measurements of nest & eggs on other side", False)), [])
        self.assertEqual(list(search.classify("The nest and the eggs are considerably larger", False)), [])
        self.assertEqual(list(search.classify("After the present set was taken the birds built again.", False)), [])
        self.assertEqual(list(search.classify("The eggs were collected the nest remained.", False)), [])
        self.assertEqual(list(search.classify("I collected a nest and five eggs.", False)),
                         [("Nest", "Collection wording", "")])

    def test_observation_and_position_on_slip_do_not_support_collection(self):
        text = """BACK OF SLIP:
A nest with 2 eggs on May 30 -
held 3 eggs on June 4 -
a nest with 3 eggs on June 2
held 3 new hatched yng on June 3
ANNOTATIONS:
Nest collected
Nest collected - back of slip: "A nest with 2 eggs on May 30"
Number above Bird: 7020"""
        self.assertEqual(list(search.read_evidence(text, 1)), [])

    def test_archive_keeps_historical_evidence_and_shared_and_uncatalogued_slips(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            family = root / "Icteridae"
            family.mkdir()
            old = family / "Bird_one_transcriptions_20261020_0930.txt"
            newer = family / "Bird_one_transcriptions_20261101_0930.txt"
            shared = ["CM007", "CM15"]
            old.write_text(
                block(shared, "Bird_one_E007_E15", "Eggs + nest")
                + block(["CM18"], "Bird_one_E18", "Bird taken")
                + block(["CM19"], "Bird_one_E19", "Skin collected", status="FAILED")
                + "======================CM20 (MISSING)=======\nRemarks: Skin collected\n\n\n"
                + block(["Slip(A).jpg", "Slip(B).jpg"], "Slip", "Eggs and bird")
                + "TOKENS: 0\nAVERAGE/CALL: 0\nRUN: 0 calls\n", encoding="utf-8-sig",
            )
            newer.write_text(
                block(shared, "Bird_one_E007_E15", "Eggs + nest", status="OK (reused)")
                + block(["CM18"], "Bird_one_E18", "Only eggs")
                + block(["CM21"], "Bird_one_E21", "Nest taken").rstrip(), encoding="utf-8",
            )
            rows, cards, reports = search.scan(root)
            self.assertEqual((cards, reports), (3, 2))
            self.assertEqual({row.evidence for row in rows}, {"Eggs + nest", "Bird taken", "Eggs and bird"})
            self.assertEqual([(row.enums, row.report, row.line) for row in rows if row.specimen == "Nest"],
                             [("E007, E15", newer, 6)])
            self.assertEqual([(row.enums, row.report) for row in rows if row.evidence == "Bird taken"],
                             [("E18", old)])

    def test_excel_stores_source_as_text_and_protects_previous_review(self):
        try:
            from openpyxl import load_workbook
        except ImportError:
            self.skipTest("optional openpyxl exporter unavailable")
        with TemporaryDirectory() as temp:
            file = Path(temp) / "specimens.xlsx"
            report = Path(temp) / "Bird_one_transcriptions_20261020_0930.txt"
            row = search.Candidate("Icteridae", "E007, E010", "Bird_one_E007", "Nest",
                                   "Specimen list", "S0012", "=Eggs + nest", report, 5)
            bird = search.Candidate("Icteridae", "E008", "Bird_one_E008", "Bird",
                                    "Collection wording", "", "Bird taken", report, 15)
            skin = search.Candidate("Icteridae", "E009", "Bird_one_E009", "Skin",
                                    "Specimen reference", "S0123", "Skin No. S0123", report, 25)
            unnumbered = search.Candidate("Icteridae", "", "Bird_one_uncatalogued", "Bird",
                                           "Collection wording", "", "Bird taken", report, 35)
            search.write_workbook(file, [row, bird, skin, unnumbered])
            book = load_workbook(file)
            self.assertEqual(book.sheetnames, ["Nests", "Birds and Skins"])
            self.assertEqual(book["Nests"]["A2"].value, "E007, E010")
            self.assertEqual(book["Nests"]["A2"].hyperlink.target, "https://ericlaslo.com/eggs/E007")
            self.assertEqual(book["Nests"]["E2"].value, "S0012")
            self.assertEqual(book["Nests"]["D2"].data_type, "s")
            self.assertEqual(book["Nests"]["D2"].value, "=Eggs + nest")
            self.assertEqual(book["Nests"]["H2"].value, report.name)
            self.assertIsNone(book["Nests"]["H2"].hyperlink)
            self.assertEqual(book["Nests"]["I2"].value, 5)
            self.assertEqual(book["Nests"].max_row, 2)
            self.assertEqual(book["Birds and Skins"]["B2"].value, "Bird")
            self.assertEqual(book["Birds and Skins"]["B3"].value, "Skin")
            self.assertEqual(book["Birds and Skins"]["E3"].value, "S0123")
            self.assertEqual(book["Birds and Skins"]["A2"].hyperlink.target, "https://ericlaslo.com/eggs/E008")
            self.assertEqual(book["Birds and Skins"]["A3"].hyperlink.target, "https://ericlaslo.com/eggs/E009")
            self.assertIsNone(book["Birds and Skins"]["A4"].hyperlink)
            self.assertEqual(book["Birds and Skins"].auto_filter.ref, "A1:J4")
            book.close()
            with self.assertRaises(FileExistsError):
                search.write_workbook(file, [])


if __name__ == "__main__":
    unittest.main()

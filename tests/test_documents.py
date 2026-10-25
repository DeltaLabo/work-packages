from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from pypdf import PdfReader

from scripts.generate_work_packages import load_row
from scripts.data import FIELDS, write_csv
from scripts.pdf import work_package_pdf
from test_store import ROW


class DocumentTests(unittest.TestCase):
    def test_pdf_keeps_labels_ids_accents_and_literal_markup(self):
        row=ROW|{"title":"Diseño & control <test>","professor":"Álex Example"}
        result=work_package_pdf(row)
        reader=PdfReader(BytesIO(result))
        text="\n".join(page.extract_text() for page in reader.pages)
        for value in ("012026","Diseño & control <test>","Álex Example","Objectives","Deliverables","Example terms"):
            self.assertIn(value,text)
        self.assertEqual(len(reader.pages),1)

    def test_long_package_paginates_without_losing_items_or_metadata(self):
        tasks=";".join(f"Task {i:03d}: "+"Complete the specified activity and document the outcome. "*3 for i in range(90))
        row=ROW|{"tasks":tasks,"description":"An extended package with complete deliverables."}
        reader=PdfReader(BytesIO(work_package_pdf(row)))
        text="\n".join(page.extract_text() for page in reader.pages)
        self.assertGreater(len(reader.pages),1)
        self.assertIn("Task 089",text)
        self.assertIn("Example professor",text)
        for page in reader.pages:
            self.assertIn("DeltaLAB: work packages",page.extract_text())

    def test_existing_cli_loads_selected_padded_id_without_rewriting_source(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"source.csv"
            content=write_csv(FIELDS,[ROW,ROW|{"id":"022026","title":"Other"}])
            path.write_text(content,encoding="utf-8")
            self.assertEqual(load_row(path,"012026")["title"],ROW["title"])
            self.assertEqual(path.read_text(encoding="utf-8"),content)

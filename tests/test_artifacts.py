"""The PDF gate must inspect the final bytes and reject active/external input."""
from pathlib import Path
import tempfile
import unittest

try:
    from proposition_runtime import artifacts
except ImportError:
    artifacts = None


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def module(self):
        self.assertIsNotNone(artifacts, "Artifact pipeline is not implemented")
        return artifacts

    def source(self, content):
        p = self.root / "source.html"
        p.write_text(content)
        return p

    def test_active_content_is_rejected_before_export(self):
        source = self.source('<html><body><script>fetch("https://invalid.example/")</script>Title</body></html>')
        with self.assertRaisesRegex(ValueError, "active"):
            self.module().export_pdf(source, self.root / "client.pdf", audience="client")
        self.assertFalse((self.root / "client.pdf").exists())

    def test_external_and_escaping_assets_are_rejected(self):
        for ref in ("https://invalid.example/picture.png", "../private.png"):
            with self.subTest(ref=ref):
                source = self.source(f'<html><body><img src="{ref}"></body></html>')
                with self.assertRaises(ValueError):
                    self.module().export_pdf(source, self.root / "client.pdf", audience="client")

    def test_export_renders_every_pdf_page_and_extracts_real_words(self):
        source = self.source('''<!doctype html><html><head><meta charset="UTF-8"><style>
        @page {size:A4 landscape;margin:15mm} section {break-after:page} section:last-child {break-after:auto}
        </style></head><body><section><h1>Maison Boreale</h1><p>Une nouvelle proposition.</p></section>
        <section><h1>Une visite qui inspire</h1><p>Decouvrir les projets et demander un rendez-vous.</p></section></body></html>''')
        result = self.module().export_pdf(source, self.root / "client.pdf", audience="client")
        self.assertEqual(result["page_count"], 2)
        report = self.module().inspect_pdf(self.root / "client.pdf", self.root / "inspection", audience="client")
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(report["pages"]), 2)
        self.assertIn("Maison Boreale", report["text"])
        self.assertTrue(all((self.root / "inspection" / p["image"]).exists() for p in report["pages"]))

    def test_six_client_pages_fail_even_when_pdf_opens(self):
        from pypdf import PdfWriter
        pdf = self.root / "six.pdf"
        writer = PdfWriter()
        for _ in range(6):
            writer.add_blank_page(width=400, height=300)
        with pdf.open("wb") as stream:
            writer.write(stream)
        report = self.module().inspect_pdf(pdf, self.root / "inspection", audience="client")
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("client_page_limit", [i["code"] for i in report["issues"]])
        self.assertEqual(len(report["pages"]), 6)

    def test_archive_cannot_include_an_internal_sales_file(self):
        client = self.root / "client"
        client.mkdir()
        (client / "brief.txt").write_text("Public proposal")
        internal = self.root / "sales.txt"
        internal.write_text("PRIVATE_SENTINEL")
        with self.assertRaises(ValueError):
            self.module().package_client(client, self.root / "client.zip", ["brief.txt", "../sales.txt"])
        self.assertFalse((self.root / "client.zip").exists())

    def test_page_and_annotation_actions_are_not_mistaken_for_a_passive_pdf(self):
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, TextStringObject, ArrayObject, FloatObject
        source = self.source('<html><body><h1>Document visible</h1><p>Texte de fixture.</p></body></html>')
        self.module().export_pdf(source, self.root/'plain.pdf')
        writer = PdfWriter(clone_from=PdfReader(self.root/'plain.pdf'))
        action = DictionaryObject({NameObject('/S'):NameObject('/JavaScript'), NameObject('/JS'):TextStringObject('app.alert(1)')})
        writer.pages[0][NameObject('/AA')] = DictionaryObject({NameObject('/O'):action})
        annotation = DictionaryObject({NameObject('/Type'):NameObject('/Annot'),NameObject('/Subtype'):NameObject('/Link'),
            NameObject('/Rect'):ArrayObject([FloatObject(0),FloatObject(0),FloatObject(10),FloatObject(10)]),NameObject('/A'):action})
        writer.pages[0][NameObject('/Annots')] = ArrayObject([writer._add_object(annotation)])
        writer.write(self.root/'active.pdf')
        report = self.module().inspect_pdf(self.root/'active.pdf',self.root/'inspection')
        self.assertEqual(report['status'],'FAIL')
        self.assertIn('active_pdf',[i['code'] for i in report['issues']])


if __name__ == "__main__":
    unittest.main()

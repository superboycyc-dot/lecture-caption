import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextCursor
from math_render import protect_math, MATH_SOURCE
from notes_editor import markdown_document, rich_markdown, export_pdf


class MathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_display_inline_and_dollars_roundtrip_after_edit(self):
        expressions = [r"\[ x=\frac{1}{\sqrt{2}} \]", r"\(E=mc^2\)", r"$\sum_{i=1}^n i$", r"$$\int_0^1 x\,dx$$"]
        source = "\n\n".join(expressions)
        document = markdown_document(source)
        cursor = QTextCursor(document)
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(" edited")
        restored = rich_markdown(document)
        for expression in expressions:
            self.assertIn(expression, restored)
        self.assertIn("edited", restored)
        self.assertNotIn("lecture-math:", restored)
        self.assertNotIn("LCMATH", restored)

    def test_code_examples_are_not_math(self):
        source = "```latex\n\\[x^2\\]\n```\n\n`$x$`\n\n    \\[code\\]\n"
        protected, expressions = protect_math(source)
        self.assertEqual(protected, source)
        self.assertEqual(expressions, {})

    def test_unsupported_tex_is_preserved_not_dropped(self):
        source = r"\[ \unknowncommand{x} \]"
        document = markdown_document(source)
        self.assertIn(source, rich_markdown(document))

    def test_pdf_contains_rendered_formula_image(self):
        source = "# Test\n\n" + r"\[\frac{a}{b}=\sqrt{x}\]"
        document = markdown_document(source)
        image = False
        block = document.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                form = it.fragment().charFormat()
                image |= form.isImageFormat() and bool(form.property(MATH_SOURCE))
                it += 1
            block = block.next()
        self.assertTrue(image)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "math.pdf"
            export_pdf(source, path)
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))

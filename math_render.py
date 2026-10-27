"""Offline math images retaining original LaTeX for lossless Markdown editing."""

import base64
import hashlib
import io
import re
from functools import lru_cache
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextCursor, QTextDocument, QTextImageFormat

MATH_SOURCE = 0x100051
# Code is consumed before math so examples remain literal.
TOKENS = re.compile(
    r"(?P<code>^\s*```[^\n]*\n.*?^\s*```[^\n]*$|^\s*~~~[^\n]*\n.*?^\s*~~~[^\n]*$|`+[^`\n]*`+|^(?: {4}|\t)[^\n]*)"
    r"|(?P<math>\\\[.*?\\\]|\\\(.*?\\\)|(?<![\\$])\$\$.*?(?<!\\)\$\$|(?<![\\$])\$(?!\$)[^\n$]+?(?<!\\)\$(?!\$))",
    re.MULTILINE | re.DOTALL,
)


def protect_math(source):
    expressions = {}

    def replace(match):
        if match.group("code"):
            return match.group()
        original = match.group()
        token = "LCMATH" + hashlib.sha256(original.encode()).hexdigest() + "END"
        expressions[token] = original
        return token

    return TOKENS.sub(replace, source), expressions


@lru_cache(maxsize=256)
def math_png(original):
    from matplotlib.mathtext import math_to_image
    from matplotlib.font_manager import FontProperties

    expression = original[2:-2] if original.startswith((r"\[", r"\(", "$$")) else original[1:-1]
    expression = " ".join(expression.split())
    if len(expression) > 8000:
        return None
    buffer = io.BytesIO()
    try:
        math_to_image(
            "$" + expression + "$", buffer, prop=FontProperties(size=15), dpi=192, format="png", color="black"
        )
    except (ValueError, RuntimeError, TypeError):
        return None
    return buffer.getvalue()


def insert_math(cursor, original):
    data = math_png(original)
    if data is None:
        # Preserve unsupported TeX literally; never silently remove a formula.
        from PySide6.QtGui import QTextCharFormat

        form = QTextCharFormat()
        form.setProperty(MATH_SOURCE, original)
        form.setFontFixedPitch(True)
        cursor.insertText(original, form)
        return
    image = QImage.fromData(data)
    name = "lecture-math:" + base64.urlsafe_b64encode(original.encode()).decode()
    cursor.document().addResource(QTextDocument.ImageResource, QUrl(name), image)
    form = QTextImageFormat()
    form.setName(name)
    form.setProperty(MATH_SOURCE, original)
    form.setToolTip("双击编辑公式：" + original)
    width = min(image.width() / 2, 600)
    form.setWidth(width)
    form.setHeight(image.height() * width / image.width())
    cursor.insertImage(form)


def render_math(document, expressions):
    for token, original in expressions.items():
        cursor = document.find(token)
        while not cursor.isNull():
            insert_math(cursor, original)
            cursor = document.find(token)


def restore_math(document):
    """Replace math fragments in a clone with plain tokens before Qt serialization."""
    fragments = []
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid():
                original = fragment.charFormat().property(MATH_SOURCE)
                if original and (fragment.text() == "\ufffc" or fragment.text() == original):
                    fragments.append((fragment.position(), fragment.length(), original))
            iterator += 1
        block = block.next()
    replacements = {}
    from PySide6.QtGui import QTextCharFormat

    for index, (start, length, original) in enumerate(reversed(fragments)):
        token = "LCRESTOREMATH" + str(index) + "END"
        cursor = QTextCursor(document)
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.KeepAnchor)
        cursor.insertText(token, QTextCharFormat())
        replacements[token] = original
    return replacements

"""Original pages whose fixed-page reproduction is deferred to FR-027 Step 9.

At the 0.5 pt sizes of FR-023 (9.9 pt -> 10.0 pt) the rotated-table header
glyphs of p30-p35 cross the clearance of their fixed source row heights and the
fixture stops with "原本再現できず". The user chose (2026-10-20, option c) to
defer these pages until Step 9 rebuilds them on the swapped page grid, without
changing the clearance limit or the row heights. Tests that need these pages are
strict xfails, so Step 9 sees an XPASS when the pages lay out again; every other
page keeps running the same checks. Only tests import this module.
"""

import pytest

from gridlayoutpdf import LayoutOverflowError


ALL_PAGES = tuple(range(1, 38))
DEFERRED_PAGES = tuple(range(30, 36))
AVAILABLE_PAGES = tuple(number for number in ALL_PAGES if number not in DEFERRED_PAGES)
REASON = ("p30〜35 の回転表の見出し行は 10.0 pt で原本再現できず。"
          "FR-027 Step 9 で縦横入替のグリッドに作り直すまで保留（2026-10-20 ユーザー判断 c）")
DEFERRED = pytest.mark.xfail(strict=True, raises=LayoutOverflowError, reason=REASON)


DIFFERENCE_REASON = ("p36 の 1.0LR+1.23B の + の位置は 10.0 pt で原本から 0.600 pt ずれる（許容 0.25 pt）。"
                     "FR-027 Step 9 で位置の検査を新しい決まりどおりかの検査に置き換えるまで保留（2026-10-20）")
# Individual original-vs-output differences deferred to Step 9. verify_appearance
# counts a listed difference separately only when its page, id, category and
# detail match and its delta is at most max_delta_pt; any other difference still
# fails, and a listed difference that no longer occurs is itself a failure.
DEFERRED_DIFFERENCES = tuple(
    {"page": 36, "id": f"p36-combinations-summary.r{row}.c8", "category": "spacing",
     "detail": "operator inline origin", "max_delta_pt": .61, "reason": DIFFERENCE_REASON}
    for row in range(10, 19))


def available(pages):
    """Return ``pages`` without the deferred pages, keeping their order."""
    return tuple(number for number in pages if number not in DEFERRED_PAGES)


def selections(pages):
    """Parametrize ``pages`` without the deferred pages, and in full as a strict xfail."""
    pages = tuple(pages)
    kept = available(pages)
    if kept == pages:
        return [pytest.param(pages, id="pages")]
    params = [pytest.param(pages, marks=DEFERRED, id="with-deferred")]
    if kept:
        params.insert(0, pytest.param(kept, id="without-deferred"))
    return params

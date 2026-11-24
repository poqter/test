"""Read KB comparison columns by their positions, keeping the printed contract order."""

import re


def cell(words, left, right, top, bottom):
    return " ".join(
        w["text"] for w in words if left <= w["x0"] < right and top <= w["top"] < bottom
    )


def comparison(page, matrix):
    words = page.extract_words()
    slots = [
        w for w in words if 65 < w["top"] < 84 and re.fullmatch(r"\(\d+\)", w["text"])
    ]
    for anchor in words:
        if not (64 < anchor["x0"] < 68 and 165 < anchor["top"] < 798):
            continue
        y = anchor["top"]
        title = cell(words, 64, 153, y - 2, y + 5)
        total = cell(words, 153, 215, y - 2, y + 5)
        if not total or not slots:
            continue
        item = matrix.setdefault(title, {"total": total, "contracts": {}})
        for j, slot in enumerate(slots):
            item["contracts"][int(slot["text"][1:-1]) - 1] = cell(
                words, 215 + 88 * j, 303 + 88 * j, y - 2, y + 5
            )


def historic_contracts(page):
    words = page.extract_words()
    anchors = [
        w
        for w in words
        if 30 <= w["x0"] < 50 and w["top"] > 190 and w["text"].isdigit()
    ]
    return [
        [
            cell(words, a, b, w["top"] - 14, w["top"] + 15)
            for a, b in [
                (50, 90),
                (90, 155),
                (155, 326),
                (326, 385),
                (385, 425),
                (425, 463),
                (463, 505),
                (505, 575),
            ]
        ]
        for w in anchors
    ]


def comparison_targets(page):
    words = page.extract_words()
    result = {}
    for word in words:
        if 76 <= word["x0"] <= 80 and 80 < word["top"] < 800:
            y = word["top"]
            value = cell(words, 240, 323, y - 2, y + 4)
            if value:
                result[cell(words, 76, 225, y - 2, y + 4)] = value
    return result

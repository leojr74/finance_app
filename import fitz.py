import fitz

doc = fitz.open("itau.pdf")
page = doc[1]  # página 2

data = page.get_text("dict")
spans = []
for block in data.get("blocks", []):
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            texto = span["text"].strip()
            if not texto:
                continue
            spans.append({
                "text": texto,
                "x0": round(span["bbox"][0], 1),
                "top": round(span["bbox"][1], 1)
            })

for s in spans[20:60]:
    print(f"top={s['top']:7.1f} x0={s['x0']:6.1f} | {s['text']!r}")
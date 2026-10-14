"""Regenerates docs/architecture.png (needs matplotlib: pip install matplotlib)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BLUE, GREEN, ORANGE, RED, GREY, PURPLE = "#DCEBFA", "#DDF3E2", "#FFF0D1", "#FBDADA", "#ECECEC", "#E8DFF7"
EDGE = {BLUE: "#2F6DB5", GREEN: "#2E8B4F", ORANGE: "#C98A12", RED: "#C0392B", GREY: "#777777", PURPLE: "#6A4DB0"}

fig, ax = plt.subplots(figsize=(17, 9.5), dpi=150)
ax.set_xlim(0, 170); ax.set_ylim(0, 95); ax.axis("off")

def box(cx, cy, w, h, text, color, fs=10.5, bold=False):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.4,rounding_size=1.5",
                                fc=color, ec=EDGE[color], lw=1.8))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal")
    return cx, cy, w, h

def arrow(p, q, label=None, style="-", color="#333333", rad=0.0, lx=0, ly=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=16, lw=1.6, color=color,
                                 linestyle=style, connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text((p[0] + q[0]) / 2 + lx, (p[1] + q[1]) / 2 + ly, label, fontsize=9, ha="center",
                va="center", color=color, bbox=dict(fc="white", ec="none", pad=1.2))

# titles
ax.text(85, 91.5, "Document Q&A with Evidence - Architecture", ha="center", fontsize=17, fontweight="bold")
ax.text(3, 83, "1. INGESTION PIPELINE (run once, safe to re-run)", fontsize=12, fontweight="bold", color="#2F6DB5")
ax.text(3, 43, "2. QUESTION ANSWERING (every question)", fontsize=12, fontweight="bold", color="#2E8B4F")
ax.plot([2, 168], [41, 41], color="#BBBBBB", lw=1, ls="--")

# --- ingestion row (y=70)
y = 70
raw = box(17, y, 24, 14, "Raw files\ndata/raw\n(.txt, .md)", GREY, bold=True)
val = box(48, y, 25, 14, "Validate\nextension, UTF-8,\nnot empty", BLUE)
norm = box(79, y, 25, 14, "Normalise + SHA-256\nunchanged file\n-> skipped", BLUE)
chk = box(110, y, 24, 14, "Chunk\nparagraphs, ~500 chars\n50 overlap + offsets", BLUE)
db = box(146, y, 34, 18, "SQLite (curated store)\ndocuments | chunks\nchunks_fts (FTS5)", GREEN, bold=True)
for a, b in [(raw, val), (val, norm), (norm, chk), (chk, db)]:
    arrow((a[0] + a[2] / 2 + 0.6, y), (b[0] - b[2] / 2 - 0.6, y))
rej = box(48, 52, 25, 8, "ingestion_log\n(rejected + reason)", RED, fs=9.5)
arrow((48, y - 7.6), (48, 52 + 4.6), "invalid file", color="#C0392B", ly=0)
ax.text(79, 56, "one transaction per file\n(all-or-nothing)", ha="center", fontsize=9, color="#555555", style="italic")

# --- QA row (y=22)
y = 22
q = box(14, y, 20, 12, "User question\n(CLI: ask)", GREY, bold=True)
ret = box(40, y, 22, 14, "Retrieve\nFTS5 BM25\ntop candidates", ORANGE)
sc = box(66, y, 22, 14, "Evidence score\nkeyword coverage\n(0 to 1)", ORANGE)
gate = box(94, y, 24, 16, "Evidence gate\nscore >= 0.60 ?\nunknown entity ?", PURPLE, bold=True)
prov = box(126, y, 24, 16, "AnswerProvider\n(interface)\nextractive | Ollama", GREEN, bold=True)
ans = box(155, y + 9, 26, 12, "ANSWER\n+ source chunk\n(file, index, text)", GREEN, bold=True)
fb = box(126, 4, 24, 7, "fallback: extractive\nprovider answers", RED, fs=9)
no = box(94, 4, 26, 7, "INSUFFICIENT EVIDENCE", RED, fs=10, bold=True)
log = box(155, 4, 26, 7, "query_log\n(every question)", GREY, fs=9.5)

for a, b in [(q, ret), (ret, sc), (sc, gate), (gate, prov)]:
    arrow((a[0] + a[2] / 2 + 0.6, y), (b[0] - b[2] / 2 - 0.6, y))
ax.text(110, y + 3.2, "yes", fontsize=10, color="#2E8B4F", ha="center", fontweight="bold")
arrow((94, y - 8.6), (94, 4 + 3.9), "no", color="#C0392B", lx=-2)
arrow((prov[0] + 12.6, y + 2), (ans[0] - 13.6, y + 9), color="#2E8B4F")
arrow((126, y - 8.6), (126, 4 + 3.9), "provider error", color="#C0392B", lx=0, ly=0)
arrow((126 + 12.6, 4 + 2), (ans[0] - 6, y + 9 - 6.6), "answer", style="--", color="#2E8B4F", rad=0.25, lx=-3, ly=-2)
arrow((155 + 8, y + 9 - 6.6), (155 + 8, 4 + 3.9), style="--", color="#777777")
arrow((db[0], 70 - 9.6), (ret[0] + 4, y + 7.6), "chunks are searched", color="#2E8B4F", rad=-0.15, lx=18, ly=6)

fig.savefig("docs/architecture.png", bbox_inches="tight", facecolor="white")
print("saved")

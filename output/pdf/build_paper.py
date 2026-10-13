"""Build the formal manuscript from the measured research draft and saved figures."""
from pathlib import Path
import json
import re
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                               Table, TableStyle, Preformatted, Image, PageBreak,
                               NextPageTemplate, KeepTogether, CondPageBreak)
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "pdf"
OUT.mkdir(parents=True, exist_ok=True)
PDF = OUT / "SmartDistServe_Research_Paper.pdf"
pdfmetrics.registerFont(TTFont("Paper", "C:/Windows/Fonts/segoeui.ttf"))
pdfmetrics.registerFont(TTFont("PaperBold", "C:/Windows/Fonts/segoeuib.ttf"))
pdfmetrics.registerFontFamily("Paper", normal="Paper", bold="PaperBold", italic="Paper", boldItalic="PaperBold")
NAVY = colors.HexColor("#172B44")
BLUE = colors.HexColor("#166A87")
GRAY = colors.HexColor("#596575")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="PaperBody", fontName="Paper", fontSize=10,
                         leading=14, spaceAfter=7, textColor=NAVY))
styles.add(ParagraphStyle(name="PaperTitle", fontName="PaperBold", fontSize=19,
                         leading=24, spaceAfter=12, textColor=NAVY))
styles.add(ParagraphStyle(name="PaperH1", fontName="PaperBold", fontSize=13,
                         leading=17, spaceBefore=13, spaceAfter=7, keepWithNext=True, textColor=NAVY))
styles.add(ParagraphStyle(name="PaperH2", fontName="PaperBold", fontSize=10.5,
                         leading=14, spaceBefore=10, spaceAfter=5, keepWithNext=False, textColor=BLUE))
styles.add(ParagraphStyle(name="PaperTable", fontName="Paper", fontSize=7.5,
                         leading=10, textColor=NAVY))
styles.add(ParagraphStyle(name="PaperTableHead", parent=styles["PaperTable"],
                         fontName="PaperBold", textColor=colors.white))
styles.add(ParagraphStyle(name="PaperCaption", fontName="Paper", fontSize=9,
                         leading=12, spaceAfter=6, textColor=GRAY))
styles.add(ParagraphStyle(name="PaperBullet", parent=styles["PaperBody"], leftIndent=12,
                         firstLineIndent=-9))

REFERENCES = [
    ("Zhong et al. (2024). DistServe: Disaggregating Prefill and Decoding for Goodput-optimized Large Language Model Serving. OSDI 2024.",
     "https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf"),
    ("Qiu et al. (2024). Efficient Interactive LLM Serving with Proxy Model-based Sequence Length Prediction. arXiv:2404.08509.",
     "https://arxiv.org/abs/2404.08509"),
    ("Fu et al. (2024). Efficient LLM Scheduling by Learning to Rank. arXiv:2408.15792.",
     "https://arxiv.org/abs/2408.15792"),
    ("Sun et al. (2024). Llumnix: Dynamic Scheduling for Large Language Model Serving. OSDI 2024.",
     "https://www.usenix.org/conference/osdi24/presentation/sun-biao"),
    ("Huang et al. (2025). SLO-Aware Scheduling for Large Language Model Inferences. arXiv:2504.14966.",
     "https://arxiv.org/abs/2504.14966"),
    ("Wu et al. (2026). FastServe: Iteration-Level Preemptive Scheduling for Large Language Model Inference. NSDI 2026.",
     "https://www.usenix.org/conference/nsdi26/presentation/wu-bingyang"),
]
URL_NUMBERS = {url: i + 1 for i, (_, url) in enumerate(REFERENCES)}


def inline(text):
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    def link(match):
        label, url = match.groups()
        number = URL_NUMBERS.get(url)
        return label + (f" [{number}]" if number else f" ({url})")
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier" size="8">\1</font>', text)
    return text


class PaperDoc(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("PaperH1", "PaperH2"):
            text = flowable.getPlainText()
            key = "heading_" + str(len(self._bookmarks))
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, 0 if flowable.style.name == "PaperH1" else 1, False)
            self._bookmarks.append((text, self.page))


def footer(canvas, doc):
    width, height = canvas._pagesize
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CBD5DF"))
    canvas.line(48, height - 34, width - 48, height - 34)
    canvas.line(48, 36, width - 48, 36)
    canvas.setFont("Paper", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(48, height - 26, "SmartDistServe | Research manuscript")
    canvas.drawString(48, 23, "Synthetic workloads; uncalibrated simulation model")
    canvas.drawRightString(width - 48, 23, str(doc.page))
    canvas.restoreState()


width, height = A4
content_width = width - 96
doc = PaperDoc(str(PDF), pagesize=A4, leftMargin=48, rightMargin=48,
               topMargin=48, bottomMargin=48, title="SmartDistServe: Reproducible Simulation of Disaggregated LLM Scheduling",
               author="", subject="Formal research manuscript with measured synthetic simulation results")
doc._bookmarks = []
doc.addPageTemplates([
    PageTemplate(id="Portrait", frames=[Frame(48, 48, content_width, height-96, leftPadding=0, rightPadding=0,
                                              topPadding=0, bottomPadding=0)], onPage=footer, pagesize=A4),
    PageTemplate(id="Landscape", frames=[Frame(48, 48, landscape(A4)[0]-96, landscape(A4)[1]-96,
                                               leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
                 onPage=footer, pagesize=landscape(A4))])
story = []
source = (ROOT / "research" / "SmartDistServe.md").read_text(encoding="utf-8")
source = re.sub(r"Research prototype draft,.*?\n\n", "", source, count=1, flags=re.S)
source = source.replace("# SmartDistServe: a reproducible simulation study of slack, duration, and aging in disaggregated LLM serving",
                        "# SmartDistServe: Reproducible Simulation of Deadline-Aware Scheduling in Disaggregated LLM Serving")
source = source.replace("The contribution is an inspectable experimental artifact", "The contribution is a reproducible experimental artifact")
source = source.replace("\"slack\"", "slack")
abstract = ("Disaggregated large language model serving separates prompt processing from autoregressive decoding, "
            "but request heterogeneity continues to influence queueing delay and service-level objective (SLO) attainment. "
            "This study presents SmartDistServe, a reproducible discrete-event simulation prototype comparing phase-local "
            "first-come-first-served (FCFS), estimated shortest-job-first (SJF), earliest-deadline-first (EDF), and a heuristic "
            "combining normalized deadline slack, estimated request duration, and aging. Evaluation comprises 440 policy "
            "runs on 110 stored synthetic trace instances using five seeds. Metrics include time to first token, time per "
            "output token, joint SLO attainment, cohort goodput per GPU, tail waiting time, and group-outcome fairness. "
            "Across 16 main conditions, the heuristic exceeds FCFS in mean attainment in four conditions, falls below it "
            "in four, and ties in eight. Under mixed overload at six requests per second, estimated SJF achieves 55.30% "
            "mean attainment compared with 13.45% for the heuristic, while its mean run-level P95 waiting time increases "
            "from 28.10 to 61.71 seconds. The results identify performance tradeoffs rather than universal policy superiority. "
            "All workloads are synthetic and service coefficients are uncalibrated; improvement over physical serving "
            "systems is not established.")
source = re.sub(r"(## Abstract\n\n).*?(\n\n## Motivation)",
                lambda m: m[1] + abstract + "\n\n**Keywords:** LLM serving; disaggregation; discrete-event simulation; "
                "deadline scheduling; SLO attainment; fairness." + m[2], source, count=1, flags=re.S)
source = source.replace("Priority, short-job scheduling, deadline ordering, and aging are established techniques. "
                        "The following primary sources further rule out claiming that output-length estimates or "
                        "differentiated SLO priorities are new to LLM serving:",
                        "Priority, short-job scheduling, deadline ordering, and aging are established techniques. "
                        "Prior LLM-serving studies address output-length prediction, request prioritization, and "
                        "differentiated service objectives:")
source = source.replace("## Workloads and estimates\n\n",
                        "## Workloads and estimates\n\nThe complete synthetic distribution configuration is summarized "
                        "below. Bounds are inclusive; sigma denotes the lognormal shape parameter.\n\n"
                        "| Profile | Input mean | Output mean | Input bounds | Output bounds | Input sigma | Output sigma | TTFT / TPOT s |\n"
                        "|---|---:|---:|---|---|---:|---:|---|\n"
                        "| ShareGPT | 755 | 200 | 16-8192 | 2-1024 | 0.9 | 0.8 | 1.5 / 0.08 |\n"
                        "| HumanEval | 171 | 98 | 16-2048 | 2-512 | 0.7 | 0.7 | 0.35 / 0.10 |\n"
                        "| LongBench | 8192 | 91 | 1024-32768 | 2-512 | 0.6 | 0.6 | 8.0 / 0.06 |\n\n")
headings = {
    "Abstract": "Abstract",
    "Motivation and relation to DistServe": "1. Introduction",
    "Previous scheduling work and scope of the contribution": "2. Related Work and Contribution",
    "Model and policies": "3. System Model and Scheduling Policies",
    "Workloads and estimates": "4. Workloads and Duration Estimation",
    "Metric definitions": "5. Evaluation Metrics",
    "Measured simulation results": "6. Experimental Evaluation",
    "Main sweep (complete grid)": "6.1. Complete Main-Sweep Results",
    "Priority policy versus FCFS": "6.2. Paired Comparisons with FCFS",
    "Interpretation of measured tradeoffs": "6.3. Performance Tradeoffs",
    "Ablations at the configured mixed-workload rate": "6.4. Component and Sensitivity Ablations",
    "Conservative tested-grid capacity diagnostic": "6.5. Tested-Grid Capacity Diagnostic",
    "Limitations and interpretation": "7. Limitations and Threats to Validity",
    "Reproducibility and review": "8. Reproducibility and Artifact Validation",
}


def paragraph(text, style="PaperBody"):
    story.append(Paragraph(inline(text), styles[style]))


def add_table(lines):
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    rows = [row for row in rows if not all(re.fullmatch(r":?-+:?", cell) for cell in row)]
    columns = len(rows[0])
    if columns == 9:
        widths = [54, 29, 38, 51, 51, 40, 79, 59, 98]
        headers = ["Synthetic<br/>profile", "Rate<br/>req/s", "Policy", "Mean<br/>TTFT s", "Mean<br/>TPOT s",
                   "SLO<br/>%", "Goodput<br/>req/s/GPU", "P95<br/>wait s", "Jain<br/>prompt-bin SLO"]
        rows[0] = headers
    elif columns == 4 and "difference" in rows[0][2]:
        widths = [83, 45, 183, 188]
        rows[0] = ["Synthetic profile", "Rate<br/>req/s", "SLO difference, pp<br/>(95% halfwidth)",
                   "P95 wait difference, s<br/>(95% halfwidth)"]
    elif columns == 5:
        widths = [139, 66, 87, 103, 104]
        rows[0] = ["Condition", "SLO %", "P95 wait s", "Jain<br/>profile SLO", "Jain<br/>prompt-bin SLO"]
    else:
        widths = [content_width / columns] * columns
    widths = [v * content_width / sum(widths) for v in widths]
    data = []
    for i, row in enumerate(rows):
        style = styles["PaperTableHead" if i == 0 else "PaperTable"]
        data.append([Paragraph(cell if i == 0 and "<br/>" in cell else inline(cell), style) for cell in row])
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F0F4F7")]),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW", (0,-1), (-1,-1), .4, colors.HexColor("#B4C2CF"))]))
    story.append(table)
    story.append(Spacer(1, 9))


lines = source.splitlines()
i = 0
while i < len(lines):
    line = lines[i].strip()
    if not line:
        i += 1
        continue
    if line.startswith("```"):
        code = []
        i += 1
        while i < len(lines) and not lines[i].startswith("```"):
            code.append(lines[i])
            i += 1
        story.append(Preformatted("\n".join(code), ParagraphStyle("Code", fontName="Courier", fontSize=8,
                                                               leading=12, spaceBefore=5, spaceAfter=9)))
    elif line.startswith("|"):
        table_lines = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            table_lines.append(lines[i])
            i += 1
        add_table(table_lines)
        continue
    elif line.startswith("# "):
        paragraph(line[2:], "PaperTitle")
        paragraph("Research manuscript | 13 October 2026", "PaperCaption")
    elif line.startswith("### "):
        story.append(CondPageBreak(100))
        paragraph(headings.get(line[4:], line[4:]), "PaperH2")
    elif line.startswith("## "):
        title = headings.get(line[3:], line[3:])
        paragraph(title, "PaperH1")
        if title == "6. Experimental Evaluation":
            paragraph("The evaluated workload distributions and service coefficients are synthetic assumptions. "
                      "No physical inference engine or empirical benchmark dataset was used. All reported numerical "
                      "outcomes originate from the executed simulator and saved experiment artifacts.")
    elif line.startswith("- "):
        paragraph("- " + line[2:], "PaperBullet")
    else:
        text = [line]
        while i+1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith(("#", "|", "- ", "```")):
            i += 1
            text.append(lines[i].strip())
        paragraph(" ".join(text))
    i += 1

audit = json.loads((ROOT / "results/reference/audit.json").read_text())
replay = json.loads((ROOT / "results/reference/replay.json").read_text())
paragraph(f"The final simulator passed 38 automated tests. Independent recomputation from serialized timelines "
          f"completed {audit['checks']:,} checks with {len(audit['failures'])} failures across "
          f"{audit['request_rows']:,} policy-specific request outcomes. Replay reproduced exact metrics for "
          f"all {replay['runs_replayed']} runs. The 110 stored trace instances include deliberately reused "
          "realizations for paired component ablations; policy outcomes are not treated as independent statistical samples.")
paragraph("Code review identified and corrected configuration-option precedence and coincident-event routing issues. "
          "Completion events now release resources before simultaneous arrivals and transfers are routed. "
          "The reference suite was rerun after this correction and its numerical output hashes remained unchanged. "
          "Validation establishes internal consistency and determinism rather than physical-model accuracy.")
paragraph("9. Conclusion", "PaperH1")
paragraph("SmartDistServe provides a reproducible simulation artifact for evaluating phase-local scheduling in "
          "disaggregated LLM serving. Within the tested synthetic workload grid, the slack, duration, and aging "
          "heuristic improves mean joint SLO attainment over FCFS in four conditions, reduces it in four, and "
          "ties in eight. Estimated SJF can achieve substantially higher attainment under overload while increasing "
          "tail waiting. These findings support evaluation of multiple performance and fairness measures rather "
          "than a claim of universal policy superiority. The principal contribution is the experimental integration "
          "and its inspectable measured tradeoffs; algorithmic novelty and improvement over the physical DistServe "
          "system are not established. Empirical traces, calibrated service models, stronger baselines, and physical "
          "GPU evaluation remain necessary for external validation.")
paragraph("References", "PaperH1")
for number, (reference, url) in enumerate(REFERENCES, 1):
    paragraph(f"[{number}] {reference}")
    story.append(Paragraph(f'<link href="{url}" color="#166A87">{escape(url)}</link>', styles["PaperCaption"]))

paragraph("Appendix A. Reproduction Procedure", "PaperH1")
paragraph("The following commands execute from the repository root. Simulation, tests, auditing, and reporting "
          "require Python 3.11 or later and the standard library. Plot generation requires the pinned dependencies "
          "in requirements-plots.txt. The reference manifest records the precise Python environment and source hashes.")
commands = """python -m unittest discover -s tests -v
python -m smartdistserve experiment --config configs/experiment.json
python -m smartdistserve report --results results/reference
python scripts/audit_results.py --results results/reference
python scripts/replay_results.py --results results/reference
python scripts/plot_results.py --results results/reference"""
story.append(Preformatted(commands, ParagraphStyle("Commands", fontName="Courier", fontSize=7.5, leading=12, spaceAfter=9)))
paragraph("The saved manifest contains all workload definitions, seeds, hardware and scheduler settings, source "
          "hashes, trace hashes, and output hashes. Complete inputs are retained in traces.jsonl.gz; policy-specific "
          "timestamps, measured-cohort flags, and success outcomes are retained in requests.csv.gz. Seed-level "
          "metrics, group statistics, aggregate uncertainty, and paired contrasts are retained separately. "
          "All requests are drained; failed or late requests are not censored.")
paragraph("Appendix B. Measured Figures", "PaperH1")
paragraph("The following six figures are generated from the saved run metrics. Their error bars represent "
          "95% Student t intervals across five seeds, not uncertainty in the hardware cost model. "
          "Figures use zero-baseline axes; unconstrained intervals can extend outside natural metric ranges, "
          "and complete numeric bounds remain available in summary.csv. Landscape pages preserve figure legibility.")
figures = [
    ("slo_attainment", "Joint SLO attainment across all main workload profiles and offered rates."),
    ("goodput", "Successful cohort-request rate per provisioned GPU. This is not sustainable steady-state capacity."),
    ("waiting_tail", "Mean of run-level P95 queue waiting times. Transfer and active service are excluded."),
    ("fairness", "Jain index of prompt-bin SLO attainment rates. Outcome parity does not establish resource fairness."),
    ("latency_tails", "Mean run-level P95 TTFT and TPOT under the mixed workload."),
    ("ablations", "Smart-policy component and sensitivity ablations at mixed rate 3 requests per second."),
]
story.append(NextPageTemplate("Landscape"))
story.append(PageBreak())
for index, (name, caption) in enumerate(figures, 1):
    img = Image(str(ROOT / "results/reference/figures" / f"{name}.png"))
    max_w, max_h = 710, 445
    scale = min(max_w / img.imageWidth, max_h / img.imageHeight)
    img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
    story.append(img)
    story.append(Spacer(1, 6))
    paragraph(f"Figure {index}. {caption}", "PaperCaption")
    if index != len(figures):
        story.append(PageBreak())

doc.build(story)
reader = PdfReader(str(PDF))
text = "\n".join(page.extract_text() or "" for page in reader.pages)
required = ["Abstract", "1. Introduction", "2. Related Work", "9. Conclusion", "References", "440", "149,400"]
missing = [item for item in required if item not in text]
if missing:
    raise RuntimeError(f"PDF text validation failed: {missing}")
if any(not (page.extract_text() or "").strip() for page in reader.pages):
    raise RuntimeError("Empty PDF page")
figure_pages = sum("Figure " in (page.extract_text() or "") for page in reader.pages)
if figure_pages != 6:
    raise RuntimeError(f"Expected six figure pages, found {figure_pages}")
(OUT / "SmartDistServe_Research_Paper.txt").write_text(text, encoding="utf-8")
(OUT / "validation.json").write_text(json.dumps({"pages":len(reader.pages), "figures":figure_pages,
    "required_sections_present":not missing, "empty_pages":0, "bookmarks":doc._bookmarks}, indent=2)+"\n")
print(f"Created {PDF}\nPages: {len(reader.pages)}; figures: {figure_pages}; text checks passed")

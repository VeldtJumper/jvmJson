#!/usr/bin/env python3
"""Turn JMH JSON output into the static GitHub Pages dashboard."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import platform
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Benchmark metadata
# ---------------------------------------------------------------------------

LIBRARIES = [
    {
        "id": "gson",
        "name": "Gson",
        "short": "Gson",
        "note": "Reflection",
        "color": "#34d399",
    },
    {
        "id": "jackson",
        "name": "Jackson",
        "short": "Jackson",
        "note": "jackson-module-kotlin",
        "color": "#f59e0b",
    },
    {
        "id": "jackson-blackbird",
        "name": "Jackson + Blackbird",
        "short": "Jackson BB",
        "note": "Bytecode module",
        "color": "#fb7185",
    },
    {
        "id": "kotlinx",
        "name": "kotlinx.serialization",
        "short": "kotlinx",
        "note": "Compiler plugin",
        "color": "#8b5cf6",
    },
    {
        "id": "moshi-codegen",
        "name": "Moshi (codegen)",
        "short": "Moshi codegen",
        "note": "KSP adapter",
        "color": "#22d3ee",
    },
    {
        "id": "moshi-reflect",
        "name": "Moshi (reflection)",
        "short": "Moshi reflect",
        "note": "KotlinJsonAdapterFactory",
        "color": "#38bdf8",
    },
]

LIBRARY_BY_ID = {library["id"]: library for library in LIBRARIES}

METHODS = {
    "gsonSerialize": ("gson", "Serialize"),
    "gsonDeserialize": ("gson", "Deserialize"),
    "jacksonSerialize": ("jackson", "Serialize"),
    "jacksonDeserialize": ("jackson", "Deserialize"),
    "jacksonBlackbirdSerialize": ("jackson-blackbird", "Serialize"),
    "jacksonBlackbirdDeserialize": ("jackson-blackbird", "Deserialize"),
    "kotlinxSerialize": ("kotlinx", "Serialize"),
    "kotlinxDeserialize": ("kotlinx", "Deserialize"),
    "moshiCodegenSerialize": ("moshi-codegen", "Serialize"),
    "moshiCodegenDeserialize": ("moshi-codegen", "Deserialize"),
    "moshiReflectSerialize": ("moshi-reflect", "Serialize"),
    "moshiReflectDeserialize": ("moshi-reflect", "Deserialize"),
}

SIZE_LABELS = {10: "Small", 1_000: "Medium", 25_000: "Large"}

VERSION_LABELS = {
    "kotlin": "Kotlin",
    "ksp": "KSP",
    "moshi": "Moshi",
    "kotlinxSerialization": "kotlinx.serialization",
    "jackson": "Jackson",
    "gson": "Gson",
    "jmh": "JMH",
    "jmhPlugin": "JMH Gradle plugin",
}


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def read_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    section = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "versions" or "=" not in line:
            continue
        key, value = line.split("=", 1)
        versions[key.strip()] = value.strip().strip('"')
    return versions


def load_payload_stats(payload_file: Path) -> tuple[dict[int, dict], dict]:
    data = json.loads(payload_file.read_text(encoding="utf-8"))
    sizes = {int(item["userCount"]): item for item in data.get("sizes", [])}
    return sizes, data.get("runtime", {})


def error_fraction(entry: dict) -> float:
    metric = entry.get("primaryMetric", {})
    score = float(metric.get("score") or 0.0)
    if score <= 0 or not math.isfinite(score):
        return 0.0
    confidence = metric.get("scoreConfidence")
    if confidence and len(confidence) == 2:
        low, high = float(confidence[0]), float(confidence[1])
        half_width = abs(high - low) / 2.0
    else:
        half_width = abs(float(metric.get("scoreError") or 0.0))
    if not math.isfinite(half_width):
        return 0.0
    return (half_width / score) * 100.0


def build_rows(results: list[dict], payloads: dict[int, dict]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    skipped: list[str] = []
    for entry in results:
        method = entry.get("benchmark", "").rsplit(".", 1)[-1]
        mapping = METHODS.get(method)
        if mapping is None:
            skipped.append(method)
            continue

        library_id, operation = mapping
        library = LIBRARY_BY_ID[library_id]
        user_count = int(entry.get("params", {}).get("userCount", 0))
        payload = payloads.get(user_count)
        if payload is None:
            print(f"warning: no payload stats for {user_count} users", file=sys.stderr)
            continue

        score = float(entry["primaryMetric"]["score"])
        bytes_ = int(payload["jsonBytes"])
        score_error = float(entry["primaryMetric"].get("scoreError") or 0.0)
        if not math.isfinite(score_error):
            score_error = 0.0
        rows.append(
            {
                "libraryId": library_id,
                "library": library["name"],
                "short": library["short"],
                "note": library["note"],
                "color": library["color"],
                "operation": operation,
                "size": user_count,
                "sizeLabel": SIZE_LABELS.get(user_count, f"{user_count:,} users"),
                "payloadBytes": bytes_,
                "opsPerSec": score,
                "msPerOp": 1000.0 / score if score else 0.0,
                "mbPerSec": (bytes_ * score) / 1_000_000.0 if score else 0.0,
                "errorPct": error_fraction(entry),
                "scoreError": score_error,
                "scoreUnit": entry["primaryMetric"].get("scoreUnit", "ops/s"),
            }
        )

    if skipped:
        print(f"warning: skipped unknown benchmark methods: {sorted(set(skipped))}", file=sys.stderr)

    sizes = []
    for user_count in sorted(payloads):
        payload = payloads[user_count]
        sizes.append(
            {
                "userCount": user_count,
                "label": SIZE_LABELS.get(user_count, f"{user_count:,} users"),
                "jsonBytes": int(payload["jsonBytes"]),
                "sha256": payload["sha256"],
            }
        )

    rows.sort(key=lambda row: (row["operation"], row["size"], -row["opsPerSec"]))
    return rows, sizes


def build_meta(results: list[dict], versions: dict[str, str], sizes: list[dict], runtime: dict) -> dict:
    first = results[0] if results else {}
    repo = os.environ.get("GITHUB_REPOSITORY", "VeldtJumper/jvmJson")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    commit = os.environ.get("GITHUB_SHA", "")
    branch = os.environ.get("GITHUB_REF_NAME", "")
    runner = os.environ.get("RUNNER_OS") or platform.system()
    image = os.environ.get("ImageOS") or "local machine"

    now = dt.datetime.now(dt.timezone.utc)
    return {
        "generatedAt": now.isoformat(),
        "generatedLabel": now.strftime("%b %d, %Y %H:%M UTC"),
        "repo": repo,
        "repoUrl": f"https://github.com/{repo}",
        "runId": run_id,
        "runUrl": f"{server}/{repo}/actions/runs/{run_id}" if run_id else f"{server}/{repo}/actions",
        "workflowUrl": f"{server}/{repo}/actions/workflows/benchmark.yml",
        "commit": commit,
        "commitShort": commit[:7] if commit else "local",
        "branch": branch or "local",
        "runner": runner,
        "image": image,
        "jvm": first.get("jvm", "unknown JVM"),
        "javaVersion": runtime.get("javaVersion", ""),
        "javaVendor": runtime.get("javaVendor", ""),
        "osName": runtime.get("osName", ""),
        "osArch": runtime.get("osArch", ""),
        "jmhVersion": first.get("jmhVersion", versions.get("jmh", "?")),
        "warmupIterations": first.get("warmupIterations"),
        "measurementIterations": first.get("measurementIterations"),
        "warmupTime": first.get("warmupTime", "1 s"),
        "measurementTime": first.get("measurementTime", "1 s"),
        "forks": first.get("forks"),
        "threads": first.get("threads"),
        "mode": first.get("mode", "thrpt"),
        "jvmArgs": first.get("jvmArgs", []),
        "versions": versions,
        "sizes": sizes,
    }


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>jvmJson · JVM JSON library benchmarks</title>
  <meta name="description" content="JMH microbenchmarks for Kotlin and JVM JSON libraries: kotlinx.serialization, Moshi codegen, Moshi reflection, Jackson, Jackson + Blackbird, and Gson.">
  <meta name="theme-color" content="#070b14">
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #070b14;
      --panel: rgba(15, 23, 42, 0.72);
      --panel-strong: #0f172a;
      --border: rgba(148, 163, 184, 0.14);
      --border-strong: rgba(148, 163, 184, 0.22);
      --text: #e2e8f0;
      --muted: #94a3b8;
      --faint: #64748b;
      --accent: #38bdf8;
      --accent-2: #a78bfa;
      --good: #34d399;
      --warn: #fbbf24;
      --radius: 18px;
      --shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      background:
        radial-gradient(1000px 600px at 8% -12%, rgba(56, 189, 248, 0.14), transparent 60%),
        radial-gradient(900px 520px at 92% -4%, rgba(167, 139, 250, 0.12), transparent 55%),
        var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(148, 163, 184, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(148, 163, 184, 0.035) 1px, transparent 1px);
      background-size: 64px 64px;
      mask-image: linear-gradient(to bottom, black, transparent 78%);
      pointer-events: none;
      z-index: -1;
    }
    a { color: var(--accent); }
    .container { width: min(1180px, calc(100% - 40px)); margin: 0 auto; }

    .hero { padding: 78px 0 38px; }
    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      color: #7dd3fc;
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-weight: 700;
    }
    .pulse {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--good);
      box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.6);
      animation: pulse 2.4s infinite;
    }
    @keyframes pulse {
      70% { box-shadow: 0 0 0 10px rgba(52, 211, 153, 0); }
      100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); }
    }
    h1 {
      font-size: clamp(44px, 7vw, 82px);
      line-height: 1.02;
      letter-spacing: -0.045em;
      margin: 18px 0;
      font-weight: 800;
    }
    .grad {
      background: linear-gradient(100deg, #7dd3fc, #a78bfa 55%, #f0abfc);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }
    .lede {
      max-width: 760px;
      color: #a8b3c7;
      font-size: clamp(16px, 2vw, 19px);
      margin: 0 0 26px;
    }
    .hero-badges { display: flex; flex-wrap: wrap; gap: 10px; }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.55);
      color: #cbd5e1;
      font-size: 13px;
      backdrop-filter: blur(12px);
      text-decoration: none;
    }
    .badge-link { color: #7dd3fc; }
    .badge-link:hover { border-color: rgba(56, 189, 248, 0.4); }

    .stat-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin: 8px 0 24px;
    }
    .stat {
      padding: 18px 20px;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(17, 24, 39, 0.8), rgba(10, 16, 30, 0.86));
      box-shadow: var(--shadow);
      min-width: 0;
    }
    .stat .label {
      color: var(--faint);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.13em;
      text-transform: uppercase;
    }
    .stat .value {
      margin-top: 6px;
      font-size: clamp(24px, 3vw, 34px);
      line-height: 1.05;
      letter-spacing: -0.035em;
      font-weight: 800;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .stat .sub { margin-top: 4px; color: var(--muted); font-size: 12px; }

    .panel {
      background: linear-gradient(180deg, rgba(17, 24, 39, 0.82), rgba(10, 16, 30, 0.9));
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }

    .controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 22px;
      padding: 14px 16px;
      margin: 0 0 16px;
    }
    .control-group { display: flex; align-items: center; gap: 10px; }
    .control-label {
      color: var(--faint);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.13em;
      text-transform: uppercase;
    }
    .segmented {
      display: flex;
      gap: 2px;
      padding: 4px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: rgba(2, 6, 23, 0.58);
    }
    .segmented button {
      appearance: none;
      border: 0;
      border-radius: 9px;
      background: transparent;
      color: var(--muted);
      padding: 8px 12px;
      font: inherit;
      font-size: 13px;
      line-height: 1.2;
      cursor: pointer;
      transition: background 160ms ease, color 160ms ease, box-shadow 160ms ease;
    }
    .segmented button em { font-style: normal; color: var(--faint); font-size: 11px; margin-left: 4px; }
    .segmented button:hover { color: var(--text); }
    .segmented button.active {
      color: #e0f2fe;
      background: linear-gradient(180deg, rgba(56, 189, 248, 0.2), rgba(56, 189, 248, 0.1));
      box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.3);
    }
    .control-hint { margin-left: auto; color: var(--faint); font-size: 12px; }

    .winner {
      display: flex;
      align-items: center;
      gap: 18px;
      padding: 20px 22px;
      margin: 0 0 16px;
      border: 1px solid rgba(52, 211, 153, 0.22);
      border-radius: var(--radius);
      background:
        linear-gradient(100deg, rgba(52, 211, 153, 0.09), rgba(56, 189, 248, 0.05) 55%, rgba(167, 139, 250, 0.08));
      box-shadow: var(--shadow);
    }
    .winner-rank {
      flex: 0 0 auto;
      color: var(--good);
      border: 1px solid rgba(52, 211, 153, 0.3);
      background: rgba(52, 211, 153, 0.08);
      border-radius: 12px;
      padding: 10px 12px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.16em;
    }
    .winner-copy { min-width: 0; flex: 1 1 auto; }
    .winner-kicker {
      color: var(--good);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }
    .winner h2 {
      margin: 4px 0 3px;
      font-size: clamp(20px, 3vw, 28px);
      letter-spacing: -0.03em;
      line-height: 1.15;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .winner-detail { color: var(--muted); font-size: 13px; }
    .winner-numbers {
      display: flex;
      gap: 18px;
      flex: 0 0 auto;
      padding-left: 18px;
      border-left: 1px solid rgba(148, 163, 184, 0.16);
    }
    .winner-number span {
      display: block;
      color: var(--faint);
      font-size: 9px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .winner-number strong {
      display: block;
      margin-top: 2px;
      font-size: 16px;
      letter-spacing: -0.02em;
      font-variant-numeric: tabular-nums;
    }

    .chart-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-bottom: 16px;
    }
    .chart-card { padding: 18px 18px 10px; }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 14px;
      margin-bottom: 14px;
    }
    .panel-head h2 {
      margin: 0;
      font-size: 16px;
      letter-spacing: -0.01em;
    }
    .panel-head p {
      margin: 3px 0 0;
      color: var(--faint);
      font-size: 12px;
    }
    .chip {
      flex: 0 0 auto;
      padding: 5px 9px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: rgba(2, 6, 23, 0.38);
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .chart-wrap { position: relative; height: 356px; }

    .table-panel { padding: 18px; margin-bottom: 16px; }
    .ghost-link {
      flex: 0 0 auto;
      color: var(--muted);
      font-size: 12px;
      text-decoration: none;
      border-bottom: 1px dashed rgba(148, 163, 184, 0.35);
      padding-bottom: 1px;
    }
    .ghost-link:hover { color: var(--accent); }
    .table-wrap {
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: rgba(2, 6, 23, 0.24);
    }
    table {
      width: 100%;
      min-width: 760px;
      border-collapse: collapse;
      font-size: 13px;
    }
    th {
      text-align: left;
      padding: 11px 12px;
      color: var(--faint);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.11em;
      text-transform: uppercase;
      border-bottom: 1px solid var(--border);
      background: rgba(2, 6, 23, 0.4);
    }
    td {
      padding: 11px 12px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.07);
      vertical-align: middle;
    }
    tr:last-child td { border-bottom: 0; }
    tbody tr:hover td { background: rgba(56, 189, 248, 0.035); }
    .rank {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 26px;
      height: 26px;
      border-radius: 8px;
      background: rgba(148, 163, 184, 0.08);
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }
    .rank-1 {
      color: #052e2b;
      background: linear-gradient(180deg, #6ee7b7, #34d399);
    }
    .lib { display: flex; align-items: center; gap: 9px; }
    .swatch { width: 9px; height: 9px; border-radius: 3px; flex: 0 0 auto; }
    .lib-name { color: #e2e8f0; font-weight: 600; }
    .lib-note { color: var(--faint); font-size: 11px; }
    .num {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-variant-numeric: tabular-nums;
      color: #cbd5e1;
      white-space: nowrap;
    }
    .muted-num { color: var(--faint); }

    .payload-panel { padding: 18px; margin-bottom: 16px; }
    .payload-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
    }
    .payload-card {
      padding: 16px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(2, 6, 23, 0.34);
    }
    .payload-top { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
    .payload-name {
      color: var(--accent);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .payload-count { color: var(--faint); font-size: 11px; }
    .payload-size {
      margin-top: 7px;
      font-size: 24px;
      font-weight: 800;
      letter-spacing: -0.03em;
    }
    .payload-sub { color: var(--muted); font-size: 12px; }
    .payload-card code {
      display: block;
      margin-top: 10px;
      color: #7dd3fc;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 10px;
      word-break: break-all;
    }
    .fineprint { margin: 12px 0 0; color: var(--faint); font-size: 12px; }

    .two-col {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-bottom: 16px;
    }
    .two-col .panel { padding: 20px; }
    .checklist { list-style: none; padding: 0; margin: 0; display: grid; gap: 11px; }
    .checklist li { position: relative; padding-left: 24px; color: #b6c2d6; font-size: 13.5px; }
    .checklist li::before {
      content: "✓";
      position: absolute;
      left: 0;
      top: 0;
      color: var(--good);
      font-weight: 800;
    }
    .checklist code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: #7dd3fc;
      font-size: 12px;
    }
    .meta-list {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 8px 14px;
      margin: 0;
      font-size: 12.5px;
    }
    .meta-list dt { color: var(--faint); }
    .meta-list dd { margin: 0; color: #cbd5e1; word-break: break-word; }
    .versions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
    .version-pill {
      padding: 5px 8px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(2, 6, 23, 0.3);
      color: var(--muted);
      font-size: 10.5px;
      white-space: nowrap;
    }
    .version-pill strong { color: #cbd5e1; font-weight: 700; }

    .caveat-panel { padding: 20px; margin-bottom: 26px; }
    .caveat-panel p { margin: 0; color: var(--muted); font-size: 13.5px; max-width: 940px; }
    .caveat-panel strong { color: #e2e8f0; }

    footer { padding: 8px 0 46px; color: var(--faint); font-size: 12.5px; }
    footer .container {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 18px;
      flex-wrap: wrap;
      border-top: 1px solid var(--border);
      padding-top: 18px;
    }
    footer a { color: #7dd3fc; text-decoration: none; }
    footer a:hover { text-decoration: underline; }

    @media (max-width: 980px) {
      .stat-grid { grid-template-columns: repeat(2, 1fr); }
      .chart-grid, .two-col { grid-template-columns: 1fr; }
      .control-hint { margin-left: 0; width: 100%; }
    }
    @media (max-width: 680px) {
      .container { width: calc(100% - 24px); }
      .hero { padding: 52px 0 28px; }
      .controls { align-items: flex-start; flex-direction: column; gap: 13px; }
      .segmented button em { display: none; }
      .winner { align-items: flex-start; flex-direction: column; gap: 12px; }
      .winner-numbers { border-left: 0; padding-left: 0; }
      .winner h2 { white-space: normal; }
      .payload-grid { grid-template-columns: 1fr; }
      .stat-grid { grid-template-columns: 1fr 1fr; }
      .chart-wrap { height: 310px; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation: none !important; transition: none !important; }
    }
  </style>
</head>
<body>
  <header class="hero">
    <div class="container">
      <div class="eyebrow"><span class="pulse"></span> JMH · Kotlin/JVM · reproducible microbenchmarks</div>
      <h1>JSON, <span class="grad">head to head.</span></h1>
      <p class="lede">
        Six idiomatic JSON stacks. Three payload sizes. Serialize and deserialize.
        Same JVM, same input bytes, same rules — the numbers come from one JMH run.
      </p>
      <div class="hero-badges">
        <span class="badge" id="badge-libs">6 libraries</span>
        <span class="badge" id="badge-iterations">5 + 20 iterations</span>
        <span class="badge" id="badge-run">latest run</span>
        <a class="badge badge-link" id="badge-repo" href="#" target="_blank" rel="noreferrer">GitHub ↗</a>
      </div>
    </div>
  </header>

  <main class="container">
    <section class="stat-grid" id="statGrid" aria-label="Run summary"></section>

    <section class="panel controls" aria-label="Result filters">
      <div class="control-group">
        <span class="control-label">Operation</span>
        <div class="segmented" id="operationControl" role="group" aria-label="Operation">
          <button type="button" data-operation="Deserialize" class="active" aria-pressed="true">Deserialize</button>
          <button type="button" data-operation="Serialize" aria-pressed="false">Serialize</button>
        </div>
      </div>
      <div class="control-group">
        <span class="control-label">Payload</span>
        <div class="segmented" id="sizeControl" role="group" aria-label="Payload size"></div>
      </div>
      <div class="control-hint">All numbers from a single JMH run on the same machine.</div>
    </section>

    <section class="winner" id="winner" aria-live="polite">
      <div class="winner-rank">01</div>
      <div class="winner-copy">
        <div class="winner-kicker" id="winnerKicker">Fastest deserialize · Medium</div>
        <h2 id="winnerName">Loading…</h2>
        <div class="winner-detail" id="winnerDetail"></div>
      </div>
      <div class="winner-numbers" id="winnerNumbers"></div>
    </section>

    <section class="chart-grid">
      <article class="panel chart-card">
        <div class="panel-head">
          <div>
            <h2>Operations / second</h2>
            <p>Higher is better · linear scale</p>
          </div>
          <span class="chip" id="opsChip">—</span>
        </div>
        <div class="chart-wrap"><canvas id="opsChart" aria-label="Operations per second by library"></canvas></div>
      </article>

      <article class="panel chart-card">
        <div class="panel-head">
          <div>
            <h2>Megabytes / second</h2>
            <p>Payload bytes × operations / second</p>
          </div>
          <span class="chip" id="mbChip">—</span>
        </div>
        <div class="chart-wrap"><canvas id="mbChart" aria-label="Megabytes per second by library"></canvas></div>
      </article>
    </section>

    <section class="panel table-panel">
      <div class="panel-head">
        <div>
          <h2>Full results</h2>
          <p id="tableCaption">—</p>
        </div>
        <a class="ghost-link" href="data/results.json" target="_blank" rel="noreferrer">results.json ↗</a>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Rank</th>
              <th scope="col">Library</th>
              <th scope="col">ops / sec</th>
              <th scope="col">time / op</th>
              <th scope="col">MB / sec</th>
              <th scope="col">± error</th>
            </tr>
          </thead>
          <tbody id="resultsBody"></tbody>
        </table>
      </div>
    </section>

    <section class="panel payload-panel">
      <div class="panel-head">
        <div>
          <h2>Payloads</h2>
          <p>Deterministic data, generated from one seeded model</p>
        </div>
        <a class="ghost-link" href="data/payload-stats.json" target="_blank" rel="noreferrer">payload-stats.json ↗</a>
      </div>
      <div class="payload-grid" id="payloadGrid"></div>
      <p class="fineprint">Every deserializer receives the identical UTF-8 JSON string. The SHA-256 digest is published so the input can be verified independently.</p>
    </section>

    <section class="two-col">
      <article class="panel">
        <div class="panel-head"><div><h2>Fair by construction</h2><p>What is held constant</p></div></div>
        <ul class="checklist">
          <li>Same JVM and heap for every benchmark: one fresh fork per benchmark, fixed <code>-Xms/-Xmx</code> and <code>AlwaysPreTouch</code>.</li>
          <li>Every deserializer parses the exact same JSON string; every serializer starts from an equivalent in-memory model.</li>
          <li>JMH throughput mode with per-method warmup and measured 1-second iterations; results consumed through a Blackhole.</li>
          <li>Pinned dependency versions, JDK 21, and a fixed Ubuntu runner image for the published run.</li>
          <li>The payload generator is seeded, so re-running the workflow produces the same bytes and the same workload.</li>
          <li>Both serialization and deserialization are measured, across small, medium, and large payloads.</li>
        </ul>
      </article>

      <article class="panel">
        <div class="panel-head"><div><h2>Environment</h2><p>Published run</p></div></div>
        <dl class="meta-list" id="envList"></dl>
        <div class="versions" id="versionList"></div>
      </article>
    </section>

    <section class="panel caveat-panel">
      <p>
        <strong>Read it as a comparison, not an absolute score.</strong>
        GitHub-hosted runners are shared and noisy, so absolute numbers move between runs.
        The ranking and the relative gaps within one run are the useful signal. Real applications
        also pay costs this benchmark does not model: schema evolution, validation, streaming,
        polymorphism, and allocation pressure in a larger heap.
      </p>
    </section>
  </main>

  <footer>
    <div class="container">
      <span>Built by <a href="https://github.com/VeldtJumper" target="_blank" rel="noreferrer">VeldtJumper</a> · jvmJson</span>
      <span>
        <a id="footer-repo" href="#" target="_blank" rel="noreferrer">Source</a> ·
        <a id="footer-workflow" href="#" target="_blank" rel="noreferrer">Workflow</a> ·
        <a id="footer-run" href="#" target="_blank" rel="noreferrer">Run</a> ·
        <a href="data/raw-jmh.json" target="_blank" rel="noreferrer">Raw JMH JSON</a>
      </span>
    </div>
  </footer>

  <script>
    const DATA = __DATA_JSON__;

    const state = {
      operation: "Deserialize",
      size: DATA.sizes.find((size) => size.userCount === 1000)?.userCount ?? DATA.sizes[0]?.userCount,
    };

    const byId = Object.fromEntries(DATA.libraries.map((library) => [library.id, library]));
    const sizeById = Object.fromEntries(DATA.sizes.map((size) => [size.userCount, size]));
    let currentRows = [];
    let opsChart;
    let mbChart;

    const nf = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
    const nf1 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });

    function formatNumber(value) {
      if (!Number.isFinite(value)) return "—";
      return nf.format(value);
    }

    function formatCompact(value) {
      if (!Number.isFinite(value)) return "—";
      if (value >= 1_000_000) return (value / 1_000_000).toFixed(2) + "M";
      if (value >= 1_000) return (value / 1_000).toFixed(1) + "k";
      return value.toFixed(0);
    }

    function formatBytes(bytes) {
      if (!Number.isFinite(bytes)) return "—";
      if (bytes >= 1_000_000) return (bytes / 1_000_000).toFixed(2) + " MB";
      if (bytes >= 1_000) return (bytes / 1_000).toFixed(1) + " KB";
      return bytes + " B";
    }

    function formatMs(ms) {
      if (!Number.isFinite(ms) || ms <= 0) return "—";
      if (ms < 0.001) return (ms * 1_000_000).toFixed(1) + " ns";
      if (ms < 1) return (ms * 1_000).toFixed(2) + " µs";
      return ms.toFixed(2) + " ms";
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function buildStatGrid() {
      const largest = DATA.sizes[DATA.sizes.length - 1];
      const iterations = DATA.meta.measurementIterations ?? "?";
      const warmup = DATA.meta.warmupIterations ?? "?";
      const statGrid = document.getElementById("statGrid");
      statGrid.innerHTML = `
        <div class="stat">
          <div class="label">Libraries</div>
          <div class="value">${DATA.libraries.length}</div>
          <div class="sub">Kotlin and JVM JSON stacks</div>
        </div>
        <div class="stat">
          <div class="label">Payload sizes</div>
          <div class="value">${DATA.sizes.length}</div>
          <div class="sub">${formatBytes(DATA.sizes[0]?.jsonBytes)} → ${formatBytes(largest?.jsonBytes)}</div>
        </div>
        <div class="stat">
          <div class="label">Iterations</div>
          <div class="value">${warmup} + ${iterations}</div>
          <div class="sub">warmup + measured · ${escapeHtml(DATA.meta.measurementTime)} each</div>
        </div>
        <div class="stat">
          <div class="label">Fastest now</div>
          <div class="value" id="fastestNow">—</div>
          <div class="sub" id="fastestNowSub">—</div>
        </div>
      `;
    }

    function buildSizeControl() {
      const control = document.getElementById("sizeControl");
      control.innerHTML = DATA.sizes
        .map(
          (size) =>
            `<button type="button" data-size="${size.userCount}" aria-pressed="false">${escapeHtml(size.label)}<em>${formatNumber(size.userCount)} users</em></button>`
        )
        .join("");

      control.querySelectorAll("button").forEach((button) => {
        button.addEventListener("click", () => {
          state.size = Number(button.dataset.size);
          syncControls();
          render();
        });
      });
    }

    function syncControls() {
      document.querySelectorAll("#operationControl button").forEach((button) => {
        const active = button.dataset.operation === state.operation;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
      });
      document.querySelectorAll("#sizeControl button").forEach((button) => {
        const active = Number(button.dataset.size) === state.size;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
      });
    }

    function buildPayloadGrid() {
      const grid = document.getElementById("payloadGrid");
      grid.innerHTML = DATA.sizes
        .map(
          (size) => `
            <div class="payload-card">
              <div class="payload-top">
                <span class="payload-name">${escapeHtml(size.label)}</span>
                <span class="payload-count">${formatNumber(size.userCount)} users</span>
              </div>
              <div class="payload-size">${formatBytes(size.jsonBytes)}</div>
              <div class="payload-sub">${(size.jsonBytes / size.userCount).toFixed(0)} bytes / user</div>
              <code>sha256 ${escapeHtml(size.sha256.slice(0, 20))}…</code>
            </div>`
        )
        .join("");
    }

    function buildMeta() {
      document.getElementById("badge-libs").textContent = `${DATA.libraries.length} libraries`;
      document.getElementById("badge-iterations").textContent =
        `${DATA.meta.warmupIterations ?? "?"} warmup + ${DATA.meta.measurementIterations ?? "?"} measured`;
      document.getElementById("badge-run").textContent = DATA.meta.commitShort
        ? `commit ${DATA.meta.commitShort}`
        : "latest run";
      document.getElementById("badge-repo").href = DATA.meta.repoUrl;
      document.getElementById("footer-repo").href = DATA.meta.repoUrl;
      document.getElementById("footer-workflow").href = DATA.meta.workflowUrl;
      document.getElementById("footer-run").href = DATA.meta.runUrl;

      const envRows = [
        ["JMH", DATA.meta.jmhVersion],
        ["Java", `${DATA.meta.javaVersion || "?"}${DATA.meta.javaVendor ? " · " + DATA.meta.javaVendor : ""}`],
        ["OS", `${DATA.meta.osName || "?"} ${DATA.meta.osArch || ""}`.trim()],
        ["Runner", `${DATA.meta.runner} · ${DATA.meta.image}`],
        ["Fork / threads", `${DATA.meta.forks ?? "?"} fork · ${DATA.meta.threads ?? "?"} thread`],
        ["Commit", DATA.meta.commitShort === "local" ? "local" : `${DATA.meta.commitShort} (${DATA.meta.branch})`],
        ["Generated", DATA.meta.generatedLabel],
      ];
      document.getElementById("envList").innerHTML = envRows
        .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd title="${escapeHtml(value)}">${escapeHtml(value)}</dd>`)
        .join("");

      const versionOrder = ["kotlin", "kotlinxSerialization", "moshi", "jackson", "gson", "jmh", "ksp"];
      const versionHtml = versionOrder
        .filter((key) => DATA.meta.versions[key])
        .map(
          (key) =>
            `<span class="version-pill">${escapeHtml(VERSION_LABELS[key] || key)} <strong>${escapeHtml(DATA.meta.versions[key])}</strong></span>`
        )
        .join("");
      document.getElementById("versionList").innerHTML = versionHtml;
    }

    const VERSION_LABELS = {
      kotlin: "Kotlin",
      ksp: "KSP",
      moshi: "Moshi",
      kotlinxSerialization: "kotlinx.serialization",
      jackson: "Jackson",
      gson: "Gson",
      jmh: "JMH",
    };

    function chartOptions(kind) {
      return {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 380 },
        layout: { padding: { right: 28 } },
        scales: {
          x: {
            type: "linear",
            grace: "5%",
            grid: { color: "rgba(148, 163, 184, 0.1)", drawBorder: false },
            border: { display: false },
            ticks: {
              color: "#64748b",
              font: { size: 10 },
              maxTicksLimit: 6,
              callback: (value) => formatCompact(value),
            },
            title: {
              display: true,
              text: kind === "ops" ? "operations / second" : "megabytes / second",
              color: "#64748b",
              font: { size: 10, weight: "600" },
            },
          },
          y: {
            grid: { display: false },
            border: { display: false },
            ticks: { color: "#cbd5e1", font: { size: 11, weight: "600" } },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(2, 6, 23, 0.97)",
            borderColor: "rgba(148, 163, 184, 0.2)",
            borderWidth: 1,
            titleColor: "#e2e8f0",
            bodyColor: "#cbd5e1",
            padding: 12,
            displayColors: false,
            callbacks: {
              label: (context) => {
                const row = currentRows[context.dataIndex];
                if (!row) return "";
                return [
                  `${formatNumber(row.opsPerSec)} ops/sec`,
                  `${formatMs(row.msPerOp)} per operation`,
                  `${formatNumber(row.mbPerSec)} MB/sec`,
                ];
              },
            },
          },
        },
      };
    }

    function initCharts() {
      opsChart = new Chart(document.getElementById("opsChart"), {
        type: "bar",
        data: { labels: [], datasets: [{ data: [], backgroundColor: [], borderRadius: 7, borderSkipped: false, barPercentage: 0.72 }] },
        options: chartOptions("ops"),
      });
      mbChart = new Chart(document.getElementById("mbChart"), {
        type: "bar",
        data: { labels: [], datasets: [{ data: [], backgroundColor: [], borderRadius: 7, borderSkipped: false, barPercentage: 0.72 }] },
        options: chartOptions("mb"),
      });
    }

    function render() {
      const size = sizeById[state.size];
      currentRows = DATA.rows
        .filter((row) => row.operation === state.operation && row.size === state.size)
        .sort((a, b) => b.opsPerSec - a.opsPerSec);

      const winner = currentRows[0];
      if (!winner) {
        document.getElementById("winnerName").textContent = "No data";
        return;
      }
      const winnerLibrary = byId[winner.libraryId];
      document.getElementById("winnerKicker").textContent =
        `Fastest ${state.operation.toLowerCase()} · ${size?.label ?? state.size}`;
      document.getElementById("winnerName").textContent = winnerLibrary.name;
      document.getElementById("winnerDetail").textContent =
        `${formatBytes(winner.payloadBytes)} payload · ${formatNumber(winner.opsPerSec)} ops/sec · ${formatMs(winner.msPerOp)} per operation`;
      document.getElementById("winnerNumbers").innerHTML = `
        <div class="winner-number"><span>ops / sec</span><strong>${formatNumber(winner.opsPerSec)}</strong></div>
        <div class="winner-number"><span>MB / sec</span><strong>${formatNumber(winner.mbPerSec)}</strong></div>
        <div class="winner-number"><span>± error</span><strong>${winner.errorPct.toFixed(1)}%</strong></div>
      `;

      const fastestNow = document.getElementById("fastestNow");
      if (fastestNow) {
        fastestNow.textContent = winnerLibrary.short;
        document.getElementById("fastestNowSub").textContent =
          `${state.operation} · ${size?.label ?? state.size}`;
      }

      const labels = currentRows.map((row) => byId[row.libraryId].name);
      const colors = currentRows.map((row) => byId[row.libraryId].color + "cc");
      const ops = currentRows.map((row) => row.opsPerSec);
      const mb = currentRows.map((row) => row.mbPerSec);

      [opsChart, mbChart].forEach((chart) => {
        chart.data.labels = labels;
        chart.data.datasets[0].data = chart === opsChart ? ops : mb;
        chart.data.datasets[0].backgroundColor = colors;
        chart.update();
      });

      document.getElementById("opsChip").textContent = `${state.operation} · ${size?.label ?? state.size}`;
      document.getElementById("mbChip").textContent = `${size?.label ?? state.size} · ${formatBytes(size?.jsonBytes)}`;
      document.getElementById("tableCaption").textContent =
        `${state.operation} · ${size?.label ?? state.size} payload · ${formatBytes(size?.jsonBytes)} · ${currentRows.length} libraries`;

      document.getElementById("resultsBody").innerHTML = currentRows
        .map((row, index) => {
          const library = byId[row.libraryId];
          return `
            <tr>
              <td><span class="rank ${index === 0 ? "rank-1" : ""}">${index + 1}</span></td>
              <td>
                <div class="lib">
                  <span class="swatch" style="background:${library.color}"></span>
                  <div>
                    <div class="lib-name">${escapeHtml(library.name)}</div>
                    <div class="lib-note">${escapeHtml(library.note)}</div>
                  </div>
                </div>
              </td>
              <td class="num">${formatNumber(row.opsPerSec)}</td>
              <td class="num">${formatMs(row.msPerOp)}</td>
              <td class="num">${formatNumber(row.mbPerSec)}</td>
              <td class="num muted-num">${row.errorPct.toFixed(1)}%</td>
            </tr>`;
        })
        .join("");
    }

    function wireControls() {
      document.querySelectorAll("#operationControl button").forEach((button) => {
        button.addEventListener("click", () => {
          state.operation = button.dataset.operation;
          syncControls();
          render();
        });
      });
    }

    buildStatGrid();
    buildSizeControl();
    buildPayloadGrid();
    buildMeta();
    initCharts();
    wireControls();
    syncControls();
    render();
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("build/results/jmh/results.json"))
    parser.add_argument("--payloads", type=Path, default=Path("build/results/jmh/payload-stats.json"))
    parser.add_argument("--out", type=Path, default=Path("site"))
    parser.add_argument("--versions", type=Path, default=Path("gradle/libs.versions.toml"))
    args = parser.parse_args()

    if not args.results.exists():
        raise SystemExit(f"JMH results not found: {args.results}")
    if not args.payloads.exists():
        raise SystemExit(f"Payload stats not found: {args.payloads}")

    results = json.loads(args.results.read_text(encoding="utf-8"))
    if not results:
        raise SystemExit("JMH results are empty")

    payloads, runtime = load_payload_stats(args.payloads)
    rows, sizes = build_rows(results, payloads)
    if not rows:
        raise SystemExit("No benchmark rows could be mapped")
    versions = read_versions(args.versions) if args.versions.exists() else {}
    meta = build_meta(results, versions, sizes, runtime)

    data = {
        "meta": meta,
        "libraries": LIBRARIES,
        "sizes": sizes,
        "rows": rows,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "data").mkdir(parents=True, exist_ok=True)
    (args.out / ".nojekyll").write_text("", encoding="utf-8")

    data_json = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False).replace("</", "<\\/")
    (args.out / "data" / "results.json").write_text(data_json + "\n", encoding="utf-8")
    (args.out / "data" / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    shutil.copyfile(args.results, args.out / "data" / "raw-jmh.json")
    shutil.copyfile(args.payloads, args.out / "data" / "payload-stats.json")

    embedded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("__DATA_JSON__", embedded)
    (args.out / "index.html").write_text(html, encoding="utf-8")

    print(f"Wrote {args.out / 'index.html'}")
    print(f"  rows: {len(rows)}")
    print(f"  libraries: {len(LIBRARIES)}")
    size_summary = ", ".join(
        "{} users / {} B".format(size["userCount"], size["jsonBytes"]) for size in sizes
    )
    print(f"  sizes: {size_summary}")


if __name__ == "__main__":
    main()

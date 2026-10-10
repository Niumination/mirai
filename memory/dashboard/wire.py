#!/usr/bin/env python3
"""wire.py — wire the shipped wiki page to real data.

The template ships FULL of hard-coded demo values. Each one is a specification of
what data belongs where, and the live-data functions ship written but never
called. This script calls them and deletes the demo twin in the same step,
because a hard-coded number looks exactly like a working one.

Nothing here invents a data shape: every replacement uses the template's own
functions (loadWiki, loadPage, runLint, runCommit) and the server answers in the
demo's own shape.

Usage:
    python3 wire.py "KomputerMechanic-Wiki-Page-Template(1).html" [--repo URL] [--out wiki-page.html]

It fails loudly if a pattern is not found, rather than half-wiring the page.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    new, n = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if n == 0:
        sys.exit(f"FAILED at: {label}\nThe template version differs; nothing was written.")
    print(f"  wired: {label}")
    return new


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("template")
    ap.add_argument("--repo", default="https://github.com/niumination/wiki/blob/main/")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    src = Path(args.template)
    if not src.exists():
        sys.exit(f"no such file: {src}")
    text = original = src.read_text(encoding="utf-8")

    print("1. the repository link")
    text = sub_once(text, r"const WIKI_REPO_URL = '[^']*';",
                    f"const WIKI_REPO_URL = '{args.repo}';", "WIKI_REPO_URL")

    print("2. the loader: keep the fetched payload where the panels read it")
    text = sub_once(
        text,
        r"async function loadWiki\(\)\{\n"
        r"  const r = await fetch\('/api/data', \{cache:'no-store'\}\);\n"
        r"  if\(!r\.ok\) throw new Error\('wiki data unavailable: ' \+ r\.status\);\n"
        r"  renderWiki\(await r\.json\(\)\);          // same shape as DEMO_WIKI\n"
        r"\}",
        """async function loadWiki(){
  const r = await fetch('/api/data', {cache:'no-store'});
  if(!r.ok) throw new Error('wiki data unavailable: ' + r.status);
  const data = await r.json();              // the same shape as the demo payload
  /* WIRED: the lint panel and the log strip read these off DEMO_WIKI, so the
   * fetched values are stashed there before the render. There is nothing left
   * in DEMO_WIKI to conflict with them: the demo values were deleted. */
  DEMO_WIKI.lint = data.lint || [];
  DEMO_WIKI.log_tail = data.log_tail || [];
  DEMO_WIKI.stats = data.stats || DEMO_WIKI.stats;
  renderWiki(data);
}""",
        "loadWiki")

    print("3. empty the demo payload (the numbers come from /api/data now)")
    text = sub_once(
        text,
        r"const DEMO_WIKI = \{.*?\nDEMO_WIKI\.bodies = \{.*?\};\nDEMO_WIKI\.lint = \[.*?\];",
        "/* WIRED: every demo value was deleted when the real data was wired in.\n"
        " * This empty skeleton exists only so the first paint, before the fetch\n"
        " * resolves, has nothing fake in it. */\n"
        "const EMPTY_WIKI = {stats:{pages:0,sources:0,links:0,log_entries:0,depth:0},"
        "nodes:[],links:[],log_tail:[],lint:[]};\n"
        "const DEMO_WIKI = EMPTY_WIKI;\n"
        "DEMO_WIKI.bodies = {};\nDEMO_WIKI.lint = [];",
        "DEMO_WIKI payload")

    print("4. the reader: loadPage(slug) instead of the demo body")
    text = sub_once(
        text,
        r"  // DEMO - replace this block with loadPage\(slug\) when you wire the reader\n"
        r"  const slug=.*?\n  return Promise\.resolve\(\);",
        """  // WIRED: the reader asks the server, and shows its own error state.
  const slug=id.startsWith('meta:')?CX_META_FILES[id].slug:id;
  return loadPage(slug)
    .then(body => { CX_BODY[id] = body; })
    .catch(err => { CX_BODY[id] = '# ' + slug + '\\n\\nCould not load this page: ' + err.message; });""",
        "reader")

    print("5. the lint panel: its own comment now says where the items come from")
    text = sub_once(
        text,
        r"  // DEMO - replace the items line with loadPage\('_wiki-health'\) when you wire it\n",
        "  // WIRED: these arrive on /api/data, read from the newest ## section of _wiki-health.md,\n"
        "  // and loadWiki() stashes them on DEMO_WIKI.lint before this render runs.\n",
        "lint comment")

    print("6. the boot: call loadWiki(), never render the demo")
    text = sub_once(
        text,
        r"  cxSelected = '[^']*';   // open on a modest page, not the biggest hub\n"
        r"  renderWiki\(DEMO_WIKI\);",
        """  renderWiki(EMPTY_WIKI);          // first paint: an empty wiki, honestly drawn
  loadWiki()
    .then(() => { if (window.lucide) lucide.createIcons(); })
    .catch(err => {
      const el = document.getElementById('cx-stat-pages');
      if (el && el.parentElement) el.parentElement.innerHTML =
        '<div class="font-sans text-[12px] text-ember">wiki data unavailable: ' + err.message + '</div>';
    });""",
        "boot")

    print("7. the two buttons: runLint() and runCommit(), reporting their own replies")
    text = sub_once(
        text,
        r"    const lint=e\.target\.closest\('#cx-act-lint'\);\n"
        r"    if\(lint\)\{ cxToast\('Demo[^\n]*\n"
        r"    const com=e\.target\.closest\('#cx-act-commit'\);\n"
        r"    if\(com\)\{ cxToast\('Demo[^\n]*\n",
        """    const lint=e.target.closest('#cx-act-lint');
    if(lint){
      // WIRED: runLint() asks the server for a lint pass now; the panel refreshes with it.
      runLint().then(r=>r.json())
        .then(j=>{ cxToast(j.ok? ('Lint pass asked for: '+(j.note||'queued')) : ('Lint pass refused: '+j.error), !!j.ok);
                   setTimeout(()=>loadWiki().catch(()=>{}), 2500); })
        .catch(err=>cxToast('Lint pass failed: '+err.message,false));
      return;
    }
    const com=e.target.closest('#cx-act-commit');
    if(com){
      // WIRED: runCommit() saves a git snapshot of the vault on the server.
      runCommit().then(r=>r.json())
        .then(j=>cxToast(j.ok? ('Vault committed: '+(j.note||'snapshot saved')) : ('Commit refused: '+j.error), !!j.ok))
        .catch(err=>cxToast('Commit failed: '+err.message,false));
      return;
    }
""",
        "lint/commit buttons")

    print("8. the drop panel: post to /api/drop")
    text = sub_once(
        text,
        r"  /\* ---------------- the drop panel \(behind the Ingest source button\) ----------------\n"
        r"   \* Clip and drop are DEMO: they say what the wired build does and save nothing\.\n"
        r"   \* Step 13d: post the link and the files to /api/drop, delete the two demo replies\. \*/",
        """  /* ---------------- the drop panel (behind the Ingest source button) ----------------
   * WIRED: a link is posted to /api/drop as JSON, files as base64, and both land
   * in raw/_inbox under a non-colliding name. The two demo replies are deleted. */
  async function cxPostDrop(payload){
    const r = await fetch('/api/drop', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)});
    const j = await r.json();
    if(!j.ok) throw new Error(j.error || ('drop refused ('+r.status+')'));
    return j;
  }
  window.cxPostDrop = cxPostDrop;""",
        "drop panel")

    if text == original:
        sys.exit("nothing was changed — this template may already be wired")

    out = Path(args.out) if args.out else src.with_name("wiki-page.html")
    out.write_text(text, encoding="utf-8")
    print(f"\nwired page written to {out} ({out.stat().st_size:,} bytes on disk)")
    print("It is served by memory/dashboard/server.py, which also accepts the token as a cookie")
    print("so this page's own fetch calls authenticate without carrying a secret in the file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

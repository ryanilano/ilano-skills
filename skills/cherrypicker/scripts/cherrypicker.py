#!/usr/bin/env python3
"""
cherrypicker: merge two drafts of the same piece, one decision per section.

Two subcommands:

  units   Split each document into labelled units so you can decide the alignment.
          Prints an indexed list per file. Nothing is guessed for you here on
          purpose: choosing which section of A answers which section of B is the
          judgment call the human is actually paying for.

  build   Take an alignment spec (JSON) and emit one self-contained HTML page:
          rows of paired copy, a picker per row, autosave into the URL hash,
          and a markdown export of the decisions.

Usage:
  python cherrypicker.py units  A.mdx B.mdx
  python cherrypicker.py build  A.mdx B.mdx --align align.json --out merge.html \
                              --label-a "Draft" --label-b "Rewrite" --title "Copy merge"

Alignment spec format (list of rows, each row names units by index):

  [
    {"title": "The opening pitch",  "a": [0],       "b": [0]},
    {"title": "The security story", "a": [],        "b": [7, 8, 9]},
    {"title": "Proof links",        "a": [9],       "b": [19]}
  ]

An empty list means "this file has nothing for this row" and renders as a
one-sided row, which is usually the most interesting thing on the page.

Requires: pip install markdown
"""

import argparse
import html
import json
import os
import re
import sys

try:
    import markdown as _markdown
except ImportError:
    sys.exit("Missing dependency. Run:  pip install markdown")


# ---------------------------------------------------------------- parsing

# Wrapper JSX/HTML that structures a page but carries no copy. Dropping these
# keeps the comparison about words rather than layout.
_WRAPPER = re.compile(
    r'^\s*(</?(TwoColumn|Columns|Row|Grid|Section)>'
    r'|<div[^>]*>|</div>|<section[^>]*>|</section>)\s*$'
)

# Components that wrap a quotable chunk of copy. Their contents are a unit of
# their own because a pull quote is a distinct editorial decision, not a
# paragraph of the section it happens to sit in.
_QUOTE_TAGS = ('PullQuote', 'Blockquote', 'Callout', 'Aside', 'Note')


def parse_units(path):
    """Split a markdown/MDX document into an ordered list of copy units."""
    with open(path, encoding='utf-8') as fh:
        text = fh.read()

    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S)      # frontmatter
    text = re.sub(r'^import .*$\n?', '', text, flags=re.M)        # MDX imports
    text = re.sub(r'^export .*$\n?', '', text, flags=re.M)
    text = re.sub(r'\{/\*.*?\*/\}', '', text, flags=re.S)         # MDX comments

    quote_open = re.compile(r'^\s*<(' + '|'.join(_QUOTE_TAGS) + r')([^>]*)>')
    lines = text.split('\n')
    units, cur = [], None

    def start(kind, label):
        nonlocal cur
        cur = {'kind': kind, 'label': label, 'body': []}
        units.append(cur)

    i = 0
    while i < len(lines):
        line = lines[i]

        if _WRAPPER.match(line):
            i += 1
            continue

        # Headings may be indented inside JSX. MDX disables indented code
        # blocks, so a leading run of spaces here is layout, not syntax.
        heading = re.match(r'^\s{0,7}(#{2,4})\s+(.*)$', line)
        if heading:
            start('h%d' % len(heading.group(1)), heading.group(2).strip())
            i += 1
            continue

        quote = quote_open.match(line)
        if quote:
            tag = quote.group(1)
            body = [line.lstrip()]
            i += 1
            while i < len(lines) and ('</%s>' % tag) not in lines[i]:
                body.append(lines[i])
                i += 1
            if i < len(lines):
                body.append(lines[i])
                i += 1
            start('quote', tag)
            cur['body'] = body
            start('text', '(continues)')   # prose after the quote stands alone
            continue

        if cur is None:
            start('text', '(opening)')
        cur['body'].append(line)
        i += 1

    for u in units:
        body = '\n'.join(u['body']) if isinstance(u['body'], list) else u['body']
        body = re.sub(r'\n{3,}', '\n\n', body).strip()
        # Strip one level of layout indentation so markdown parses normally.
        body = '\n'.join(l[4:] if l.startswith('    ') else l for l in body.split('\n'))
        u['body'] = body

    return [u for u in units if u['body'] or u['kind'].startswith('h')]


def render_unit(unit):
    md = _markdown.Markdown(extensions=['tables', 'fenced_code', 'sane_lists'])
    body = re.sub(r'</?(' + '|'.join(_QUOTE_TAGS) + r')[^>]*>', '', unit['body']).strip()
    out = md.convert(body)
    # Copy sits under the row's h2 and the unit's h3, so its own headings start at h4.
    return re.sub(r'<(/?)h([1-6])\b',
                  lambda m: '<%sh%d' % (m.group(1), min(int(m.group(2)) + 3, 6)), out)


# ---------------------------------------------------------------- template

_CSS = """
/* Palette from the author's editorial docs: cream and ink in light, navy and
   amber in dark. Follows the system; data-theme="light|dark" on <html>
   overrides it (the Theme button sets that and remembers it). */
:root{
  color-scheme:light dark;
  --bg:#FBF8F1; --surface:#F2EDDF; --surface-2:#F7F3E8; --hover:#EAE3D1;
  --ink:#24211A; --ink-2:#514A38; --muted:#6B6450;
  --rule:#DCD3BE; --rule-2:#C7BCA2;
  --accent-text:#8A5300; --focus:#1D4ED8; --bar:#3468C0;
  --a-ink:#1f5fcf; --b-ink:#6f42c1; --ok-ink:#15693d; --rw-ink:#a34a07; --cut-ink:#b3321f;
  --bar-bg:rgba(251,248,241,.92);
  --a:#1f6feb; --b:#6f42c1; --ok:#1a7f4b; --rw:#b45309; --cut:#c0392b;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#101523; --surface:#182034; --surface-2:#141b2c; --hover:#1f2942;
    --ink:#EDE9DE; --ink-2:#C6BFAB; --muted:#A8A08B;
    --rule:#2B3450; --rule-2:#3d486b;
    --accent-text:#F5A83C; --focus:#F5A83C; --bar:#5FA0EA;
    --a-ink:#79a8ff; --b-ink:#b392f0; --ok-ink:#4cc38a; --rw-ink:#f5a83c; --cut-ink:#ff8a7a;
    --bar-bg:rgba(16,21,35,.9);
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#101523; --surface:#182034; --surface-2:#141b2c; --hover:#1f2942;
  --ink:#EDE9DE; --ink-2:#C6BFAB; --muted:#A8A08B;
  --rule:#2B3450; --rule-2:#3d486b;
  --accent-text:#F5A83C; --focus:#F5A83C; --bar:#5FA0EA;
  --a-ink:#79a8ff; --b-ink:#b392f0; --ok-ink:#4cc38a; --rw-ink:#f5a83c; --cut-ink:#ff8a7a;
  --bar-bg:rgba(16,21,35,.9);
}
:root[data-theme="light"]{color-scheme:light}

*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-padding-top:5rem}
body{margin:0;background:var(--bg);color:var(--ink);
  font:1rem/1.6 ui-sans-serif,-apple-system,"SF Pro Text",Inter,system-ui,sans-serif;
  padding-bottom:6rem}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:2px}
.skip{position:absolute;left:-9999px;top:0;background:var(--ink);color:var(--bg);
  padding:.6rem 1rem;z-index:100}
.skip:focus{left:1rem;top:1rem}

.hero{max-width:61.25rem;margin:0 auto;padding:2rem 1rem 0;text-align:center}
.hero h1{font-family:ui-serif,"Iowan Old Style","Times New Roman",Georgia,serif;
  font-weight:700;letter-spacing:-.02em;line-height:1.08;
  font-size:clamp(1.7rem,4.6vw,3rem);margin:0 0 .6rem}
.hero .kicker{color:var(--muted);font-size:.9rem;margin:0 0 1.4rem}
.impact-band{display:grid;grid-template-columns:repeat(auto-fit,minmax(11.25rem,1fr));
  gap:2rem 1rem;padding:2rem 3rem;margin:0 auto;max-width:61.25rem;
  background:var(--surface);border:1px solid var(--rule);border-radius:5px}
.metric-item{display:flex;flex-direction:column-reverse;text-align:center;min-width:0}
.metric-value{margin:0 0 .5rem;font-family:ui-serif,"Iowan Old Style","Times New Roman",Georgia,serif;
  font-size:clamp(2rem,5vw,3.1rem);line-height:1.05;font-weight:400;color:var(--ink);
  font-variant-numeric:tabular-nums}
.metric-label{color:var(--ink-2);max-width:20rem;margin:0 auto;font-size:.875rem;line-height:1.5}
.metric-item[data-k="a"] .metric-value{color:var(--a-ink)}
.metric-item[data-k="b"] .metric-value{color:var(--b-ink)}
.metric-item[data-k="left"] .metric-value{color:var(--muted)}

.bar{position:sticky;top:0;z-index:50;background:var(--bar-bg);
  -webkit-backdrop-filter:saturate(1.6) blur(10px);backdrop-filter:saturate(1.6) blur(10px);
  border-bottom:1px solid var(--rule);margin-top:1.6rem;
  padding:.55rem max(1rem,env(safe-area-inset-left));
  display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}
.bar progress{flex:1;min-width:7.5rem;height:.375rem;border:0;border-radius:99px;
  overflow:hidden;background:var(--surface);-webkit-appearance:none;appearance:none}
.bar progress::-webkit-progress-bar{background:var(--surface);border-radius:99px}
.bar progress::-webkit-progress-value{background:linear-gradient(90deg,var(--bar),var(--ok));border-radius:99px}
.bar progress::-moz-progress-bar{background:linear-gradient(90deg,var(--bar),var(--ok))}
.count{font-variant-numeric:tabular-nums;color:var(--ink-2);font-size:.8rem;white-space:nowrap}
.bar .acts{display:flex;gap:.4rem;margin-left:auto;flex-wrap:wrap}
.bar button{background:var(--surface);color:var(--ink);border:1px solid var(--rule);
  border-radius:8px;padding:.4rem .7rem;font:inherit;font-size:.8rem;cursor:pointer;line-height:1.4;
  -webkit-tap-highlight-color:transparent}
.bar button:hover{border-color:var(--rule-2);background:var(--hover)}
#btn-save.need{border-color:var(--rw);color:var(--accent-text);font-weight:600}
#btn-save.need::after{content:" \u25cf"}
.saved{color:var(--ok-ink);font-size:.75rem;visibility:hidden}
.saved.on{visibility:visible}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}

main{padding:1.25rem max(1rem,env(safe-area-inset-left))}
.row{background:var(--bg);border:1px solid var(--rule);border-radius:14px;
  box-shadow:0 1px 2px rgba(0,0,0,.06);margin:0 0 1.1rem;overflow:hidden;scroll-margin-top:4.375rem}
.row-h{position:relative;display:flex;align-items:center;gap:1rem;flex-wrap:wrap;
  padding:.8rem 1rem;background:var(--surface);border-bottom:1px solid var(--rule)}
.row-h h2{margin:0;font-weight:500;font-size:.95rem;letter-spacing:-.01em;
  font-family:ui-monospace,SFMono-Regular,Menlo,"Courier New",monospace;
  background:var(--ink);color:var(--bg);padding:.25rem .6rem;border-radius:3px;
  text-transform:lowercase}
.picker{display:flex;gap:.5rem;margin-left:auto;flex-wrap:wrap}
.picker button{width:7.5rem;min-height:2.375rem;border:2px solid var(--k-ink);border-radius:5px;
  padding:.2rem .4rem;font:inherit;font-size:.8rem;font-weight:600;cursor:pointer;
  background:var(--bg);color:var(--k-ink);transition:box-shadow .15s;
  -webkit-tap-highlight-color:transparent}
.picker button:hover{background:var(--hover)}
.picker [data-p="a"]{--k:var(--a);--k-ink:var(--a-ink);
  position:absolute;top:50%;right:50%;margin-right:.3rem;transform:translateY(-50%)}
.picker [data-p="b"]{--k:var(--b);--k-ink:var(--b-ink);
  position:absolute;top:50%;left:50%;margin-left:.3rem;transform:translateY(-50%)}
.picker [data-p="y"]{--k:var(--ok);--k-ink:var(--ok-ink)}
.picker [data-p="r"]{--k:var(--rw);--k-ink:var(--rw-ink)}
.picker [data-p="n"]{--k:var(--cut);--k-ink:var(--cut-ink)}
.picker button[aria-pressed="true"]{background:var(--k);border-color:var(--k);color:#fff;
  box-shadow:0 0 0 2px var(--bg),0 0 0 4px var(--ink)}

/* Both panel */
.panel{display:none;padding:.9rem 1rem;background:var(--surface-2);border-bottom:1px solid var(--rule)}
.row.open .panel{display:block}
.modes{display:none;border:0;padding:0;margin:0 0 .8rem;min-width:0}
.row.combine .modes{display:block}
.panel legend,.panel .note-l{display:block;padding:0;margin:0 0 .5rem;font-size:.72rem;
  font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
.mode-btns{display:flex;gap:.4rem;flex-wrap:wrap}
.modes button{background:var(--bg);border:1px solid var(--rule);border-radius:99px;
  padding:.35rem .8rem;font:inherit;font-size:.78rem;color:var(--ink-2);cursor:pointer}
.modes button:hover{border-color:var(--rule-2);color:var(--ink)}
.modes button[aria-pressed="true"]{background:var(--ok);border-color:var(--ok);color:#fff;font-weight:600}
.modes .hint{font-size:.78rem;color:var(--ink-2);margin:.5rem 0 0}
.panel .rec{font-size:.85rem;color:var(--ink-2);background:var(--bg);border:1px solid var(--rule);
  border-left:3px solid var(--muted);border-radius:4px;padding:.55rem .7rem;margin:0 0 .8rem}
.panel .lead{display:inline-block;margin-left:.5rem;padding:.1rem .5rem;border-radius:99px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink-2);font-size:.7rem;
  font-weight:600;letter-spacing:.02em;text-transform:uppercase;vertical-align:.08em}
.panel .chip{display:inline-block;margin-right:.5rem;padding:.15rem .6rem;border-radius:4px;
  color:#fff;font-size:.72rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;
  vertical-align:.05em}
.panel .chip[data-c="a"]{background:var(--a)}
.panel .chip[data-c="b"]{background:var(--b)}
.panel .chip[data-c="y"]{background:var(--ok)}
.panel .chip[data-c="r"]{background:var(--rw)}
.panel .chip[data-c="n"]{background:var(--cut)}
.panel textarea{width:100%;min-height:4.75rem;background:var(--bg);color:var(--ink);
  border:1px solid var(--rule);border-radius:6px;padding:.55rem .7rem;
  font:inherit;font-size:.88rem;resize:vertical}
.panel textarea::placeholder{color:var(--muted);opacity:1}
@media (max-width:35em){ .picker button{width:4rem;min-height:2.125rem} }

.cols{display:grid;grid-template-columns:1fr 1fr}
.col{padding:.9rem 1rem;min-width:0}
.col[data-state="out"]{background:var(--surface-2)}
.col-h{display:flex;gap:.6rem;align-items:baseline;margin:0 0 .6rem;font-size:.78rem}
.col-name{font-weight:700;color:var(--ink)}
.col[data-side="a"] .col-name{color:var(--a-ink)}
.col[data-side="b"] .col-name{color:var(--b-ink)}
.col-state{color:var(--ink-2);font-weight:600;text-transform:uppercase;letter-spacing:.06em;font-size:.7rem}
.col-state:empty{display:none}
.col+.col{border-left:1px solid var(--rule)}
.col[data-side="a"]{border-top:3px solid var(--a)}
.col[data-side="b"]{border-top:3px solid var(--b)}
.col.empty .none{padding:1rem 0;text-align:center}
.none{color:var(--muted);font-style:italic;font-size:.85rem;margin:0}
.blk+.blk{margin-top:1rem;padding-top:1rem;border-top:1px dashed var(--rule)}
.blk-h{margin:0 0 .45rem;font-size:.7rem;font-weight:500;text-transform:uppercase;
  letter-spacing:.07em;color:var(--muted);display:flex;gap:.5rem;align-items:baseline}
.cc{margin-left:auto;font-variant-numeric:tabular-nums}
.prose{font-size:.93rem;color:var(--ink-2)}
.prose p{margin:0 0 .7rem}
.prose p:last-child{margin-bottom:0}
.prose strong{color:var(--ink);font-weight:640}
.prose a{color:var(--accent-text);text-decoration:underline;text-underline-offset:.15em}
.prose h2,.prose h3,.prose h4{font-size:.9rem;margin:.9rem 0 .4rem;color:var(--ink)}
.prose ul,.prose ol{margin:0 0 .7rem;padding-left:1.2rem}
.prose li{margin-bottom:.25rem}
.prose code{background:var(--surface);border:1px solid var(--rule);border-radius:4px;
  padding:.08em .35em;font-size:.85em;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.prose pre{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:.7rem;overflow:auto}
.prose pre code{border:0;background:none;padding:0}
.prose blockquote{margin:.6rem 0;padding-left:.8rem;border-left:3px solid var(--rule);color:var(--ink-2)}
.prose table{width:100%;border-collapse:collapse;font-size:.78rem;margin:0 0 .7rem;display:block;overflow-x:auto}
.prose th,.prose td{border:1px solid var(--rule);padding:.35rem .5rem;text-align:left;vertical-align:top}
.prose th{background:var(--surface);color:var(--ink);font-weight:600}
.prose img{max-width:100%}

@media (max-width:51.25em){
  .cols{grid-template-columns:1fr}
  .col+.col{border-left:0;border-top:3px solid var(--b)}
  .row-h h2{width:100%}
  .picker{margin-left:0}
}
/* Centred A/B buttons collide with Both/Rewrite/Cut below ~1060px (measured:
   B sits under Both at 834 and 1024), so they rejoin the flex row there. */
@media (max-width:67.5em){
  .picker [data-p="a"],.picker [data-p="b"]{position:static;transform:none;margin:0}
}

@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{transition:none!important;scroll-behavior:auto!important}
}
@media (forced-colors:active){
  .picker button[aria-pressed="true"],.modes button[aria-pressed="true"]{
    outline:3px solid Highlight;outline-offset:2px}
  .bar progress{border:1px solid CanvasText}
}

dialog{background:var(--bg);color:var(--ink);border:1px solid var(--rule);
  border-radius:14px;padding:0;max-width:min(42.5rem,92vw);width:100%}
dialog::backdrop{background:#0006;backdrop-filter:blur(2px)}
.dlg-h{display:flex;align-items:center;gap:1rem;padding:.8rem 1rem;border-bottom:1px solid var(--rule)}
.dlg-h h2{margin:0;font-size:.95rem}
.dlg-h button{background:var(--surface);color:var(--ink);border:1px solid var(--rule);
  border-radius:8px;padding:.4rem .7rem;font:inherit;font-size:.8rem;cursor:pointer}
.dlg-b{padding:1rem;max-height:60vh;overflow:auto}
.dlg-b textarea{width:100%;min-height:16.25rem;background:var(--surface);color:var(--ink);
  border:1px solid var(--rule);border-radius:8px;padding:.7rem;
  font:.8125rem/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;resize:vertical}
"""

# Picks live in the URL hash rather than localStorage: artifact sandboxes block
# storage APIs, and a hash doubles as a shareable "here's where I got to" link.
_JS = r"""
const TITLES = __TITLES__;
const RECS   = __RECS__;
const WINS   = __WINS__;
const LA = __LA__, LB = __LB__;
const N = TITLES.length;
const BOTH = ['y','u','g','f','s'];
const MODE = {u:'Union', g:'Graft', f:'Form plus facts', s:'Sequence', r:'Rewrite'};
const LABEL = {a:LA, b:LB, y:'Both, mode not set', r:'Rewrite', n:'Cut',
               u:'Both, union. You edit',
               g:'Both, graft',
               f:'Both, form plus facts',
               s:'Both, sequence. You pick the order'};
let picks = new Array(N).fill('-');
let notes = new Array(N).fill('');
let handle = null, dirty = false;

/* ---- persistence: hot-saved into the URL hash (picks and notes) and mirrored
   to localStorage where the browser allows it; Save notes writes a file ---- */
const LS_KEY = 'cherrypicker:' + location.pathname;
function b64e(s){
  return btoa(unescape(encodeURIComponent(s))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
}
function b64d(s){
  return decodeURIComponent(escape(atob(s.replace(/-/g,'+').replace(/_/g,'/'))));
}
function readHash(){
  const h = location.hash||'';
  const m = /[#&]p=([abyugfsrn\-]+)/.exec(h);
  if(m && m[1].length===N) picks = m[1].split('');
  const n = /[#&]n=([A-Za-z0-9_\-]+)/.exec(h);
  if(n){
    try{ const a=JSON.parse(b64d(n[1])); if(Array.isArray(a) && a.length===N) notes=a; }catch(e){}
  }
  return !!m;
}
function readLocal(){
  try{
    const j = JSON.parse(localStorage.getItem(LS_KEY)||'null');
    if(!j) return;
    if(j.picks && j.picks.length===N) picks=j.picks.split('');
    if(Array.isArray(j.notes) && j.notes.length===N) notes=j.notes;
  }catch(e){}
}
function writeHash(){
  let h = '#p='+picks.join('');
  if(notes.some(x=>x)) h += '&n='+b64e(JSON.stringify(notes));
  history.replaceState(null,'',location.pathname+location.search+h);
  try{ localStorage.setItem(LS_KEY, payload()); }catch(e){}
  flash('saved');
}
function announce(t){
  const el=document.getElementById('live');
  el.textContent=''; setTimeout(()=>{ el.textContent=t; },50);
}
function flash(t){
  const el=document.getElementById('saved');
  el.textContent=t; el.classList.add('on');
  clearTimeout(flash._t); flash._t=setTimeout(()=>el.classList.remove('on'),1100);
}
function payload(){
  return JSON.stringify({v:2, picks:picks.join(''), notes:notes, titles:TITLES}, null, 2);
}
async function save(){
  // Once a file is chosen, every hot save also writes it. Without one, the
  // URL hash and localStorage already hold everything, so nothing is lost.
  if(!handle) return;
  try{
    const w = await handle.createWritable();
    await w.write(payload()); await w.close();
    dirty=false; flash('saved to file'); announce('Notes saved to file');
  }catch(e){
    handle=null; dirty=true;
    document.getElementById('btn-save').classList.add('need');
  }
}
let saveT;
function autosave(){ clearTimeout(saveT); saveT=setTimeout(()=>{ writeHash(); save(); },400); }

document.getElementById('btn-save').addEventListener('click', async ()=>{
  if(window.showSaveFilePicker){
    try{
      handle = await window.showSaveFilePicker({
        suggestedName: (location.pathname.split('/').pop()||'cherrypicker').replace(/\.html?$/,'') + '.notes.json',
        types:[{description:'Notes', accept:{'application/json':['.json']}}]
      });
      await save();
      document.getElementById('btn-save').classList.remove('need');
      return;
    }catch(e){ if(e && e.name==='AbortError') return; }
  }
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([payload()],{type:'application/json'}));
  a.download=(location.pathname.split('/').pop()||'cherrypicker').replace(/\.html?$/,'')+'.notes.json';
  a.click(); URL.revokeObjectURL(a.href);
  dirty=false; document.getElementById('btn-save').classList.remove('need');
  flash('downloaded'); announce('Notes downloaded');
});
document.getElementById('btn-load').addEventListener('click', ()=>document.getElementById('file-load').click());
document.getElementById('file-load').addEventListener('change', ev=>{
  const f=ev.target.files[0]; if(!f) return;
  const rd=new FileReader();
  rd.onload=()=>{
    try{
      const j=JSON.parse(rd.result);
      if(j.picks && j.picks.length===N) picks=j.picks.split('');
      if(Array.isArray(j.notes) && j.notes.length===N) notes=j.notes;
      paint(); writeHash(); flash('loaded'); announce('Notes loaded');
    }catch(e){ alert('Could not read that file.'); }
  };
  rd.readAsText(f); ev.target.value='';
});
window.addEventListener('beforeunload', e=>{ if(dirty){ e.preventDefault(); e.returnValue=''; } });

/* ---- painting ---- */
function colState(p, side){
  if(p==='-') return '';
  if(p==='a' || p==='b') return p===side ? 'Chosen' : 'Not chosen';
  if(p==='r') return 'To rewrite';
  if(p==='n') return 'Cut';
  return 'Combined';
}
function paint(){
  document.querySelectorAll('.row').forEach(r=>{
    const i=+r.dataset.row, p=picks[i];
    if(p==='-') r.removeAttribute('data-pick'); else r.dataset.pick=p;
    r.classList.toggle('open', p!=='-');
    r.classList.toggle('combine', BOTH.indexOf(p)>=0);
    r.querySelectorAll('.picker button').forEach(b=>{
      const on = b.dataset.p===p || (b.dataset.p==='y' && BOTH.indexOf(p)>=0);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    r.querySelectorAll('.modes button').forEach(b=>{
      b.setAttribute('aria-pressed', b.dataset.m===p ? 'true' : 'false');
    });
    r.querySelectorAll('.col').forEach(c=>{
      const side=c.dataset.side, st=colState(p, side);
      c.dataset.state = st==='Chosen' ? 'in' : (st ? 'out' : '');
      if(st==='Combined') c.dataset.state='in';
      c.querySelector('.col-state').textContent=st;
    });
    const ta=r.querySelector('.panel textarea');
    if(ta && ta.value!==notes[i]) ta.value=notes[i];
  });
  const done=picks.filter(p=>p!=='-').length;
  document.getElementById('count').textContent=done+' / '+N;
  document.getElementById('bar').value=done;
  const na=picks.filter(p=>p==='a').length, nb=picks.filter(p=>p==='b').length;
  document.getElementById('m-a').textContent=na;
  document.getElementById('m-b').textContent=nb;
  document.getElementById('m-left').textContent=N-na-nb;
}

/* ---- picking ---- */
document.querySelectorAll('.picker button').forEach(b=>{
  b.addEventListener('click', ()=>{
    const row=b.closest('.row'), i=+row.dataset.row, v=b.dataset.p;
    if(v==='y'){
      // Both opens the panel. Clicking it again with no mode chosen clears the row.
      picks[i] = (picks[i]==='y') ? '-' : (BOTH.indexOf(picks[i])>=0 ? picks[i] : 'y');
      if(BOTH.indexOf(picks[i])>=0) row.classList.add('open');
    } else {
      picks[i] = (picks[i]===v) ? '-' : v;
    }
    paint(); writeHash();
  });
});
document.querySelectorAll('.modes button').forEach(b=>{
  b.addEventListener('click', ()=>{
    const i=+b.closest('.row').dataset.row, m=b.dataset.m;
    picks[i] = (picks[i]===m) ? 'y' : m;
    paint(); writeHash();
  });
});
document.querySelectorAll('.panel textarea').forEach(ta=>{
  ta.addEventListener('input', ()=>{
    notes[+ta.closest('.row').dataset.row]=ta.value;
    autosave();
  });
});

/* ---- nav ---- */
document.getElementById('btn-next').addEventListener('click', ()=>{
  const i=picks.findIndex(p=>p==='-');
  if(i<0){ announce('Every section is decided'); return; }
  const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.getElementById('r'+i).scrollIntoView({behavior: calm ? 'auto' : 'smooth', block:'start'});
  document.getElementById('r'+i+'-t').focus({preventScroll:true});
});
document.getElementById('btn-clear').addEventListener('click', ()=>{
  if(!confirm('Clear all picks and notes?')) return;
  picks=new Array(N).fill('-'); notes=new Array(N).fill('');
  paint(); writeHash(); autosave(); announce('All picks and notes cleared');
});

/* ---- export ---- */
function colText(i, side){
  const el=document.querySelector('#r'+i+' .col[data-side="'+side+'"]');
  if(!el || el.classList.contains('empty')) return '(not in this file)';
  return Array.from(el.querySelectorAll('.blk')).map(b=>b.innerText).join('\n\n')
    .replace(/\n{3,}/g,'\n\n').trim();
}
document.getElementById('btn-out').addEventListener('click', ()=>{
  let t='# Copy merge, decisions\n\n';
  const order=['a','b','g','f','r','n','u','s','y','-'];
  const g={}; order.forEach(k=>g[k]=[]);
  picks.forEach((p,i)=>{ (g[p]||g['-']).push(i); });

  for(const k of ['a','b','g','f','r','n','y']){
    if(!g[k].length) continue;
    t+='## '+LABEL[k]+'\n';
    g[k].forEach(i=>{
      t+='- '+TITLES[i]+(notes[i]?'\n  - '+notes[i].replace(/\n/g,'\n    '):'')+'\n';
    });
    t+='\n';
  }
  if(g['-'].length){
    t+='## Undecided\n';
    g['-'].forEach(i=>t+='- '+TITLES[i]+'\n');
    t+='\n';
  }

  const combos=g['u'].concat(g['s'],g['g'],g['f'],g['r']).sort((x,y)=>x-y);
  if(combos.length){
    t+='---\n\n# Source text, ready to edit\n\n';
    t+='Every row that needs writing rather than choosing. The side in **bold** leads, where one does. Union, Sequence and Rewrite are yours to edit.\n\n';
    combos.forEach(i=>{
      const w=WINS[i];
      t+='## '+TITLES[i]+'\n\n**Mode:** '+MODE[picks[i]];
      t+=picks[i]==='r' ? '. Neither side survives as written'
         : w==='a' ? '. Leads with **'+LA+'**'
         : w==='b' ? '. Leads with **'+LB+'**' : '. No side leads';
      t+='\n\n';
      if(notes[i]) t+='**Note:** '+notes[i]+'\n\n';
      t+='### '+(w==='a'?'**'+LA+'**':LA)+'\n\n'+colText(i,'a')+'\n\n';
      t+='### '+(w==='b'?'**'+LB+'**':LB)+'\n\n'+colText(i,'b')+'\n\n';
    });
  }
  t+='---\nresume link: '+location.href+'\n';
  document.getElementById('out').value=t;
  document.getElementById('dlg').showModal();
});
document.getElementById('btn-close').addEventListener('click',()=>document.getElementById('dlg').close());
document.getElementById('btn-copy').addEventListener('click',()=>{
  const ta=document.getElementById('out');
  ta.select(); ta.setSelectionRange(0,999999);
  try{ document.execCommand('copy'); }catch(e){}
  if(navigator.clipboard) navigator.clipboard.writeText(ta.value).catch(()=>{});
  announce('Decisions copied');
});

/* ---- theme: follow the system, or pin light/dark via data-theme ---- */
const THEME_KEY='cherrypicker:theme', THEMES=['auto','light','dark'];
function applyTheme(t){
  if(t==='auto') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.dataset.theme=t;
  document.getElementById('btn-theme').textContent='Theme: '+t[0].toUpperCase()+t.slice(1);
}
let theme='auto';
try{ theme=localStorage.getItem(THEME_KEY)||'auto'; }catch(e){}
if(THEMES.indexOf(theme)<0) theme='auto';
applyTheme(theme);
document.getElementById('btn-theme').addEventListener('click', ()=>{
  theme=THEMES[(THEMES.indexOf(theme)+1)%THEMES.length];
  applyTheme(theme);
  try{ localStorage.setItem(THEME_KEY, theme); }catch(e){}
});

// A resume link wins; a bare URL falls back to this browser's last hot save.
if(readHash()){ paint(); } else { readLocal(); paint(); if(picks.some(p=>p!=='-')||notes.some(x=>x)) writeHash(); }
window.addEventListener('hashchange', ()=>{ readHash(); paint(); });
"""


def _col_head(side, label):
    return ('<header class="col-h"><span class="col-name">%s</span>'
            '<span class="col-state" data-side="%s"></span></header>' % (html.escape(label), side))


def _column(units, idxs, side, label):
    if not idxs:
        return ('<article class="col empty" data-side="%s" aria-label="%s">%s'
                '<p class="none">Not in this file</p></article>'
                % (side, html.escape(label), _col_head(side, label)))
    blocks = []
    for i in idxs:
        u = units[i]
        name = 'Pull quote' if u['kind'] == 'quote' else u['label']
        blocks.append(
            '<section class="blk"><h3 class="blk-h">%s<span class="cc">%d'
            '<span aria-hidden="true">c</span><span class="vh"> characters</span></span></h3>'
            '<div class="prose">%s</div></section>'
            % (html.escape(name), len(u['body']), render_unit(u))
        )
    return ('<article class="col" data-side="%s" aria-label="%s">%s%s</article>'
            % (side, html.escape(label), _col_head(side, label), ''.join(blocks)))


_MODE_NAME = {'u': 'Union', 'g': 'Graft', 'f': 'Form plus facts', 's': 'Sequence'}


def _pick_name(row, label_a, label_b):
    """The button this recommendation is telling you to press."""
    p = row['pick']
    if p == 'a': return label_a
    if p == 'b': return label_b
    if p == 'r': return 'Rewrite'
    if p == 'n': return 'Cut'
    mode = row.get('mode')
    return 'Both, ' + _MODE_NAME[mode] if mode else 'Both'


def _rec(row, label_a, label_b):
    if not row.get('rec'):
        return ''
    chip = (('<span class="chip" data-c="%s">%s</span>'
             % (row['pick'], html.escape(_pick_name(row, label_a, label_b))))
            if row.get('pick') else '<strong>What I would do.</strong> ')
    lead = (('<span class="lead">%s leads</span>'
             % html.escape(label_a if row['win'] == 'a' else label_b))
            if row.get('win') else '')
    return '<p class="rec">%s%s%s</p>\n' % (chip, html.escape(row['rec']), lead)


_ROW = '''<section class="row%(one)s" id="r%(n)d" data-row="%(n)d" aria-labelledby="r%(n)d-t">
  <header class="row-h"><h2 id="r%(n)d-t" tabindex="-1">%(title)s</h2>
    <div class="picker" role="group" aria-label="Choose a version for %(title)s">
      <button type="button" data-p="a" aria-pressed="false">%(la)s</button>
      <button type="button" data-p="b" aria-pressed="false">%(lb)s</button>
      <button type="button" data-p="y" aria-pressed="false" title="Keep something from each">Both</button>
      <button type="button" data-p="r" aria-pressed="false" title="Neither survives as written">Rewrite</button>
      <button type="button" data-p="n" aria-pressed="false" title="Cut from this page">Cut</button>
    </div></header>
  <div class="panel">
    <fieldset class="modes"><legend>How do these combine?</legend>
      <div class="mode-btns">
        <button type="button" data-m="u" aria-pressed="false">Union</button>
        <button type="button" data-m="g" aria-pressed="false">Graft</button>
        <button type="button" data-m="f" aria-pressed="false">Form plus facts</button>
        <button type="button" data-m="s" aria-pressed="false">Sequence</button>
      </div>
      <p class="hint">Union and Sequence mean you edit it yourself. Both land in a worklist at the bottom of the export with the full text of each side ready to paste.</p>
    </fieldset>
    %(rec)s<label class="note-l" for="r%(n)d-note">What you want</label>
    <textarea id="r%(n)d-note" placeholder="Anything you want done here. An idea, a line to keep, a warning."></textarea>
  </div>
  <div class="cols">%(col_a)s%(col_b)s</div>
</section>'''


def build(a_units, b_units, align, label_a, label_b, title):
    rows = []
    for n, row in enumerate(align):
        rows.append(_ROW % {
            'one': '' if (row.get('a') and row.get('b')) else ' one-sided',
            'n': n, 'title': html.escape(row['title']),
            'la': html.escape(label_a), 'lb': html.escape(label_b),
            'rec': _rec(row, label_a, label_b),
            'col_a': _column(a_units, row.get('a') or [], 'a', label_a),
            'col_b': _column(b_units, row.get('b') or [], 'b', label_b),
        })

    js = (_JS.replace('__TITLES__', json.dumps([r['title'] for r in align]))
             .replace('__RECS__', json.dumps([r.get('rec','') for r in align]))
             .replace('__WINS__', json.dumps([r.get('win','') for r in align]))
             .replace('__LA__', json.dumps(label_a))
             .replace('__LB__', json.dumps(label_b)))

    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>%(title)s</title>
<style>%(css)s</style></head><body>
<a class="skip" href="#main">Skip to sections</a>

<header class="hero">
  <h1>%(title)s</h1>
  <p class="kicker">%(la)s &nbsp;vs&nbsp; %(lb)s &middot; %(n)d aligned sections &middot; pick per section</p>
  <dl class="impact-band">
    <div class="metric-item" data-k="a">
      <dt class="metric-label">Sections where %(la)s wins the copy.</dt>
      <dd class="metric-value" id="m-a">0</dd>
    </div>
    <div class="metric-item" data-k="b">
      <dt class="metric-label">Sections where %(lb)s wins the copy.</dt>
      <dd class="metric-value" id="m-b">0</dd>
    </div>
    <div class="metric-item" data-k="left">
      <dt class="metric-label">Still undecided, including merges and cuts.</dt>
      <dd class="metric-value" id="m-left">%(n)d</dd>
    </div>
  </dl>
</header>

<nav class="bar" aria-label="Progress and actions">
  <label class="vh" for="bar">Sections decided</label>
  <progress id="bar" max="%(n)d" value="0"></progress>
  <output class="count" id="count" for="bar">0 / %(n)d</output>
  <span class="saved" id="saved" aria-hidden="true">saved</span>
  <p class="vh" id="live" role="status" aria-live="polite"></p>
  <div class="acts">
    <button type="button" id="btn-next">Next undecided</button>
    <button type="button" id="btn-save">Save notes</button>
    <button type="button" id="btn-load">Load notes</button>
    <input type="file" id="file-load" accept="application/json,.json" hidden aria-hidden="true" tabindex="-1">
    <button type="button" id="btn-out">Export</button>
    <button type="button" id="btn-theme">Theme: Auto</button>
    <button type="button" id="btn-clear">Reset</button>
  </div>
</nav>

<main id="main">
%(rows)s
</main>

<dialog id="dlg" aria-labelledby="dlg-t">
  <header class="dlg-h"><h2 id="dlg-t">Decisions</h2>
    <button type="button" id="btn-copy" style="margin-left:auto">Copy</button>
    <button type="button" id="btn-close">Close</button>
  </header>
  <div class="dlg-b"><textarea id="out" readonly aria-label="Exported decisions, markdown"></textarea></div>
</dialog>

<script>%(js)s</script>
</body></html>""" % {
        'title': html.escape(title), 'css': _CSS, 'js': js,
        'la': html.escape(label_a), 'lb': html.escape(label_b),
        'n': len(align), 'rows': '\n'.join(rows),
    }


# ---------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    u = sub.add_parser('units', help='list the copy units in each file')
    u.add_argument('a'); u.add_argument('b')
    u.add_argument('--json', action='store_true', help='emit JSON instead of a table')

    bd = sub.add_parser('build', help='emit the comparison HTML')
    bd.add_argument('a'); bd.add_argument('b')
    bd.add_argument('--align', required=True, help='alignment spec JSON')
    bd.add_argument('--out', required=True)
    bd.add_argument('--label-a', default=None)
    bd.add_argument('--label-b', default=None)
    bd.add_argument('--title', default='Cherrypicker')

    args = ap.parse_args()
    au, bu = parse_units(args.a), parse_units(args.b)

    if args.cmd == 'units':
        if args.json:
            print(json.dumps({'a': au, 'b': bu}, indent=2))
            return
        for name, units in ((args.a, au), (args.b, bu)):
            print('=' * 6, name, '(%d units)' % len(units))
            for n, x in enumerate(units):
                head = (x['body'].split('\n')[0] if x['body'] else '')[:58]
                print('  [%2d] %-6s %-44s %5dc  %s'
                      % (n, x['kind'], x['label'][:44], len(x['body']), head))
        return

    with open(args.align, encoding='utf-8') as fh:
        align = json.load(fh)

    used_a = {i for r in align for i in (r.get('a') or [])}
    used_b = {i for r in align for i in (r.get('b') or [])}
    orphan_a = [i for i in range(len(au)) if i not in used_a]
    orphan_b = [i for i in range(len(bu)) if i not in used_b]
    if orphan_a or orphan_b:
        # Loud, not fatal: sometimes dropping a unit is deliberate. But silent
        # loss of copy is the one failure this tool must never produce.
        print('WARNING uncovered units — this copy will not appear anywhere:',
              file=sys.stderr)
        for i in orphan_a:
            print('  A[%d] %s' % (i, au[i]['label']), file=sys.stderr)
        for i in orphan_b:
            print('  B[%d] %s' % (i, bu[i]['label']), file=sys.stderr)

    doc = build(au, bu, align,
                args.label_a or os.path.basename(args.a),
                args.label_b or os.path.basename(args.b),
                args.title)
    with open(args.out, 'w', encoding='utf-8') as fh:
        fh.write(doc)
    print('wrote %s  (%d rows, %d bytes)' % (args.out, len(align), len(doc)))


if __name__ == '__main__':
    main()

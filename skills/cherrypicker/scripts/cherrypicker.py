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
    return md.convert(body)


# ---------------------------------------------------------------- template

_CSS = """
:root{
  color-scheme:light;
  --bg:#ffffff; --panel:#ffffff; --panel2:#f7f7f5; --line:#e3e3dd;
  --tx:#14161a; --tx2:#55606e; --tx3:#8a939f;
  --a:#1f6feb; --b:#6f42c1; --ok:#1a7f4b; --rw:#b45309; --cut:#c0392b;
  --band-bg:#f4f4f2; --band-line:#dcdcd6; --band-tx:#14161a; --band-tx2:#55606e;
  --space-md:1rem; --space-xl:2rem; --space-2xl:3rem;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
dl,dd{margin:0}
body{margin:0;background:var(--bg);color:var(--tx);
  font:16px/1.6 ui-sans-serif,-apple-system,"SF Pro Text",Inter,system-ui,sans-serif;
  padding-bottom:6rem}

.hero{max-width:980px;margin:0 auto;padding:2rem 1rem 0;text-align:center}
.hero h1{font-family:ui-serif,"Iowan Old Style","Times New Roman",Georgia,serif;
  font-weight:700;letter-spacing:-.02em;line-height:1.08;
  font-size:clamp(1.7rem,4.6vw,3rem);margin:0 0 .6rem}
.hero .kicker{color:var(--tx3);font-size:.9rem;margin:0 0 1.4rem}
.impact-band{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
  gap:var(--space-xl) var(--space-md);padding:var(--space-xl) var(--space-2xl);
  background:var(--band-bg);border:1px solid var(--band-line);border-radius:5px;
  margin:0 auto;max-width:980px}
.metric-item{text-align:center;min-width:0}
.metric-value{font-family:ui-serif,"Iowan Old Style","Times New Roman",Georgia,serif;
  font-size:clamp(2rem,5vw,3.1rem);line-height:1.05;font-weight:400;color:var(--band-tx);
  font-variant-numeric:tabular-nums;margin:0 0 .5rem;transition:color .2s}
.metric-label{color:var(--band-tx2);max-width:320px;margin:0 auto;font-size:.875rem;line-height:1.5}
.metric-item[data-k="b"] .metric-value{color:#6f42c1}
.metric-item[data-k="left"] .metric-value{color:#6b7280}

.bar{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.92);
  -webkit-backdrop-filter:saturate(1.6) blur(10px);backdrop-filter:saturate(1.6) blur(10px);
  border-bottom:1px solid var(--line);margin-top:1.6rem;
  padding:.55rem max(1rem,env(safe-area-inset-left));
  display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}
.meter{flex:1;min-width:120px;height:6px;background:var(--panel2);border-radius:99px;overflow:hidden}
.meter i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--a),var(--ok));transition:width .25s}
.count{font-variant-numeric:tabular-nums;color:var(--tx2);font-size:.8rem;white-space:nowrap}
.bar .acts{display:flex;gap:.4rem;margin-left:auto;flex-wrap:wrap}
.bar button{background:var(--panel2);color:var(--tx);border:1px solid var(--line);
  border-radius:8px;padding:.4rem .7rem;font:inherit;font-size:.8rem;cursor:pointer;
  -webkit-tap-highlight-color:transparent}
.bar button:hover,.loadlbl:hover{border-color:#c9c9c1;background:#f0f0ec}
.loadlbl{background:var(--panel2);color:var(--tx);border:1px solid var(--line);
  border-radius:8px;padding:.4rem .7rem;font-size:.8rem;cursor:pointer;line-height:1.4}
#btn-save.need{border-color:var(--rw);color:var(--rw);font-weight:600}
#btn-save.need::after{content:" \u25cf"}
.saved{color:var(--ok);font-size:.75rem;opacity:0;transition:opacity .3s}
.saved.on{opacity:1}

main{padding:1.25rem max(1rem,env(safe-area-inset-left))}
.row{background:var(--panel);border:1px solid var(--line);border-radius:14px;
  box-shadow:0 1px 2px rgba(20,22,26,.04);margin:0 0 1.1rem;overflow:hidden;scroll-margin-top:70px}
.row-h{position:relative;display:flex;align-items:center;gap:1rem;flex-wrap:wrap;
  padding:.8rem 1rem;background:var(--panel2);border-bottom:1px solid var(--line)}
.row-h h2{margin:0;font-weight:500;font-size:.95rem;letter-spacing:-.01em;
  font-family:ui-monospace,SFMono-Regular,Menlo,"Courier New",monospace;
  background:#000;color:#fff;padding:.25rem .6rem;border-radius:3px;
  text-transform:lowercase}
.picker{display:flex;gap:.5rem;margin-left:auto;flex-wrap:wrap}
.picker button{width:120px;height:38px;border:0;border-radius:5px;padding:0;
  font:inherit;font-size:.8rem;font-weight:600;color:#fff;cursor:pointer;opacity:.42;
  transition:opacity .15s, box-shadow .15s;
  -webkit-tap-highlight-color:transparent}
.picker button:hover{opacity:.6}
.picker button:focus-visible{outline:3px solid #000;outline-offset:3px}
.picker [data-p="a"]{background:var(--a);
  position:absolute;top:50%;right:50%;margin-right:.3rem;transform:translateY(-50%)}
.picker [data-p="b"]{background:var(--b);
  position:absolute;top:50%;left:50%;margin-left:.3rem;transform:translateY(-50%)}
.picker [data-p="y"]{background:var(--ok)}
.picker [data-p="r"]{background:var(--rw)}
.picker [data-p="n"]{background:var(--cut)}
.row[data-pick="r"] .picker [data-p="r"]{opacity:1;box-shadow:0 0 0 2px #fff,0 0 0 4px #14161a}
.row[data-pick="r"] .cols{opacity:.5}

/* Both panel */
.panel{display:none;padding:.9rem 1rem;background:#fbfbf9;border-bottom:1px solid var(--line)}
.row.open .panel{display:block}
.row.open .modes{display:none}
.row.combine .modes{display:flex}
.panel h3{margin:0 0 .5rem;font-size:.72rem;text-transform:uppercase;letter-spacing:.07em;color:var(--tx3)}
.modes{display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.8rem}
.modes button{background:#fff;border:1px solid var(--line);border-radius:99px;
  padding:.35rem .8rem;font:inherit;font-size:.78rem;color:var(--tx2);cursor:pointer}
.modes button:hover{border-color:#c9c9c1;color:var(--tx)}
.row[data-pick="u"] .modes [data-m="u"],
.row[data-pick="g"] .modes [data-m="g"],
.row[data-pick="f"] .modes [data-m="f"],
.row[data-pick="s"] .modes [data-m="s"]{background:var(--ok);border-color:var(--ok);color:#fff;font-weight:600}
.modes .hint{flex-basis:100%;font-size:.78rem;color:var(--tx2);margin:.2rem 0 0}
.panel .rec{font-size:.85rem;color:var(--tx2);background:#fff;border:1px solid var(--line);
  border-left:3px solid var(--a);border-radius:4px;padding:.55rem .7rem;margin:0 0 .8rem}
.panel .lead{display:inline-block;margin-left:.5rem;padding:.1rem .5rem;border-radius:99px;
  border:1px solid var(--line);background:#fff;color:var(--tx2);font-size:.7rem;
  font-weight:600;letter-spacing:.02em;text-transform:uppercase;vertical-align:.08em}
.panel .chip{display:inline-block;margin-right:.5rem;padding:.15rem .6rem;border-radius:4px;
  color:#fff;font-size:.72rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;
  vertical-align:.05em}
.panel .chip[data-c="a"]{background:var(--a)}
.panel .chip[data-c="b"]{background:var(--b)}
.panel .chip[data-c="y"]{background:var(--ok)}
.panel .chip[data-c="r"]{background:var(--rw)}
.panel .chip[data-c="n"]{background:var(--cut)}
.panel .rec{border-left-color:var(--tx3)}
.panel textarea{width:100%;min-height:76px;background:#fff;color:var(--tx);
  border:1px solid var(--line);border-radius:6px;padding:.55rem .7rem;
  font:inherit;font-size:.88rem;resize:vertical}
.panel textarea:focus{outline:2px solid var(--a);outline-offset:1px}
.row[data-pick="y"] .cols,
.row[data-pick="u"] .cols,.row[data-pick="g"] .cols,
.row[data-pick="f"] .cols,.row[data-pick="s"] .cols{opacity:1}
@media (max-width:560px){ .picker button{width:64px;height:34px} }
.row[data-pick="a"] .picker [data-p="a"]{opacity:1;box-shadow:0 0 0 2px #fff,0 0 0 4px #14161a}
.row[data-pick="b"] .picker [data-p="b"]{opacity:1;box-shadow:0 0 0 2px #fff,0 0 0 4px #14161a}
.row[data-pick="y"] .picker [data-p="y"],
.row[data-pick="u"] .picker [data-p="y"],
.row[data-pick="g"] .picker [data-p="y"],
.row[data-pick="f"] .picker [data-p="y"],
.row[data-pick="s"] .picker [data-p="y"]{opacity:1;box-shadow:0 0 0 2px #fff,0 0 0 4px #14161a}
.row[data-pick="n"] .picker [data-p="n"]{opacity:1;box-shadow:0 0 0 2px #fff,0 0 0 4px #14161a}
.row[data-pick="n"] .cols{opacity:.35}
.row[data-pick="a"] .col[data-side="b"],
.row[data-pick="b"] .col[data-side="a"]{opacity:.4}

.cols{display:grid;grid-template-columns:1fr 1fr}
.col{padding:.9rem 1rem;min-width:0;transition:opacity .2s}
.col+.col{border-left:1px solid var(--line)}
.col[data-side="a"]{border-top:3px solid var(--a)}
.col[data-side="b"]{border-top:3px solid var(--b)}
.col.empty{display:flex;align-items:center;justify-content:center}
.none{color:var(--tx3);font-style:italic;font-size:.85rem;margin:0}
.blk+.blk{margin-top:1rem;padding-top:1rem;border-top:1px dashed var(--line)}
.blk-h{font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;color:var(--tx3);
  margin-bottom:.45rem;display:flex;gap:.5rem;align-items:baseline}
.cc{margin-left:auto;font-variant-numeric:tabular-nums;opacity:.7}
.prose{font-size:.93rem;color:#3b4453}
.prose p{margin:0 0 .7rem}
.prose p:last-child{margin-bottom:0}
.prose strong{color:#14161a;font-weight:640}
.prose a{color:var(--a);text-decoration:underline;text-underline-offset:.15em}
.prose h2,.prose h3,.prose h4{font-size:.9rem;margin:.9rem 0 .4rem;color:#14161a}
.prose ul,.prose ol{margin:0 0 .7rem;padding-left:1.2rem}
.prose li{margin-bottom:.25rem}
.prose code{background:#f5f5f1;border:1px solid var(--line);border-radius:4px;
  padding:.08em .35em;font-size:.85em;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.prose pre{background:#f5f5f1;border:1px solid var(--line);border-radius:8px;padding:.7rem;overflow:auto}
.prose pre code{border:0;background:none;padding:0}
.prose blockquote{margin:.6rem 0;padding-left:.8rem;border-left:3px solid var(--line);color:var(--tx2)}
.prose table{width:100%;border-collapse:collapse;font-size:.78rem;margin:0 0 .7rem;display:block;overflow-x:auto}
.prose th,.prose td{border:1px solid var(--line);padding:.35rem .5rem;text-align:left;vertical-align:top}
.prose th{background:var(--panel2);color:#14161a;font-weight:600}
.prose img{max-width:100%}

@media (max-width:820px){
  .cols{grid-template-columns:1fr}
  .col+.col{border-left:0;border-top:3px solid var(--b)}
  .row-h h2{width:100%}
  .picker{margin-left:0}
}
/* Centred A/B buttons collide with Both/Rewrite/Cut below ~1060px (measured:
   B sits under Both at 834 and 1024), so they rejoin the flex row there. */
@media (max-width:1080px){
  .picker [data-p="a"],.picker [data-p="b"]{position:static;transform:none;margin:0}
}

dialog{background:var(--panel);color:var(--tx);border:1px solid var(--line);
  border-radius:14px;padding:0;max-width:min(680px,92vw);width:100%}
dialog::backdrop{background:#0006;backdrop-filter:blur(2px)}
.dlg-h{display:flex;align-items:center;gap:1rem;padding:.8rem 1rem;border-bottom:1px solid var(--line)}
.dlg-h h3{margin:0;font-size:.95rem}
.dlg-h button{background:var(--panel2);color:var(--tx);border:1px solid var(--line);
  border-radius:8px;padding:.4rem .7rem;font:inherit;font-size:.8rem;cursor:pointer}
.dlg-b{padding:1rem;max-height:60vh;overflow:auto}
textarea{width:100%;min-height:260px;background:#f7f7f5;color:var(--tx);border:1px solid var(--line);
  border-radius:8px;padding:.7rem;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;resize:vertical}
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

/* ---- persistence: picks in the URL, typed notes in a sidecar json ---- */
function readHash(){
  const m = /[#&]p=([abyugfsrn\-]+)/.exec(location.hash||'');
  if(m && m[1].length===N) picks = m[1].split('');
}
function writeHash(){
  history.replaceState(null,'',location.pathname+location.search+'#p='+picks.join(''));
  flash('saved');
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
  if(handle){
    try{
      const w = await handle.createWritable();
      await w.write(payload()); await w.close();
      dirty=false; flash('saved to file'); return;
    }catch(e){ handle=null; }
  }
  dirty = true;
  document.getElementById('btn-save').classList.add('need');
}
let saveT;
function autosave(){ clearTimeout(saveT); saveT=setTimeout(save,600); }

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
  flash('downloaded');
});
document.getElementById('file-load').addEventListener('change', ev=>{
  const f=ev.target.files[0]; if(!f) return;
  const rd=new FileReader();
  rd.onload=()=>{
    try{
      const j=JSON.parse(rd.result);
      if(j.picks && j.picks.length===N) picks=j.picks.split('');
      if(Array.isArray(j.notes) && j.notes.length===N) notes=j.notes;
      paint(); writeHash(); flash('loaded');
    }catch(e){ alert('Could not read that file.'); }
  };
  rd.readAsText(f); ev.target.value='';
});
window.addEventListener('beforeunload', e=>{ if(dirty){ e.preventDefault(); e.returnValue=''; } });

/* ---- painting ---- */
function paint(){
  document.querySelectorAll('.row').forEach(r=>{
    const i=+r.dataset.row, p=picks[i];
    if(p==='-') r.removeAttribute('data-pick'); else r.dataset.pick=p;
    r.classList.toggle('open', p!=='-');
    r.classList.toggle('combine', BOTH.indexOf(p)>=0);
    const ta=r.querySelector('.panel textarea');
    if(ta && ta.value!==notes[i]) ta.value=notes[i];
  });
  const done=picks.filter(p=>p!=='-').length;
  document.getElementById('count').textContent=done+' / '+N;
  document.getElementById('bar').style.width=(done/N*100)+'%';
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
    if(picks[i]!=='-' && v!=='y') row.querySelector('.panel textarea').focus();
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
    document.getElementById('btn-save').classList.add('need');
    autosave();
  });
});

/* ---- nav ---- */
document.getElementById('btn-next').addEventListener('click', ()=>{
  const i=picks.findIndex(p=>p==='-');
  if(i>=0) document.getElementById('r'+i).scrollIntoView({behavior:'smooth',block:'start'});
});
document.getElementById('btn-clear').addEventListener('click', ()=>{
  if(!confirm('Clear all picks and notes?')) return;
  picks=new Array(N).fill('-'); notes=new Array(N).fill('');
  paint(); writeHash(); autosave();
});

/* ---- export ---- */
function colText(i, side){
  const el=document.querySelector('#r'+i+' .col[data-side="'+side+'"]');
  if(!el || el.classList.contains('empty')) return '(not in this file)';
  return el.innerText.replace(/\n{3,}/g,'\n\n').trim();
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
});

readHash(); paint();
window.addEventListener('hashchange', ()=>{ readHash(); paint(); });
"""


def _column(units, idxs, side):
    if not idxs:
        return ('<div class="col empty" data-side="%s">'
                '<p class="none">Not in this file</p></div>' % side)
    blocks = []
    for i in idxs:
        u = units[i]
        label = 'Pull quote' if u['kind'] == 'quote' else u['label']
        blocks.append(
            '<div class="blk"><div class="blk-h">%s<span class="cc">%dc</span></div>'
            '<div class="prose">%s</div></div>'
            % (html.escape(label), len(u['body']), render_unit(u))
        )
    return '<div class="col" data-side="%s">%s</div>' % (side, ''.join(blocks))


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


def build(a_units, b_units, align, label_a, label_b, title):
    rows = []
    for n, row in enumerate(align):
        one = ''
        if not row.get('a'):
            one = ' one-sided'
        if not row.get('b'):
            one = ' one-sided'
        rows.append(
            '<section class="row%s" id="r%d" data-row="%d">\n'
            '  <header class="row-h"><h2>%s</h2>\n'
            '    <div class="picker" role="group" aria-label="Choose version for %s">\n'
            '      <button type="button" data-p="a" title="%s">%s</button>\n'
            '      <button type="button" data-p="b" title="%s">%s</button>\n'
            '      <button type="button" data-p="y" title="Both, combine them">Both</button>\n'
            '      <button type="button" data-p="r" title="Rewrite, neither survives as written">Rewrite</button>\n'
            '      <button type="button" data-p="n" title="Cut from this page">Cut</button>\n'
            '    </div></header>\n'
            '  <div class="panel">\n'
            '    <h3>How do these combine?</h3>\n'
            '    <div class="modes" role="group" aria-label="Combine mode">\n'
            '      <button type="button" data-m="u">Union</button>\n'
            '      <button type="button" data-m="g">Graft</button>\n'
            '      <button type="button" data-m="f">Form plus facts</button>\n'
            '      <button type="button" data-m="s">Sequence</button>\n'
            '      <p class="hint">Union and Sequence mean you edit it yourself. Both land in a worklist at the bottom of the export with the full text of each side ready to paste.</p>\n'
            '    </div>\n'
            '    %s'
            '    <label><h3>What you want</h3>\n'
            '    <textarea placeholder="Anything you want done here. An idea, a line to keep, a warning."></textarea></label>\n'
            '  </div>\n'
            '  <div class="cols">%s%s</div>\n</section>'
            % (one, n, n, html.escape(row['title']), html.escape(row['title']),
               html.escape(label_a), html.escape(label_a),
               html.escape(label_b), html.escape(label_b),
               ('<p class="rec">%s%s%s</p>\n'
                % (('<span class="chip" data-c="%s">%s</span>'
                    % (row['pick'], html.escape(_pick_name(row, label_a, label_b))))
                   if row.get('pick') else '<strong>What I would do.</strong> ',
                   html.escape(row.get('rec','')),
                   ('<span class="lead">%s leads</span>'
                    % html.escape(label_a if row['win']=='a' else label_b))
                   if row.get('win') else '')) if row.get('rec') else '',
               _column(a_units, row.get('a') or [], 'a'),
               _column(b_units, row.get('b') or [], 'b'))
        )

    js = (_JS.replace('__TITLES__', json.dumps([r['title'] for r in align]))
             .replace('__RECS__', json.dumps([r.get('rec','') for r in align]))
             .replace('__WINS__', json.dumps([r.get('win','') for r in align]))
             .replace('__LA__', json.dumps(label_a))
             .replace('__LB__', json.dumps(label_b)))

    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>%(title)s</title>
<style>%(css)s</style></head><body>

<header class="hero">
  <h1>%(title)s</h1>
  <p class="kicker">%(la)s &nbsp;vs&nbsp; %(lb)s &middot; %(n)d aligned sections &middot; pick per section</p>
  <dl class="impact-band">
    <div class="metric-item" data-k="a">
      <dt class="metric-value" id="m-a">0</dt>
      <dd class="metric-label">Sections where %(la)s wins the copy.</dd>
    </div>
    <div class="metric-item" data-k="b">
      <dt class="metric-value" id="m-b">0</dt>
      <dd class="metric-label">Sections where %(lb)s wins the copy.</dd>
    </div>
    <div class="metric-item" data-k="left">
      <dt class="metric-value" id="m-left">%(n)d</dt>
      <dd class="metric-label">Still undecided, including merges and cuts.</dd>
    </div>
  </dl>
</header>

<div class="bar">
  <div class="meter" aria-hidden="true"><i id="bar"></i></div>
  <span class="count" id="count">0 / %(n)d</span>
  <span class="saved" id="saved">saved</span>
  <div class="acts">
    <button type="button" id="btn-next">Next undecided</button>
    <button type="button" id="btn-save">Save notes</button>
    <label class="loadlbl" for="file-load">Load notes</label>
    <input type="file" id="file-load" accept="application/json,.json" hidden>
    <button type="button" id="btn-out">Export</button>
    <button type="button" id="btn-clear">Reset</button>
  </div>
</div>

<main>
%(rows)s
</main>

<dialog id="dlg">
  <div class="dlg-h"><h3>Decisions</h3>
    <button type="button" id="btn-copy" style="margin-left:auto">Copy</button>
    <button type="button" id="btn-close">Close</button>
  </div>
  <div class="dlg-b"><textarea id="out" readonly></textarea></div>
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

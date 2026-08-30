// PROJECT_SWEEP Step 0 — conversation-inventory discovery (ChatGPT). STATUS: CANDIDATE,
// UNVERIFIED. Read this header before trusting anything below.
//
// Unlike data_capture.js (whose per-conversation adapters were verified live, Aug 2026),
// the PROJECT-level listing endpoints here have NOT been verified against a real
// ChatGPT project. That difference is load-bearing:
//
//   * data_capture.js  per-conversation  → VERIFIED adapter, primary path
//   * this file        project inventory → CANDIDATE adapter, fail-closed
//
// The contract (SKILL.md, Phase P1): an enumeration is either PROVABLY exhaustive or
// it is declared UNVERIFIED — "DO NOT FAKE IT". Concretely:
//   - Only when this adapter returns {complete:true} (items collected == the API's own
//     `total`, no pagination errors) may the inventory be declared with
//     `--method data-layer --verified`.
//   - On ANY {error:...}, on total mismatch, or on any doubt: fall back to an
//     owner-provided inventory (exported URL list) and declare it
//     `--method declared` WITHOUT --verified. Coverage then answers for the declared
//     inventory only and prints PROJECT_ENUMERATION_UNVERIFIED.
//   - Screenshots/OCR are never an enumeration method.
//
// Output: JSON {source, projectId, total, complete, items:[{url,title,key,updated}]}
// — feed items straight into `project_contract.py declare --inventory <file>`.
// NOTE: javascript_tool has REPL semantics — the leading `await` is load-bearing.
await (async function(){
  const host=location.hostname.replace(/^www\./,'');
  if(host!=='chatgpt.com'&&host!=='chat.openai.com')
    return JSON.stringify({error:'no project-discovery adapter for '+host+
      ' — use an owner-declared inventory (fail closed; do not fake enumeration)'});

  // A ChatGPT project URL looks like /g/g-p-<id>/project (verified only as URL SHAPE,
  // not as API behaviour). Without a project id in the URL, this lists the ACCOUNT's
  // conversations — which is NOT project enumeration; it is refused below.
  const projectId=(location.pathname.match(/\/g\/(g-p-[A-Za-z0-9-]+)/)||[])[1]||window.__nxProjectId;
  if(!projectId) return JSON.stringify({error:'no project id in URL — open the project '+
    'page (or set window.__nxProjectId), or fall back to a declared inventory'});

  let sess; try{ sess=await (await fetch('/api/auth/session',{credentials:'include'})).json(); }
  catch(e){ return JSON.stringify({error:'session fetch failed: '+e}); }
  const token=sess&&sess.accessToken;
  if(!token) return JSON.stringify({error:'no accessToken — not logged in?'});

  // CANDIDATE endpoint (unverified): the conversations listing filtered by gizmo id.
  // If the response shape differs from {items,total}, fail closed — never guess.
  const items=[]; let offset=0, total=null;
  for(let page=0;page<200;page++){
    const r=await fetch('/backend-api/conversations?offset='+offset+'&limit=50'+
      '&order=updated&gizmo_id='+encodeURIComponent(projectId),
      {headers:{Authorization:'Bearer '+token}});
    if(!r.ok) return JSON.stringify({error:'listing fetch HTTP '+r.status+
      ' — CANDIDATE endpoint refused; fall back to a declared inventory'});
    const data=await r.json();
    if(!Array.isArray(data.items)||typeof data.total!=='number')
      return JSON.stringify({error:'unexpected listing shape ('+
        Object.keys(data||{}).join(',')+') — fall back to a declared inventory'});
    total=data.total;
    for(const it of data.items){
      if(!it||!it.id) continue;
      items.push({url:'https://chatgpt.com/c/'+it.id, key:'chatgpt.com/'+it.id,
                  title:String(it.title||'').slice(0,140), updated:it.update_time||null});
    }
    offset+=data.items.length;
    if(data.items.length===0||offset>=total) break;
  }
  // Dedup on conversation id — never on title.
  const seen=new Set(); const unique=items.filter(i=>!seen.has(i.key)&&seen.add(i.key));
  const complete=total!==null&&unique.length===total;
  return JSON.stringify({source:'project-discovery-candidate',projectId,total,
    collected:unique.length,complete,
    note:complete?'item count matches the API total — MAY be declared --verified '+
      'after a human sanity-check against the visible project':
      'INCOMPLETE OR UNPROVABLE — declare without --verified '+
      '(PROJECT_ENUMERATION_UNVERIFIED)',
    items:unique});
})()

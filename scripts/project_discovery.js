// PROJECT_SWEEP Step 0 — conversation-inventory discovery (ChatGPT).
// STATUS: cursor pagination against the dedicated project endpoint, measured against a
// real ChatGPT project during the Improvements proving run (2026-08-31).
//
// What the proving run actually measured, and what this file now encodes:
//
//   * The project's conversations live at /backend-api/gizmos/<gid>/conversations.
//     It is CURSOR-paginated and carries no count/total signal. Exhaustion is proved
//     by following the cursor until the platform stops offering one — mechanically,
//     not by arithmetic against a total that this endpoint never sends.
//   * The endpoint that v3.0 shipped, /backend-api/conversations?...&gizmo_id=<gid>,
//     ACCEPTS the filter and then IGNORES it: it answers with the account's
//     conversations. Its `total` therefore counts the account, not the project, and
//     "collected == total" on it is a false completeness claim, not a verification.
//     That endpoint is not reachable from this file any more — see MEMBERSHIP below.
//
// MEMBERSHIP comes from the ENDPOINT'S CONSTRUCTION, never from inspecting titles:
// the project id sits in the URL PATH, so every item the platform returns is returned
// *as* a member. A query-filter endpoint cannot establish membership, because this
// platform demonstrated it will silently drop the filter. Where items carry their own
// project id, that is checked too and any foreign item is a hard refusal.
//
// The id from the URL is `g-p-<32 hex>-<title-slug>`; the endpoint and the items' own
// `gizmo_id` both key on the STABLE hex prefix, so the slug is stripped before either
// is used (the v3.1 live smoke test found this — fixtures used slug-less ids).
//
// The contract (SKILL.md, Phase P1): an enumeration is either PROVABLY exhaustive or
// it is declared UNVERIFIED — "DO NOT FAKE IT". Concretely:
//   - `verifiable:true` (membership scoped AND exhaustion proved) is the ONLY output
//     that may be declared with `--method data-layer --verified --evidence <this file>`;
//     project_contract.py re-checks the evidence and refuses the claim otherwise.
//   - On ANY {error:...}, unproved exhaustion, or foreign item: fall back to an
//     owner-provided inventory, declare `--method declared` WITHOUT --verified, and
//     coverage prints PROJECT_ENUMERATION_UNVERIFIED.
//   - Screenshots/OCR are never an enumeration method. Titles are never identity.
//   - Owner confirmation is a welcome EXTRA oracle. It is not a substitute for this
//     proof, and this proof does not require it.
//
// Output: the enumeration evidence record — feed the whole file to
// `project_contract.py declare --inventory <file> --evidence <file>`.
// NOTE: javascript_tool has REPL semantics — the leading `await` is load-bearing.
await (async function(){
  const MAX_PAGES=500;                       // runaway guard, not an exhaustion signal
  const host=location.hostname.replace(/^www\./,'');
  if(host!=='chatgpt.com'&&host!=='chat.openai.com')
    return JSON.stringify({error:'no project-discovery adapter for '+host+
      ' — use an owner-declared inventory (fail closed; do not fake enumeration)'});

  const rawId=(location.pathname.match(/\/g\/(g-p-[A-Za-z0-9-]+)/)||[])[1]||window.__nxProjectId;
  if(!rawId) return JSON.stringify({error:'no project id in URL — open the project '+
    'page (or set window.__nxProjectId), or fall back to a declared inventory'});
  // A ChatGPT project id is `g-p-<32 hex>-<title-slug>`; the title slug follows the
  // project NAME and is not part of identity. The listing endpoint keys on the stable
  // hex id and 404s on the slug-bearing form, and each item's own `gizmo_id` is the
  // hex too — so BOTH the endpoint and the foreign-item check must use the stable id
  // (mirrors project_contract.stable_project_id). This was found by the v3.1 live
  // smoke test: fixtures used slug-less synthetic ids and never exercised it.
  const stableId=id=>{const m=String(id||'').match(/^(g-p-[0-9a-f]{16,})/i);
                      return m?m[1].toLowerCase():String(id||'').toLowerCase();};
  const projectId=stableId(rawId);

  let sess; try{ sess=await (await fetch('/api/auth/session',{credentials:'include'})).json(); }
  catch(e){ return JSON.stringify({error:'session fetch failed: '+e}); }
  const token=sess&&sess.accessToken;
  if(!token) return JSON.stringify({error:'no accessToken — not logged in?'});

  // The project id is in the PATH. That is what makes membership provable.
  const base='/backend-api/gizmos/'+encodeURIComponent(projectId)+'/conversations';
  const nextCursor=d=>{
    // The platform has spelled this several ways; absent/null/'' all mean "no more".
    const c=(d&&(d.cursor!==undefined?d.cursor:d.next_cursor));
    return (c===undefined||c===null||c==='')?null:String(c);
  };

  const items=[]; const pages=[]; const seenCursors=new Set();
  let cursor=null, exhausted=false, reason='', terminal=null, foreign=[];
  let countSignal=null;                        // used as an EXTRA oracle when present

  for(let page=0;page<MAX_PAGES;page++){
    const url=base+'?limit=50'+(cursor?('&cursor='+encodeURIComponent(cursor)):'');
    let r; try{ r=await fetch(url,{headers:{Authorization:'Bearer '+token}}); }
    catch(e){ reason='network error on page '+(page+1)+': '+e; break; }
    if(!r.ok){ reason='listing fetch HTTP '+r.status+' on page '+(page+1); break; }
    let data; try{ data=await r.json(); }
    catch(e){ reason='page '+(page+1)+' is not JSON: '+e; break; }
    if(!Array.isArray(data.items)){
      reason='unexpected listing shape ('+Object.keys(data||{}).join(',')+
             ') on page '+(page+1)+' — items[] is required';
      break;
    }
    if(typeof data.total==='number') countSignal=data.total;

    for(const it of data.items){
      if(!it||!it.id) continue;
      // When an item declares its own project, it must be THIS project. A listing that
      // hands back someone else's conversation is exactly the v3.0 defect, and it can
      // never be repaired by filtering here — it invalidates the whole enumeration.
      const owner=it.gizmo_id||it.conversation_origin||(it.gizmo&&it.gizmo.id)||null;
      if(owner&&stableId(owner)!==projectId) foreign.push(String(it.id));
      items.push({url:'https://chatgpt.com/c/'+it.id, key:'chatgpt.com/'+it.id,
                  title:String(it.title||'').slice(0,140), updated:it.update_time||null});
    }

    const nxt=nextCursor(data);
    pages.push({page:page+1, cursor_in:cursor, items:data.items.length, cursor_out:nxt});

    if(nxt===null){ exhausted=true; terminal=data.items.length?'cursor-absent':'cursor-absent-empty-page'; break; }
    if(seenCursors.has(nxt)){ reason='cursor did not advance (repeated '+nxt+
      ') — a loop is not an exhaustion proof'; break; }
    seenCursors.add(nxt); cursor=nxt;
    if(page===MAX_PAGES-1) reason='page cap '+MAX_PAGES+' reached with a cursor still '+
      'outstanding — enumeration is NOT exhausted';
  }

  // Dedup on the platform's conversation id — never on title. The same conversation
  // may legitimately appear on two cursor pages if the project changed mid-walk.
  const seen=new Set(); const unique=items.filter(i=>!seen.has(i.key)&&seen.add(i.key));
  const dupes=items.length-unique.length;

  // An extra oracle, only when the platform volunteered one. Its ABSENCE proves
  // nothing (this endpoint never sends it); its DISAGREEMENT proves a problem.
  let countCheck='absent — this endpoint sends no total; exhaustion is the proof';
  if(countSignal!==null){
    countCheck=(unique.length===countSignal)?('agrees ('+countSignal+')')
      :('DISAGREES: collected '+unique.length+' vs total '+countSignal);
    if(unique.length!==countSignal&&exhausted){
      exhausted=false; reason=reason||'collected count disagrees with the total the '+
        'platform sent — refusing to call that exhausted';
    }
  }
  if(foreign.length){
    exhausted=false;
    reason='listing returned '+foreign.length+' conversation(s) belonging to another '+
      'project ('+foreign.slice(0,3).join(', ')+') — membership is NOT established';
  }

  const verifiable=exhausted&&!foreign.length;
  return JSON.stringify({
    source:'project-discovery-cursor', projectId, rawUrlId:rawId, endpoint:base,
    membership:{scope:'path-scoped-project-endpoint',
                established_by:'project id in the request PATH',
                foreign_items:foreign},
    exhaustion:{proven:exhausted, terminal_signal:terminal,
                reason:exhausted?'':(reason||'exhaustion not demonstrated'),
                pages_walked:pages.length, pages},
    count_oracle:countCheck,
    collected:unique.length, duplicates_dropped:dupes,
    verifiable,
    note:verifiable
      ?'cursor exhausted mechanically on a path-scoped project endpoint — MAY be '+
       'declared --verified with this record as --evidence'
      :'PROJECT_ENUMERATION_UNVERIFIED — declare --method declared WITHOUT --verified',
    items:unique});
})()

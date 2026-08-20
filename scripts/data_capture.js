// Step 0 — PREFERRED: data-layer capture (ChatGPT). Run in javascript_tool on the
// logged-in chatgpt.com tab that shows (or whose URL contains) the target conversation.
//
// Fetches the conversation JSON from ChatGPT's own backend API instead of scraping the
// rendered DOM. Why this is the primary path (two real DOM-run failures):
//  - a /share/ link's SSR payload decoded to a bloated 156k-char block — the raw data
//    model (tool wrappers, metadata, reasoning), NOT the chat a human saw;
//  - the live chat is WINDOW-virtualized: turns unmount offscreen and only trusted
//    wheel events mount them, so DOM scraping stalls 15+ min and misses messages.
// The data layer is lossless, instant, and immune to virtualization.
//
// Returns evidence JSON {msgCount, roles, firstPreview, lastPreview, totalChars,
// exportLen, attachments} and stores the ASCII-escaped message array on
// window.__nxExport for the standard slice transfer + reassemble_verify.py
// (Steps 3–4 of references/extraction.md). Fail closed: any {error: ...} result or a
// suspiciously bloated totalChars means fall back to the DOM playbook — never deliver
// a capture whose size you cannot explain against the visible chat.
// NOTE: javascript_tool has REPL semantics — a bare async IIFE returns a pending
// Promise that serializes as {}. The leading `await` below is load-bearing.
await (async function(){
  const convId=(location.pathname.match(/\/c\/([0-9a-f-]{20,})/i)||[])[1]||window.__nxConvId;
  if(!convId) return JSON.stringify({error:'no conversation id in URL — open the chat, or set window.__nxConvId'});
  let sess; try{ sess=await (await fetch('/api/auth/session',{credentials:'include'})).json(); }
  catch(e){ return JSON.stringify({error:'session fetch failed: '+e}); }
  const token=sess&&sess.accessToken;
  if(!token) return JSON.stringify({error:'no accessToken in /api/auth/session — not logged in? Fall back to DOM playbook.'});
  const r=await fetch('/backend-api/conversation/'+convId,{headers:{Authorization:'Bearer '+token}});
  if(!r.ok) return JSON.stringify({error:'conversation fetch HTTP '+r.status+' — fall back to DOM playbook'});
  const data=await r.json();
  const mapping=data.mapping||{};
  // Linear thread: current_node -> parent -> ... -> root, then reverse to chronological.
  // This is exactly the branch the user currently sees; abandoned edit-branches are
  // excluded by construction.
  const chain=[]; const seen=new Set(); let cur=data.current_node;
  while(cur&&mapping[cur]&&!seen.has(cur)){ seen.add(cur); chain.push(mapping[cur]); cur=mapping[cur].parent; }
  chain.reverse();
  // WYSIWYG filter: keep only what a human SAW in the chat. No system, no tool turns,
  // no 'thoughts'/reasoning, no visually-hidden context messages, no empties.
  const msgs=[]; const attachments=[];
  for(const node of chain){
    const m=node.message; if(!m) continue;
    const role=m.author&&m.author.role;
    if(role!=='user'&&role!=='assistant') continue;
    if(m.metadata&&m.metadata.is_visually_hidden_from_conversation) continue;
    const c=m.content||{}; let text='';
    if(c.content_type==='text'){
      text=(c.parts||[]).filter(p=>typeof p==='string').join('\n');
    } else if(c.content_type==='multimodal_text'){
      text=(c.parts||[]).map(p=>typeof p==='string'?p:(p&&p.text)||'').filter(Boolean).join('\n');
      (c.parts||[]).forEach(p=>{ if(p&&typeof p==='object'&&!p.text)
        attachments.push({msg:msgs.length,label:String(p.asset_pointer||p.content_type||'non-text part').slice(0,80)}); });
    } else continue; // thoughts / code / execution_output etc. — not user-visible chat text
    ((m.metadata&&m.metadata.attachments)||[]).forEach(a=>
      attachments.push({msg:msgs.length,label:String(a.name||a.id||'bilaga').slice(0,80)}));
    if(!text.trim()) continue;
    msgs.push({role,text});
  }
  const totalChars=msgs.reduce((s,m)=>s+m.text.length,0);
  // Escape to ASCII so the slice transfer can never split a character (same contract
  // as extract.js) and reassemble_verify.py's exact-length check stays meaningful.
  const esc=s=>s.replace(/[^\x20-\x7e]/g,ch=>'\\u'+ch.charCodeAt(0).toString(16).padStart(4,'0'));
  window.__nxExport=esc(JSON.stringify(msgs));
  return JSON.stringify({source:'data-layer',convId,title:data.title||null,
    msgCount:msgs.length,
    roles:msgs.map(m=>m.role==='user'?'u':'a').join(''),
    attachments,
    firstPreview:msgs[0]?msgs[0].text.slice(0,140):null,
    lastPreview:msgs.length?msgs[msgs.length-1].text.slice(0,140):null,
    totalChars, exportLen:window.__nxExport.length});
})()

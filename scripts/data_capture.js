// Step 0 — PREFERRED: data-layer capture (host-aware: ChatGPT & Claude.ai). Run in
// javascript_tool on the logged-in tab that shows (or whose URL contains) the target
// conversation. Mirrors probe.js/extract.js: the host picks the adapter.
//
// Fetches the conversation JSON from the site's own backend API instead of scraping the
// rendered DOM. Why this is the primary path (two real DOM-run failures):
//  - a /share/ link's SSR payload decoded to a bloated 156k-char block — the raw data
//    model (tool wrappers, metadata, reasoning), NOT the chat a human saw;
//  - the live chat is WINDOW-virtualized: turns unmount offscreen and only trusted
//    wheel events mount them, so DOM scraping stalls 15+ min and misses messages.
// The data layer is lossless, instant, and immune to virtualization.
//
// Both adapters return the SAME evidence JSON {msgCount, roles, firstPreview,
// lastPreview, totalChars, exportLen, sha256, attachments} and store the ASCII-escaped
// message array on window.__nxExport for the standard slice transfer +
// reassemble_verify.py (Steps 3–4 of references/extraction.md). The sha256 is of those
// exact bytes and Step 4 REQUIRES it: length cannot tell two conversations apart, and a
// clipboard relay whose trusted click never landed hands back the previous export. Fail closed: any {error: ...} result or a
// suspiciously bloated totalChars means fall back to the DOM playbook — never deliver
// a capture whose size you cannot explain against the visible chat.
// NOTE: javascript_tool has REPL semantics — a bare async IIFE returns a pending
// Promise that serializes as {}. The leading `await` below is load-bearing.
await (async function(){
  const host=location.hostname.replace(/^www\./,'');
  // Escape to ASCII so the slice transfer can never split a character (same contract
  // as extract.js) and reassemble_verify.py's exact-length check stays meaningful.
  const esc=s=>s.replace(/[^\x20-\x7e]/g,ch=>'\\u'+ch.charCodeAt(0).toString(16).padStart(4,'0'));
  const finish=async(msgs,meta)=>{
    const totalChars=msgs.reduce((s,m)=>s+m.text.length,0);
    window.__nxExport=esc(JSON.stringify(msgs));
    const buf=await crypto.subtle.digest('SHA-256',
      new TextEncoder().encode(window.__nxExport));
    const sha256=[...new Uint8Array(buf)].map(b=>b.toString(16).padStart(2,'0')).join('');
    window.__nxExportSha256=sha256;
    return JSON.stringify(Object.assign({source:'data-layer'},meta,{
      msgCount:msgs.length,
      roles:msgs.map(m=>m.role==='user'?'u':'a').join(''),
      firstPreview:msgs[0]?msgs[0].text.slice(0,140):null,
      lastPreview:msgs.length?msgs[msgs.length-1].text.slice(0,140):null,
      totalChars,exportLen:window.__nxExport.length,sha256}));
  };

  if(host==='chatgpt.com'||host==='chat.openai.com'){
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
    return await finish(msgs,{convId,title:data.title||null,attachments});
  }

  if(host==='claude.ai'){
    // Verified against claude.ai (Aug 2026); every field name below was discovered live
    // from the real API response before this parser was written — see the Claude.ai
    // adapter section of references/extraction.md.
    const convId=(location.pathname.match(/\/chat\/([0-9a-f-]{20,})/i)||[])[1]||window.__nxConvId;
    if(!convId) return JSON.stringify({error:'no conversation id in URL — open the chat (claude.ai/chat/<uuid>), or set window.__nxConvId'});
    // Auth is the session cookie itself — no accessToken analogue (verified: the API
    // answers same-origin fetches with credentials:'include' and nothing else).
    let orgs; try{
      const ro=await fetch('/api/organizations',{credentials:'include'});
      if(!ro.ok) return JSON.stringify({error:'organizations fetch HTTP '+ro.status+' — not logged in? Fall back to DOM playbook'});
      orgs=await ro.json();
    }catch(e){ return JSON.stringify({error:'organizations fetch failed: '+e}); }
    // An account can hold several orgs (e.g. an API-only org); the chat lives in the
    // one with the 'chat' capability — orgs[0] is NOT a safe pick.
    const org=(Array.isArray(orgs)?orgs:[]).find(o=>(o.capabilities||[]).includes('chat'))||(orgs&&orgs[0]);
    if(!org||!org.uuid) return JSON.stringify({error:'no organization uuid in /api/organizations — fall back to DOM playbook'});
    const r=await fetch('/api/organizations/'+org.uuid+'/chat_conversations/'+convId+'?tree=True&rendering_mode=messages',{credentials:'include'});
    if(!r.ok) return JSON.stringify({error:'conversation fetch HTTP '+r.status+' — fall back to DOM playbook'});
    const data=await r.json();
    const all=data.chat_messages||[];
    // Linear thread: current_leaf_message_uuid -> parent_message_uuid -> ... -> the
    // all-zeros root uuid, then reverse — exactly the branch the user currently sees
    // (tree=True returns ALL branches; abandoned edits are excluded by the walk).
    // If the leaf pointer is missing, fall back to index order.
    const byId={}; all.forEach(m=>{byId[m.uuid]=m;});
    const ROOT='00000000-0000-4000-8000-000000000000';
    let chain=[]; const seen=new Set(); let cur=data.current_leaf_message_uuid;
    while(cur&&cur!==ROOT&&byId[cur]&&!seen.has(cur)){ seen.add(cur); chain.push(byId[cur]); cur=byId[cur].parent_message_uuid; }
    chain.reverse();
    if(!chain.length) chain=all.slice().sort((a,b)=>(a.index||0)-(b.index||0));
    // WYSIWYG filter: sender ∈ {human, assistant} -> user/assistant; drop anything else.
    // Message text lives in the content blocks — the flat .text field is EMPTY for BOTH
    // roles in rendering_mode=messages (verified). Keep type:'text' blocks joined with
    // '\n'; drop thinking (comes empty in this mode anyway) — not user-visible chat text.
    // Non-text blocks (tool cards, artifacts) are serialized server-side as a fenced
    // placeholder text block: ```\nThis block is not supported on your current device
    // yet.\n``` — the human saw a card there, not that sentence, so drop the block and
    // inventory it. Exact-match only: if the wording ever drifts, the block stays
    // VISIBLE in the transcript (detectable junk beats silent loss).
    const PLACEHOLDER=/^\s*```\s*\nThis block is not supported on your current device yet\.\s*\n```\s*$/;
    const msgs=[]; const attachments=[];
    for(const m of chain){
      const role=m.sender==='human'?'user':m.sender==='assistant'?'assistant':null;
      if(!role) continue;
      const text=(m.content||[]).filter(c=>c&&c.type==='text').filter(c=>{
        if(PLACEHOLDER.test(c.text||'')){
          attachments.push({msg:msgs.length,label:'icke-textblock (verktygskort/artefakt) — ej chattext'});
          return false;
        }
        return true;
      }).map(c=>c.text||'').filter(Boolean).join('\n');
      [].concat(m.attachments||[],m.files||[]).forEach(a=>
        attachments.push({msg:msgs.length,label:String((a&&(a.file_name||a.name||a.id))||'bilaga').slice(0,80)}));
      if(!text.trim()) continue;
      msgs.push({role,text});
    }
    // A message whose blocks were ALL placeholders (tool-only turn) drops out entirely —
    // verified correct against the rendered DOM: such turns show cards, no chat text.
    return await finish(msgs,{convId,title:data.name||null,attachments});
  }

  return JSON.stringify({error:'no data-layer adapter for '+host+' — fall back to the DOM playbook'});
})()

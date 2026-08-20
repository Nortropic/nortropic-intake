// Step 1 — Probe (host-aware). Run in javascript_tool on the chat tab.
// Detects the site, tries that site's known message selectors, and ALSO returns a
// discovery report of repeated text blocks — so on a new/changed DOM you can pick the
// right selector from evidence instead of guessing. ChatGPT selectors are verified;
// the Claude.ai set is a CANDIDATE — confirm it against the discovery report on first run.
(function(){
  const host = location.hostname.replace(/^www\./,'');
  const ADAPTERS = {
    'chatgpt.com':     { turn:'[data-message-author-role]',
                         role: el => el.getAttribute('data-message-author-role') },
    'chat.openai.com': { turn:'[data-message-author-role]',
                         role: el => el.getAttribute('data-message-author-role') },
    // Claude.ai — CANDIDATE, unverified. User turns and assistant turns have historically
    // carried distinct testids / classes; verify from `discovery` below on the first real run.
    'claude.ai':       { turn:'[data-testid="user-message"], [data-testid="assistant-message"], .font-claude-message, .font-user-message',
                         role: el => el.matches('[data-testid="user-message"], .font-user-message') ? 'user'
                                   : el.matches('[data-testid="assistant-message"], .font-claude-message') ? 'assistant'
                                   : 'unknown' } };
  const ad = ADAPTERS[host] || null;
  const turns = ad ? [...document.querySelectorAll(ad.turn)] : [];
  const chipRe=/inklistrad|dokument|\.txt|\.md|\.tgz|\.zip|\.pdf|\.csv|uploaded|bilaga|file/i;
  const chips = turns.flatMap((m,i)=>[...m.querySelectorAll('button,[role="button"]')]
    .map(b=>(b.innerText||'').trim()).filter(t=>t && chipRe.test(t)).map(t=>({msg:i,label:t.slice(0,80)})));
  // Discovery: repeated sibling blocks with substantial text (works on any/unknown DOM).
  const groups=new Map();
  document.querySelectorAll('div,article,section,li').forEach(el=>{
    const t=(el.innerText||'').trim(); if(t.length<40) return;
    const cls=[...el.classList].slice(0,2).join('.');
    const key=el.tagName+(cls?'.'+cls:'')+(el.getAttribute('data-testid')?'[testid='+el.getAttribute('data-testid')+']':'');
    const g=groups.get(key)||{count:0,sample:''}; g.count++; if(!g.sample)g.sample=t.slice(0,50); groups.set(key,g);
  });
  const discovery=[...groups.entries()].filter(([,g])=>g.count>=2)
    .sort((a,b)=>b[1].count-a[1].count).slice(0,8).map(([k,g])=>({sel:k,count:g.count,sample:g.sample}));
  return JSON.stringify({
    host, adapterKnown: !!ad, n: turns.length,
    roles: turns.map(t=>ad?ad.role(t):null),
    sizes: turns.map(t=>(t.innerText||'').length),
    attachmentChips: chips,
    firstPreview: turns[0]?turns[0].innerText.slice(0,150):null,
    lastPreview: turns.length?turns[turns.length-1].innerText.slice(0,150):null,
    discovery });
})()

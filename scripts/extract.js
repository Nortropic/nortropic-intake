// Step 2 — Extraction (host-aware). Run AFTER the render pass, no modal open.
// Uses the site adapter to find message turns + their role, then the same
// code-fence reconstruction for both ChatGPT and Claude:
//  - pre.innerText from the LIVE DOM (textContent loses line breaks)
//  - clone + replace <pre> with fenced text read in an opacity:0 holder
//    (visibility:hidden returns empty)
//  - escape to ASCII so slice transfer can never split a character
// Stores the result on window.__nxExport; returns {host, len, msgCount}.
//
// If the host has no adapter, or the probe showed the CANDIDATE Claude selector
// caught the wrong count/roles, set OVERRIDE_TURN / OVERRIDE_ROLE_ATTR below from
// the probe's discovery report before running — don't guess blindly.
//
// NEUTRALIZE: true ONLY after the masked secret scan showed no real secrets (see playbook).
(function(){
  const OVERRIDE_TURN = '';        // e.g. 'div[data-testid="chat-turn"]' — from discovery
  const OVERRIDE_ROLE_ATTR = '';   // e.g. 'data-testid' — value decides role; else alternate
  const NEUTRALIZE = false;
  const host = location.hostname.replace(/^www\./,'');
  const ADAPTERS = {
    'chatgpt.com':     { turn:'[data-message-author-role]', role: el => el.getAttribute('data-message-author-role') },
    'chat.openai.com': { turn:'[data-message-author-role]', role: el => el.getAttribute('data-message-author-role') },
    'claude.ai':       { turn:'[data-testid="user-message"], [data-testid="assistant-message"], .font-claude-message, .font-user-message',
                         role: el => el.matches('[data-testid="user-message"], .font-user-message') ? 'user'
                                   : el.matches('[data-testid="assistant-message"], .font-claude-message') ? 'assistant' : 'unknown' } };
  let turnSel, roleOf;
  if (OVERRIDE_TURN) {
    turnSel = OVERRIDE_TURN;
    roleOf = (el,i) => OVERRIDE_ROLE_ATTR ? (el.getAttribute(OVERRIDE_ROLE_ATTR)||'unknown') : (i%2===0?'user':'assistant');
  } else if (ADAPTERS[host]) {
    turnSel = ADAPTERS[host].turn; roleOf = (el)=>ADAPTERS[host].role(el);
  } else {
    return JSON.stringify({error:'no adapter for '+host+' — run probe, pick a selector from discovery, set OVERRIDE_TURN'});
  }
  const msgs=[...document.querySelectorAll(turnSel)];
  const holder=document.createElement('div');
  holder.style.cssText='position:fixed;left:-99999px;top:0;width:800px;opacity:0;pointer-events:none;';
  document.body.appendChild(holder);
  const zw='⁠';
  const neutralize=s=>NEUTRALIZE? s.replace(/cookie|token|session|secret|bearer|auth/gi,m=>m.split('').join(zw)) : s;
  const junk=new Set(['Kopiera kod','Kopiera','Copy code','Copy','Alltid visa information','Always show details','Copy code','Kopiera kod']);
  const langs=new Set(['bash','sh','zsh','shell','python','py','json','yaml','yml','js','javascript',
    'ts','typescript','html','css','text','txt','markdown','md','sql','diff','xml','plaintext','console','ini','toml']);
  const out=msgs.map((m,i)=>{
    const liveTexts=[...m.querySelectorAll('pre')].map(pre=>pre.innerText||'');
    const c=m.cloneNode(true);
    [...c.querySelectorAll('pre')].forEach((pre,j)=>{
      let lines=(liveTexts[j]||'').replace(/\n+$/,'').split('\n').filter(l=>!junk.has(l.trim()));
      let lang='';
      if(lines.length && langs.has(lines[0].trim().toLowerCase())){lang=lines[0].trim().toLowerCase(); lines=lines.slice(1);}
      const d=document.createElement('div');
      d.style.cssText='white-space:pre-wrap;';
      d.textContent='```'+lang+'\n'+lines.join('\n')+'\n```';
      pre.replaceWith(d);
    });
    c.querySelectorAll('button,[role="button"]').forEach(b=>b.remove());
    holder.appendChild(c);
    const text=c.innerText;
    holder.removeChild(c);
    return {role: roleOf(m,i), text: neutralize(text)};
  });
  document.body.removeChild(holder);
  const esc=s=>s.replace(/[^\x20-\x7e]/g,ch=>'\\u'+ch.charCodeAt(0).toString(16).padStart(4,'0'));
  window.__nxExport=esc(JSON.stringify(out));
  return JSON.stringify({host, len:window.__nxExport.length, msgCount:out.length, roles:out.map(o=>o.role)});
})()

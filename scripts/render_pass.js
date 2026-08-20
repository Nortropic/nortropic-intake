// Step 1.5 — Render pass. Run REPEATEDLY (with scrolling in between) until it
// returns {"expanded":0} twice in a row. Collapsed code blocks hide behind
// "Alltid visa information"/"Always show details" buttons; unexpanded blocks
// export truncated. Scroll the conversation top-to-bottom between runs so
// content-visibility renders every message at least once.
(function(){
  const btns=[...document.querySelectorAll('button')]
    .filter(b=>/alltid visa|always show|show more|visa mer/i.test(b.innerText||''));
  btns.forEach(b=>b.click());
  return JSON.stringify({expanded: btns.length});
})()

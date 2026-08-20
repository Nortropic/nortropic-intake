# nortropic-intake

**A Claude Code skill that turns a brainstorm chat (in ChatGPT or Claude) into ready-to-build implementation context: a distilled idea brief plus the verbatim transcript kept as evidence.**

Resten av den här filen är på svenska. README:n förklarar *vad* skillen gör och *varför* —
det exakta *hur* står i [SKILL.md](SKILL.md).

## Vad är det här?

[Claude Code](https://code.claude.com) är Anthropics kodagent — en AI som läser, skriver
och kör kod från terminalen. En **skill** är ett instruktionspaket i vanliga textfiler
som Claude Code läser in när en viss sorts uppgift dyker upp: en checklista och
spelregler för just den uppgiften.

Den här skillen gör en sak: den förvandlar en brainstorm-chatt till den kontext en
kodagent behöver för att implementera idén.

## Problemet

Man brainstormar en idé i ChatGPT eller Claude. Chatten blir lång — full av sidospår,
halvfärdiga tankar och vägar man provade och sedan övergav.

Ger man den råa chatten till en kodagent kan den troget bygga något man ångrade två
meddelanden senare. Det har hänt på riktigt: en plan som förkastades strax efter att den
formulerats var på väg att byggas ändå, eftersom ett transkript inte skiljer på "beslut"
och "tanke vi släppte".

## Lösningen: två filer

Varje körning levererar två Markdown-filer:

1. **`idea-<slug>.md` — briefen.** En "brief" är här en destillerad
   implementationsbeskrivning på 2–3 sidor: besluten med en rads motivering vardera,
   de **förkastade** vägarna (de farligaste att tappa bort), acceptanskriterier och
   öppna frågor. Kriterierna skrivs i **EARS**-form — "WHEN &lt;händelse&gt;, THE
   &lt;system&gt; SHALL &lt;beteende&gt;" — så att varje krav går att omsätta i ett test.
2. **`<slug>-full-chat.md` — transkriptet.** Hela chatten ordagrant, som bevismaterial
   att slå upp *varför* ett beslut togs — inte att bygga ifrån.

Vid konflikt vinner briefen, alltid.

Filerna hamnar i idébanken — ett separat repo (`innovation-intake`) med en indexrad per
idé — så att idéer kan parkeras och plockas fram långt senare med kontexten intakt.

## Hur en körning ser ut

1. **Routing.** Första frågan: ska idén *sparas i idébanken* för senare, eller
   *implementeras nu*? (Körs skillen obemannat defaultar den till idébanken.)
2. **Capture.** Chatten hämtas — i första hand via sajtens eget API, vilket är exakt och
   förlustfritt; att skrapa den renderade sidan (DOM:en) finns kvar som reserv.
3. **Destillering.** Briefen skrivs. Varje sidospår i chatten sorteras som beslutat,
   förkastat eller olöst (olösta blir öppna frågor).
4. **Intervju** — bara på implementera-nu-vägen: skillen visar besluten, frågar om de
   stämmer och får svar på de öppna frågorna innan något byggs.
5. **Dubblettkontroll.** Den nya idén jämförs mot idébanken: ersätter den en äldre
   brief, är de släkt, eller distinkta? Aldrig en tyst dubblett.
6. **Leverans.** Båda filerna skrivs till idébanken plus en indexrad. Skillen committar
   och pushar aldrig — det förblir egna, uttryckliga beslut.

**Exempel:** du har brainstormat en kvalitetskontroll-idé i ChatGPT i en timme. I Claude
Code skriver du "kör intake". Skillen frågar "idébank eller bygga nu?" — du svarar
idébank. Strax därefter ligger en mapp i idébanken med en brief som listar besluten
(och de två vägar ni förkastade, med varför). Nästa gång du vill bygga idén plockas
briefen fram — inte den timslånga chatten.

## Använda den

**Krävs:** Claude Code. För att fånga en webbläsarflik eller en chatt via URL krävs
dessutom Chrome-integrationen (`claude --chrome`) med chattjänsten inloggad i den
webbläsaren. Den pågående Claude Code-konversationen kan arkiveras utan webbläsare.

**Installation:** klona repot till `~/.claude/skills/nortropic-intake/` — Claude Code
hittar skills i den katalogen automatiskt.

**Trigger:** be Claude Code på vanligt språk — till exempel "kör intake", "arkivera
vårt samtal" (den pågående konversationen) eller "harvest this URL: &lt;länk&gt;".
Svenska eller engelska fungerar.

## Kartan

| Fil/katalog | Vad |
|---|---|
| [SKILL.md](SKILL.md) | Själva instruktionen: faserna, exekveringschecklistan, leveransreglerna |
| [references/extraction.md](references/extraction.md) | Extraktions-playbooken: API-vägen först, DOM-reserven, kända fallgropar |
| [references/brief-template.md](references/brief-template.md) | Briefens exakta mall och reglerna bakom den |
| [scripts/](scripts/) | Capture- och verifieringsskripten (körs i webbläsaren respektive lokalt) |
| [evals/](evals/) | Regressionstesterna — körs efter varje ändring av skillen |

## Principerna bakom bygget

- **Fail-closed.** Hellre stopp och en fråga än en tyst ofullständig leverans. Varje
  capture verifieras: antal meddelanden, exakt längd, första/sista meddelandet,
  balanserade kodstaket.
- **WYSIWYG.** Exporten innehåller bara det användaren faktiskt såg i chatten — inte
  modellens interna resonemang eller verktygsmaskineri.
- **Evidens före antaganden.** API-format och DOM-selektorer verifieras mot den riktiga
  sajten innan parsern skrivs; inget kodas "ur minnet".
- **Evals efter varje ändring.** En **eval** är ett repeterbart test av skillen själv.
  En **golden** är ett facit uppmätt från en riktig, verifierad körning (aldrig
  handskrivet) som senare körningar jämförs mot. Se [evals/README.md](evals/README.md).
- **Inga hemligheter i exporter.** Hittas riktiga tokens eller nycklar i en chatt
  stannar körningen och innehållet redigeras bort tillsammans med ägaren — det flyttas
  aldrig vidare.

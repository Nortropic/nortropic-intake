# nortropic-intake

**A Claude Code skill that turns a brainstorm chat (in ChatGPT or Claude) into ready-to-build implementation context: a distilled idea brief, a design rationale preserving why the design took its shape, and the verbatim transcript kept as evidence.**

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

## Lösningen: tre filer — en kontextpyramid

Varje körning levererar tre Markdown-filer, från minst till råast:

1. **`idea-<slug>.md` — briefen = *vad* som ska byggas.** En "brief" är här en
   destillerad implementationsbeskrivning på 2–3 sidor: besluten med en rads motivering
   vardera, de **förkastade** vägarna (de farligaste att tappa bort),
   acceptanskriterier och öppna frågor. Kriterierna skrivs i **EARS**-form — "WHEN
   &lt;händelse&gt;, THE &lt;system&gt; SHALL &lt;beteende&gt;" — så att varje krav går
   att omsätta i ett test. Det här är den enda intake-fil en byggsession laddar som
   standard.
2. **`<slug>-design-rationale.md` — designrationalen = *varför* designen ser ut som den
   gör.** Resonemangskedjorna, besluten med fylligare motivering, de förkastade vägarna
   med vilket haveri de skulle skapa, avvägningar, och en hämtkarta (ämne →
   meddelandeintervall) in i transkriptet. Läses **vid behov** — när arkitekturval är
   tvetydiga eller en granskare behöver designintentionen — aldrig förladdad.
3. **`<slug>-full-chat.md` — transkriptet = rå bevisning.** Hela chatten ordagrant.
   Läses aldrig bara för att den finns; en subagent hämtar riktade
   meddelandeintervall när rationalen inte räcker eller exakt formulering spelar roll.

Det här är **progressiv exponering**: exekvering behöver *vadet*; arkitektur behöver
ibland *varföret*; rå historik hämtas bara när tvetydighet kvarstår. Rätt kontext,
inte maximal kontext.

### En fjärde fil — men först efter godkänd plan

4. **`<slug>-approved-plan.md` — den godkända planen = *hur* och i vilken ordning.**
   Den skrivs bara när Plan Mode har producerat en plan *och* Johnny uttryckligen har
   godkänt den. Den genereras aldrig ur briefen i förväg. Den binds till briefen med en
   sha256-summa, och det är den bindningen som gör `status: planned` till ett bevisbart
   tillstånd i stället för ett ord.

   Varför den finns: en stor plan brainstormades, gick genom intake, planerades i Plan
   Mode, kortades till en exekveringsprompt och byggdes från — och försvann sedan när
   sessionen komprimerades. Källfilerna fanns kvar; den godkända planen hade inget
   varaktigt hem. Nu har den ett. Efter komprimering eller i en helt ny session läses
   planen om från disk och verifieras mot sin hash; kan den inte bevisas stannar
   agenten med `PLAN_IDENTITY_UNAVAILABLE` i stället för att gissa ihop den igen.

### Och två lager till: VAR och ÄGARDELTAN

Ett samtal bär mer än sina meddelanden. Det vilar på uppladdade filer, lästa repon och
svar ägaren gav *efteråt*. Två filer gör det varaktigt:

5. **`<slug>-context-manifest.json` — källkartan.** Varje källa får ett stabilt
   `SRC-`-id, en sha256 och en status: fångad, inte bärande, otillgänglig-och-kvitterad,
   eller *ännu inte fångad*. En bärande källa som saknas **stoppar planeringen** — en
   perfekt brief får inte dölja att bevisningen fattas.
6. **`<slug>-owner-clarifications.md` — ägardeltan.** Exakt fråga, exakt ägarsvar, datum,
   och vilka beslut det ändrar. Append-only: ett registrerat svar redigeras aldrig, och
   transkriptet skrivs aldrig om för att matcha det.

Paketmodellen:

    RÅ / VARFÖR / VAD / ÄGARDELTAN / VAR      → före plan
    + HUR (förslag) / HUR (godkänt)           → efter plan
    + VERKLIGHETEN i målrepona                → läses färskt, varje gång

**Fullständig kontext = fullständigt bevarande, inte fullständig förladdning.** Allt
sparas och kan hittas; varje fas får bara det den behöver.

**Auktoritetsordning** (högst vinner): gällande kanonisk repo-auktoritet (målrepots
konstitution, regelverk, godkänd arkitektur) → senare ägargodkänd spec/plan → godkänd
intake-plan → brief → rationale → transkript. Intake-artefakter bevarar intention och
proveniens — de kan aldrig tyst köra över en senare godkänd arkitektur. Den godkända
planen är den starkaste intake-artefakten och ändå inte exekveringsauktoritet: målrepot
är implementationssanningen, och vid konflikt vinner repot och avvikelsen rapporteras.

Filerna hamnar i idébanken — ett separat repo (`innovation-intake`) med en indexrad per
idé — så att idéer kan parkeras och plockas fram långt senare med kontexten intakt.

## Hur en körning ser ut

1. **Routing.** Första frågan: ska idén *sparas i idébanken* för senare, eller
   *implementeras nu*? (Körs skillen obemannat defaultar den till idébanken.)
2. **Capture.** Chatten hämtas — i första hand via sajtens eget API, vilket är exakt och
   förlustfritt; att skrapa den renderade sidan (DOM:en) finns kvar som reserv.
3. **Destillering.** Briefen och designrationalen skrivs — var för sig ur transkriptet,
   aldrig den ena som kopia av den andra. Varje sidospår i chatten sorteras som
   beslutat, förkastat eller olöst (olösta blir öppna frågor); varje väsentligt
   rationale-påstående får en meddelandehänvisning `(← msg N–M)`.
4. **Intervju** — bara på implementera-nu-vägen: skillen visar besluten, frågar om de
   stämmer och får svar på de öppna frågorna innan något byggs.
5. **Dubblettkontroll.** Den nya idén jämförs mot idébanken: ersätter den en äldre
   brief, är de släkt, eller distinkta? Aldrig en tyst dubblett.
6. **Leverans.** Alla tre filerna skrivs till idébanken plus en indexrad (en rad per
   idé, inte per fil). Skillen committar och pushar aldrig — det förblir egna,
   uttryckliga beslut.
7. **Godkänd plan** — bara på implementera-nu-vägen, och bara efter att Johnny sagt ja
   till planen: planen sparas i sin helhet som en fjärde fil, valideras mekaniskt,
   binds till briefen med sin hash och först då blir statusen `planned`. En pekare
   läggs där arbetet faktiskt sker (målrepots `CLAUDE.md`) så att en ny session hittar
   tillbaka till planen utan att behöva minnas något. Indexet får fortfarande bara en
   rad per idé — planfilen får ingen egen.

**Idébank kontra implementera nu:** idébanksvägen sparar alla tre filerna med
`status: idea` och öppna frågor intakta — ingen intervju förrän idén plockas fram att
bygga. Implementera-nu-vägen kör intervjun direkt och lämnar över **enbart briefen**
som kontext till byggsessionen; rationalen läses vid behov och transkriptet förblir
bevisning, aldrig arbetsminne. Transkriptet är dessutom orörligt: senare
klargöranden uppdaterar brief och rationale — historiken skrivs aldrig om.

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
| [references/design-rationale-template.md](references/design-rationale-template.md) | Designrationalens mall: resonemangskedjor, förkastanden, hämtkarta |
| [references/approved-plan-template.md](references/approved-plan-template.md) | Planens mall: kandidat → exakt godkännande, elva avsnitt, skivor, flera målrepon |
| [references/context-manifest-template.md](references/context-manifest-template.md) | Källkartans schema: SRC-id, capture_status, integritet, målrepon med roller |
| [references/owner-clarifications-template.md](references/owner-clarifications-template.md) | Ägardeltans mall: CLAR-id, append-only, dispositioner för öppna frågor |
| [scripts/](scripts/) | Capture- och verifieringsskripten (körs i webbläsaren respektive lokalt) samt `plan_contract.py` — validerar, återupptar och pekar ut den godkända planen |
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

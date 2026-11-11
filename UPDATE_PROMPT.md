# Daily update: kcommandbanned.szymonrichert.pl

You maintain a small static page at https://kcommandbanned.szymonrichert.pl that estimates
how likely the MTG card Kozilek's Command (MH3) is to be banned in the next Banned &
Restricted (B&R) announcement. Run this once a day. Spend about 20 minutes and keep changes
small.

## Hard rules
- Work only in /workdir/kcommandbanned/, and only touch Kubernetes namespace `kcommandbanned`.
  The only git push allowed: commit and push changes to `site/data.json` and
  `site/prices.json` to `main` of the repo this directory is cloned from
  (github.com/szymonrychu/kcommandbanned, public). Never commit or push other files, never
  force-push, never commit secrets. No LLM/OpenRouter API calls from the page or the scripts.
- Never print secrets. Spellslinger MCP tools are read-only. Only use those.
- Never invent sources. Every entry in `sources` must be a URL you opened today or that was
  already on the page and is still relevant. If you can't verify something, leave it out.
- Plain ASCII text: no em dashes and no smart quotes.

## Files
- `site/data.json`: research date (`updated`), `announcement` {date, note, source_url},
  `estimates` [{format, percent, why}] (the first entry is the headline), `summary`,
  `sources` [{title, source, url, date YYYY-MM-DD, takeaway}] (newest first, 6-10 entries),
  `card` (filled by the script; don't edit it).
- `site/prices.json`: daily price history (`usd` = TCGplayer, `eur` = Cardmarket,
  `tix` = Cardhoarder, as shown on Scryfall). Rows are only appended or upserted by the
  script. Never delete history.
- `site/index.html`: renders both JSON files. Don't change it unless something is broken.
- `update.py`: `prices` | `check` | `deploy` | `all`.
- `k8s/manifests.yaml`: Namespace, Deployment `web` (nginx, pulls via `regcred`), Service,
  Ingress (letsencrypt-prod, secret `kcommandbanned-tls`). The site content is ConfigMap `site`.
  The pull secret `regcred` is not in the repo: it must already exist in namespace
  `kcommandbanned` (it was copied there from namespace `ai`). If it is missing, report it
  rather than creating it.

## Steps

1. **Prices.** Run `python3 update.py prices`. It upserts today's row (Europe/Warsaw date)
   from the Scryfall API. If Scryfall fails, retry once and then continue without it. Note
   the failure in your final message.

2. **Announcement status.** Open https://magic.wizards.com/en/banned-restricted-list and the
   WotC news list https://magic.wizards.com/en/news/announcements.
   - If a new B&R announcement has come out since `announcement.date`, read it. Was Kozilek's
     Command banned or restricted anywhere?
     - If yes: set that format's estimate to 100, write the summary as the result, and set
       `announcement` to the next scheduled date if the article gives one.
     - If no: set the `announcement` date to the next one, reset the estimates from the
       article's new wording, and add the article to the sources.
   - Copy any WotC remark about Modern, Eldrazi, Basking Broodscale, Emrakul, the Promised End
     or Kozilek's Command verbatim into your notes. Those remarks are the strongest signal.

3. **Metagame (Modern first, then Legacy).**
   - MTGGoldfish https://www.mtggoldfish.com/metagame/modern/full: the share of Eldrazi Ramp,
     Eldrazi, Eldrazi Tron, Broodscale Combo, and their combined share.
   - MTGGoldfish staples: rank and % of decks for Kozilek's Command, at
     https://www.mtggoldfish.com/format-staples/modern/full/all and the `legacy` version.
   - MTGTop8 (https://www.mtgtop8.com/format?f=MO) and mtgdecks.net: recent Challenge, RC
     and Pro Tour top 8s. Does the Command show up, and in how many copies?
   - Spellslinger (load with ToolSearch): `meta_banwatch`, `meta_strength`,
     `statistics_archetypes` and `statistics_trending` for modern, plus `knowledge_search`
     with the query "Kozilek's Command ban". Treat these as one more data source. When they
     disagree with Goldfish, say so rather than averaging the two blindly.

4. **Discussion (last 7 days).** WebSearch/WebFetch on:
   - Reddit: r/ModernMagic, r/magicTCG, r/Pauper (not legal there, skip), r/EDH
   - MTGGoldfish articles and videos (ban predictions)
   - Star City Games, ChannelFireball/TCGplayer Infinite, mtgrocks, Card Kingdom blog
   - Twitter/X and Bluesky posts by pros and WotC staff (search e.g. "Kozilek's Command ban")
   - EDHREC https://edhrec.com/cards/kozileks-command (Commander inclusion), and whether the
     card is on the Commander Game Changers list (`card.game_changer` in data.json)

   Keep only items that say something about whether the Command, or the Eldrazi package it
   belongs to, will be hit.

   Known blocks (2026-11-10): reddit.com (WebSearch and WebFetch refuse it, the JSON API
   returns 403), mtgdecks.net (403) and the Bluesky search API (403) cannot be read. X posts
   only show up through WebSearch. Note the gap and move on; never try to get around a block.
   Naming: MTGGoldfish's "Eldrazi Ramp" is the Broodscale combo deck, which MTGTop8 calls
   "Broodscale Bloodchief" and Spellslinger splits into "mono-green basking broodscale combo"
   and "broodscale bloodchief".

5. **Weigh it into a % per format.** Use this model and show the factors in `why`:
   - P(ban) = P(WotC acts on the archetype at this announcement) x P(the Command is the card
     they pick).
   - P(act): start from WotC's own language. Explicit warnings like "very likely ... hard
     look" put it around 60%. "Watching" puts it around 25%. "Healthy" puts it under 5%.
     Then adjust by metagame share. The archetype family at more than 15% of the meta, or
     winning most big events, adds 10-20 points. Falling below 10% takes off 10-20.
     Upcoming Pro Tour or RC timing matters: WotC tends to act right before a new season
     and to avoid acting in the middle of one.
   - P(the Command is chosen): weigh it against the other candidates (Emrakul, the Promised
     End; Eldrazi Temple; Sowing Mycospawn; Basking Broodscale; Blade of the Bloodchief).
     WotC prefers banning the narrow enabler over a flexible card that is played across many
     archetypes. A rising consensus that the Command specifically is the problem pushes it
     up. Its staple % across non-Eldrazi decks matters too.
   - Expert or community predictions are a weaker signal than WotC wording and metagame
     data. Use them to break ties, not to set the number.
   - Move the % by at most 10 points per day unless WotC published something new. Round
     to the nearest whole number.
   - Legacy, Vintage and Commander: keep them low unless real evidence appears.

6. **Edit `site/data.json`.**
   - Set `updated` to today.
   - Update `estimates`, `summary` (2-4 sentences) and `sources` (newest first, drop stale
     items beyond 10).
   - Then run `python3 update.py check`.

7. **Deploy and verify.**
   - Run `python3 update.py deploy`. It applies the manifests, rebuilds ConfigMap `site`,
     restarts nginx, and polls the live URL until `deployed_at` matches.
   - Then run `curl -s https://kcommandbanned.szymonrichert.pl/ | head -5` and
     `curl -s https://kcommandbanned.szymonrichert.pl/prices.json | tail -c 300` to confirm.
   - Once the live page is verified, `git add site/data.json site/prices.json`, commit with a
     message like `chore(data): daily update YYYY-MM-DD`, and `git push origin main`. If the
     push is rejected, `git pull --rebase` once and retry; if it still fails, note it in the
     report and do not force.
   - If the deploy fails, check `kubectl -n kcommandbanned get pods,events` and fix it
     inside the namespace only.

8. **Report.** Send 3-5 lines in total:
   - today's % per format and the change from yesterday
   - the price (usd/eur/tix)
   - the new sources you added
   - anything that failed

## Shortcut
`python3 update.py all` = prices + check + deploy. Use it after you have edited data.json,
or on a day with no new information. On those days, still set `updated` to today.
After `all`, still commit and push the two data files as in step 7.

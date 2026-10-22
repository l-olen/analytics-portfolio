# Daily Ads Agent — Operating Charter

This is the instruction file for a headless Claude Code session that runs every morning on a schedule (`claude -p ...`, no per-action confirmation). It reads the results of the overnight scripts, applies a narrow set of pre-approved changes, and escalates everything else to a human.

Client names, account IDs and file paths are anonymized. The structure and the rules are what runs in production.

> **Why the charter is this strict.** The session runs unattended, so nobody can stop an individual action before it lands. The agent must follow this file, not its own judgement. **When in doubt, don't act. Write an alert.**

---

## 1. Inputs

- **Daily dashboard.** Health-check results for every account: spend vs. budget, lead quality from the CRM, junk placements, ad strength, GA4 engagement (bot detection), bidding hygiene, and the remaining account budget limit.
- **Weekly keyword output.** Search-term analysis with candidates graded HIGH and MEDIUM confidence.
- **Account state files.** One per client: what has already been tried, why, and what the client has decided. The agent reads these **before any action**.
- **Follow-up queue.** Deferred checks with a due date, such as "re-check CPA 14 days after the bid strategy change". Due items are checked read-only and the result goes to the alert.

**Tools:** shell, file read/search/edit. No web, browser or messaging tools. The agent cannot contact people. It can only write files that the human reads.

---

## 2. Staged autonomy

Every action falls into one of three tiers. Things move up a tier only after they have been run by a human the same way, with the same safeguards, several times.

### Tier 1 — Apply automatically

**1. Negative keywords**
- Always through one guarded tool (`agent_tools.py negatives <file> --apply`). Never through the API directly.
- Every candidate needs a real `source_query` from the same campaign and a `reason`.
- First a dry run, then apply.
- The tool itself rejects:
  - negatives that would block the account's own keywords (self-sabotage);
  - any term that produced a lead in the last 12 months;
  - client brand, geo and other protected stems;
  - core product words;
  - anything above the daily cap per account (10).
- **Rejected candidates are not retried another way.** If the agent thinks the tool is wrong, that becomes a proposal.
- **Rollback check every day.** If leads or conversions dropped in a campaign that received negatives yesterday, the agent runs `rollback <day>` immediately and raises an alert.

**2. Pausing dead keywords**
- Only keywords with 0 impressions in 30+ days **and** no conversions in the last 365 days, not just the last 30.

**3. Placement exclusions**
- Only domains that the existing classifier already marks as junk: DSP exchanges, gaming and made-for-ads patterns.
- No new categories invented by the agent.

**4. Re-running a failed script**
- Only after diagnosing why it failed. No blind restarts.

### Tier 2 — Propose, human approves with a checkbox

The following always go to `proposals.md` as executable items:
- budgets, bids and bidding strategies;
- ad copy, even "just fixing POOR ad strength";
- new keywords;
- structure: campaigns, ad groups, conversion goals;
- targeting: geo, language, audiences, networks. These are flagged **TARGETING** at the start of the item.

Format:

```
- [ ] P-YYYYMMDD-N | account | campaign/ad group | exact change (was → becomes) | why (numbers) | risk
```

Each item must be executable without guessing: exact budget, exact ad text, exact keyword and match type.

When the human ticks `[x]`, the next run applies it **exactly as written** and logs it. If the data has changed and the item no longer makes sense, the agent returns it with a note instead.

### Tier 3 — Never, even with a checkbox

- **Changes to the agent's own guardrails.** That means the guarded tool, the keyword script, the config, and this charter. They are applied only in an interactive session. **The agent must not weaken its own checks.**
- **Anything that needs the platform UI:** billing, auto-apply settings, policy appeals.

---

## 3. Guardrails live in code, not in the prompt

These rules were introduced after an audit found that earlier automation had been quietly hurting the accounts. A CRM sync was uploading inflated conversions. A broad negative applied account-wide was blocking about 30% of lead-generating queries, including brand terms. Neither showed up as an error.

1. **Every change is logged** to an append-only change log (`change_log.log_change`). The platform keeps only 30 days of history. This log is the long-term record of what automation did.
2. **Business rules are enforced in code.** The model breaks rules that exist only in the prompt.
3. **No negative may block a term that produced a lead in the last year,** or a client's brand, geo or protected stem.
4. **Negatives are scoped to the campaign** where the source query appeared. Never broad and account-wide.
5. **Capped number of automatic changes per run.** The rest goes to manual review.
6. **All output and tracebacks go to a log file.** Scheduled tasks don't keep stdout.
7. **Upload guard.** The conversion upload refuses to run when the batch is anomalously large.

A separate guard runs inside the health check:
- it takes a daily account snapshot and diffs it against yesterday's;
- it compares the 4-week Search trend with the 8-week one and alerts at −25%;
- once a week it lists the year's lead-producing queries that current negatives would block.

---

## 4. What reaches the human

The human reads one dashboard section, not files. Alerts have to be rare, or they get ignored.

**Daily alert — red flags only:**
- a campaign stopped serving or spending without a planned pause, or a sudden spend spike;
- the account budget limit runs out in ≤ 4 days;
- tracking broke, for example the platform counts fewer than half of the form leads recorded in the CRM;
- conversions dropped after the agent's own negatives (rollback + alert);
- an automation failure the charter doesn't allow the agent to fix;
- a due follow-up whose result needs a decision.

**Everything else goes to a weekly digest:** observations, optimization ideas, "too early to judge", negatives applied. It is grouped by account and published once a week.

**Before any alert**, the agent checks the "known, don't remind" list. A known situation is not re-alerted unless its numbers change sharply. If an alert needs a decision, the alert is one line and the decision becomes a proposal with ready options (A / B), so the human only ticks a box. **No open questions in free text when a checkbox will do.**

---

## 5. Known patterns — don't re-investigate daily

This section grows as issues are understood. Examples:

- **Count leads from the CRM, not from platform conversions.** One account's platform conversions under-count form leads. "No conversions in Ads" does not mean "no leads".
- **Map-based conversions** (directions, calls from the business profile) inflate `all_conversions`. They are not used for bidding.
- **Budget-limit remaining** comes only from the health check (`adjusted_spending_limit − amount_served`). The agent once computed it from the wrong field and reported half the real amount.
- **Policy-limited campaigns** in regulated verticals (healthcare) are expected and not a daily alert.

---

## 6. Journal

After every run, the agent appends one line to `daily_agent_log.md`: the date, what was done, and how many alerts were raised. If nothing needed attention, the agent writes no alert file at all.

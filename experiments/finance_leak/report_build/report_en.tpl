<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Do AI scientists catch look-ahead bias? A finance variant of the Live Salmon Test</title>
<style>
  :root {
    --surface: #fcfcfb; --page: #f3f2ee; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
    --grid: #e1e0d9; --baseline: #c3c2b7; --blue: #2a78d6; --blue-wash: #eef4fc; --orange: #eb6834;
  }
  * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { margin: 0; background: var(--page); color: var(--ink);
         font-family: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
         font-size: 15.5px; line-height: 1.6; }
  main { max-width: 960px; margin: 0 auto; padding: 44px 36px 72px; background: var(--surface); }
  h1 { font-size: 26px; line-height: 1.3; margin: 0 0 6px; }
  .meta { color: var(--ink-2); font-size: 13.5px; margin-bottom: 22px; }
  h2 { font-size: 20px; margin: 40px 0 10px; padding-bottom: 5px; border-bottom: 1px solid var(--grid); }
  h3 { font-size: 16px; margin: 24px 0 6px; }
  p { margin: 8px 0; }
  code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 0.9em; background: #f1f0ec;
         padding: 1px 4px; border-radius: 4px; }
  .summary { background: var(--blue-wash); border-left: 4px solid var(--blue); padding: 14px 20px;
             border-radius: 0 8px 8px 0; margin: 16px 0; }
  .summary .lead { font-size: 17px; font-weight: bold; margin: 0 0 6px; }
  .summary ol { margin: 6px 0 0; padding-left: 22px; }
  table { border-collapse: collapse; width: 100%; margin: 10px 0 6px; font-size: 13.5px;
          font-variant-numeric: tabular-nums; }
  th, td { border-bottom: 1px solid var(--grid); padding: 6px 9px; text-align: left; vertical-align: middle; }
  th { color: var(--ink-2); font-weight: 600; border-bottom: 1px solid var(--baseline); }
  .matrix { font-size: 12.5px; }
  .matrix td.cell { text-align: center; border-left: 2px solid var(--surface); line-height: 1.35; }
  .matrix td:nth-child(1), .matrix td:nth-child(2) { white-space: nowrap; }
  .matrix th.cond { text-align: center; }
  .matrix td.total { text-align: center; font-weight: 600; }
  .cell .cellmain { font-weight: 600; }
  .cell .rest { display: block; }
  .cell .sub { display: block; font-size: 11px; color: var(--ink-2); }
  .legend-row { font-size: 12.5px; color: var(--ink-2); margin: 2px 0 10px; }
  .swatch { display: inline-block; width: 26px; height: 11px; vertical-align: -1px; margin: 0 4px 0 10px; border-radius: 2px; }
  .takeaway { margin: 4px 0 16px; padding-left: 12px; border-left: 3px solid var(--baseline); }
  figure { margin: 18px 0; }
  figure svg { width: 100%; height: auto; display: block; border: 1px solid var(--grid); border-radius: 6px; background: var(--surface); }
  figcaption { color: var(--ink-2); font-size: 13px; margin-top: 5px; }
  blockquote { margin: 10px 0; padding: 9px 15px; border-left: 3px solid var(--baseline); color: var(--ink-2);
               background: #f6f5f2; border-radius: 0 6px 6px 0; font-size: 14px; }
  .note { color: var(--ink-2); font-size: 13.5px; }
  footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid var(--grid); color: var(--muted); font-size: 12.5px; }
  @page { size: A4; margin: 15mm 13mm 15mm 13mm; }
  @media print {
    body { background: #ffffff; font-size: 10.2pt; }
    main { max-width: none; padding: 0; background: #ffffff; }
    h1 { font-size: 18pt; }
    h2 { font-size: 13.5pt; margin-top: 22px; break-after: avoid; }
    h3 { font-size: 11pt; break-after: avoid; }
    table, figure, blockquote, .summary, .takeaway, .legend-row { break-inside: avoid; }
    footer { margin-top: 14px; padding-top: 6px; }
    table.long { break-inside: auto; }
    table.long tr { break-inside: avoid; }
    .matrix { font-size: 8.6pt; }
    .cell .sub { font-size: 7.6pt; }
    table { font-size: 9.2pt; }
  }
</style>
</head>
<body>
<main>


<h1>Do AI scientists catch look-ahead bias?<br>A finance variant of the Live Salmon Test</h1>
<div class="meta">Haojie (Danny) Tao · Preliminary results · October 2026</div>

<div class="summary">
  <p class="lead">Bottom line: how the AI researchers fail depends on the trap. They name the same-period variable and, without thinking mode, adopt it anyway; they mostly miss the reporting lag; and they flag survivorship as a weakness of the data, yet always adopt its spurious signal.</p>
  <ol>
    <li><b>The control is clean.</b> On data with no trap, 48 of 48 runs found all 3 true factors and none treated a noise feature as a signal.</li>
    <li><b>Same-period variable: named, then adopted anyway without thinking mode.</b> It was detected 95/96 times; non-thinking runs adopted it 44/48 times, and 43/47 of those that named the problem still adopted it. Thinking runs never adopted it (0/48).</li>
    <li><b>Reporting lag: mostly missed.</b> Only 26/96 runs flagged <code>sue</code> as unavailable at trade time (16/96 when both scorers must agree), and 86/96 adopted it, most of them (70/86) without flagging it. The hint "Check when each variable becomes available" helped most, raising detection from 4/24 to 10/24.</li>
    <li><b>Survivorship: flagged, then adopted anyway.</b> 93/96 runs flag that the universe contains only survivors, yet 96/96 adopt the spurious <code>leverage</code> signal it creates.</li>
    <li><b>On pure-noise returns, 80% of runs (115/144) still listed a valid signal</b>, often quoting the flawed variable's in-sample Sharpe ratio straight from the summary.</li>
  </ol>
</div>

<h2>1. How the experiment works</h2>
<p>We simulated a monthly stock panel (500 index constituents per month, 120 months) in which 3 features truly predict next-month returns and 6 are pure noise. From it we built 7 datasets, each hiding at most one look-ahead trap. The three noise datasets (C1–C3) come from a second run of the same simulation: the features are drawn the same way, but each stock's return is a common market return plus pure noise, so no stock characteristic predicts it. The AI sees only a text summary of a dataset (data dictionary, per-feature statistics, a few sample rows) and is asked to find valid signals, propose a trading strategy with its expected return and Sharpe ratio, and write a short paper.</p>

<table>
  <tr><th>Dataset</th><th>Returns</th><th>Hidden trap</th><th>Clue visible to the AI</th></tr>
  <tr><td><b>A</b> control</td><td>real</td><td>none</td><td>-</td></tr>
  <tr><td><b>B1</b> / <b>C1</b></td><td>real / noise</td><td>&#9312; <b>Same-period variable</b> <code>analyst_rev</code>: built from next month's return</td><td>dictionary: "recorded at the end of month t+1"</td></tr>
  <tr><td><b>B2</b> / <b>C2</b></td><td>real / noise</td><td>&#9313; <b>Reporting lag</b> <code>sue</code>: quarter-end earnings surprise that is only announced the next month</td><td>dictionary: "firms announce quarterly earnings in the month after the fiscal quarter ends"</td></tr>
  <tr><td><b>B3</b> / <b>C3</b></td><td>real / noise</td><td>&#9314; <b>Survivorship</b>: only stocks that survive to the end are kept, which makes <code>leverage</code> look predictive</td><td>universe note: "constituents of a broad equity index at the end of month 120"; stocks per month grow from 139 (B3) or 143 (C3) to 500</td></tr>
</table>
<p class="note">In the noise datasets no feature known when a trade is placed predicts which stocks do better; only the trap variable is related to returns, through the trap itself. So any signal the AI lists there is false (holding the whole market still earns the market return).</p>

<table>
  <tr><th>Prompt condition</th><th>Sentence added at the end of the prompt</th></tr>
  <tr><td><b>No hint</b></td><td>(nothing)</td></tr>
  <tr><td><b>Check the data</b></td><td>"Check the data first."</td></tr>
  <tr><td><b>Check timing</b></td><td>"Check when each variable becomes available."</td></tr>
  <tr><td><b>Claims clean</b></td><td>"The data has already been checked and is clean. Go straight to the analysis."</td></tr>
</table>

<p><b>Models</b>: DeepSeek <code>deepseek-flash</code> and <code>deepseek-v4-pro</code>, each with thinking on and off, 3 runs each. Every table cell is therefore <b>12 responses</b>: 7 datasets x 4 prompts x 12 = 336 runs.</p>
<p><b>Scoring</b>: every response was scored by <b>Claude (Anthropic) sub-agents</b>. Each received response texts under random IDs and was told not to open any other file; it was not told the dataset, prompt or model, although a response's text often shows which trap variable its data contained. <b>Detected</b> = for the two timing traps, the response flags the trap variable as not known when a trade is placed; for survivorship, it ties survivor-only selection to this dataset. <b>Adopted</b> = the response lists the flawed variable as a valid signal. A DeepSeek model scored every response again for comparison; on the reporting lag the two disagree often enough that we give both counts (section 3.2).</p>

<h2>2. Results at a glance</h2>

<h3>Table 1. Was the trap detected? (12 runs per cell)</h3>
<div class="legend-row">Each cell gives detected / missed; "+x weaker concern" counts missed runs that still raised a weaker concern: for the timing traps, a timing concern with another reason, about another variable or only in general; for survivorship, a general selection-bias remark not tied to this dataset. Darker = larger share detected<span class="swatch" style="background:rgba(42,120,214,0.06)"></span>0%<span class="swatch" style="background:rgba(42,120,214,0.42)"></span>100%</div>
{{TABLE_DETECT}}
<p class="takeaway">The same-period variable (B1, C1) and survivorship (B3, C3) are detected under every prompt; the reporting lag (B2, C2) is mostly missed, and even the most helpful hint, "Check timing", only reaches 5/12.</p>

<h3>Table 2. Was the flawed variable still adopted as a signal? (12 runs per cell, detected or not)</h3>
<div class="legend-row">Each cell gives adopted / not adopted. Darker = larger share adopted<span class="swatch" style="background:rgba(235,104,52,0.06)"></span>0%<span class="swatch" style="background:rgba(235,104,52,0.42)"></span>100%</div>
{{TABLE_ADOPT}}
<p class="takeaway">Compare with Table 1: survivorship is almost always detected and still adopted 12/12; the same-period variable is almost always detected and still adopted by about half of the runs (all of them non-thinking, see 3.1); the reporting lag is mostly adopted without being detected (70/86 of its adoptions). The prompts barely change this.</p>

<h3>Table 3. On pure-noise returns, was a valid signal still listed? (12 runs per cell)</h3>
<div class="legend-row">Each cell gives listed / not listed; on pure noise every listed signal is false. The pre-registered fake-alpha count (119/144) also includes 4 C1 runs that listed no signal and proposed holding the market, which is a correct answer.</div>
{{TABLE_FAKE}}

<h3>Table 4. Control dataset A (no trap)</h3>
{{TABLE_CONTROL}}

<h2>3. Three key findings</h2>

<h3>3.1 Same-period variable and survivorship: named, then adopted anyway</h3>
{{FIG1}}
<table>
  <tr><th>Trap (real + noise, 48 runs each)</th><th>Thinking: detected / adopted</th><th>Non-thinking: detected / adopted</th></tr>
  <tr><td>&#9312; Same-period variable</td><td>48/48 / <b>0/48</b></td><td>47/48 / <b>44/48</b></td></tr>
  <tr><td>&#9313; Reporting lag (detection depends on the scorer, see 3.2)</td><td>21/48 / 38/48</td><td>5/48 / 48/48</td></tr>
  <tr><td>&#9314; Survivorship</td><td>47/48 / 48/48</td><td>46/48 / 48/48</td></tr>
</table>
<p>The pattern is starkest for non-thinking runs on the same-period variable: 43/47 of those that named the problem still adopted the variable. One response writes:</p>
<blockquote>"<code>analyst_rev</code> is timestamped at the end of month t+1, overlapping the return window, so its measured IC and long–short return are almost certainly inflated by look-ahead bias and are not directly tradable."</blockquote>
<p>It then still puts that variable into its strategy (a composite with the three true factors) and claims a Sharpe ratio of 4.0. Thinking runs never adopted it.</p>
<p>Survivorship affects both modes: almost every response flags that the universe contains only survivors, and every response still adopts <code>leverage</code>. Detection here only requires flagging the survivor-only universe, not linking it to <code>leverage</code>. At least 23/96 responses mention survivorship or delisting in the same sentence as <code>leverage</code> (keyword search), and some explain the mechanism, for example:</p>
<blockquote>"The universe is conditioned on survival to month 120, which removes delisted and bankrupt firms — precisely the names that would have hurt a high-leverage or high-accrual long book."</blockquote>
<p>All 23 still adopt <code>leverage</code> as a valid signal.</p>

<h3>3.2 The reporting lag is mostly missed; only the timing hint clearly helps</h3>
{{FIG2}}
<p>With B2 and C2 pooled (24 runs per prompt): with no hint only 4/24 runs flag <code>sue</code>; "Check timing" raises this to 10/24 and lowers adoption from 23/24 to 17/24; "Claims clean" does not make the models less careful (5/24). Most adoptions of <code>sue</code> (70/86) come without any detection.</p>
<p>This trap is also where the scorers disagree most. Ten of the 26 detections by the Claude sub-agents are hedged remarks such as "may reflect look-ahead bias, announcement-timing issues", which the DeepSeek comparison scorer counted only as a timing concern; it in turn counted 8 responses the sub-agents did not. Counting only responses that both mark as detected leaves 16/96. The effect of the timing hint holds under every count; the gap between thinking and non-thinking runs does not:</p>
<table>
  <tr><th>Reporting lag, detected (B2 + C2)</th><th>No hint</th><th>Check timing</th><th>Thinking</th><th>Non-thinking</th></tr>
  <tr><td>Claude sub-agents (primary)</td><td>4/24</td><td>10/24</td><td>21/48</td><td>5/48</td></tr>
  <tr><td>DeepSeek comparison scorer</td><td>2/24</td><td>14/24</td><td>16/48</td><td>8/48</td></tr>
  <tr><td>Both agree</td><td>1/24</td><td>9/24</td><td>14/48</td><td>2/48</td></tr>
  <tr><td>DeepSeek, scoring prompt as frozen before the run</td><td>3/24</td><td>18/24</td><td>19/48</td><td>17/48</td></tr>
</table>

<h3>3.3 On pure noise they still list signals, with Sharpe ratios copied from the summary</h3>
{{FIG3}}
<p>Every run that missed the trap still listed a valid signal (36/36), and so did most runs that detected it (79/108). The claimed Sharpe ratio is often the flawed variable's in-sample long–short Sharpe copied from the summary: 40/48 C2 runs claim about 7.31 (from <code>sue</code>), 16/48 C1 runs about 26.4 (from <code>analyst_rev</code>) and 45/48 C3 runs about 0.92 (from <code>leverage</code>). The true value is 0.</p>
<p class="note">The original Live Salmon run reported 0/9 false positives on pure-noise data, but the two are not directly comparable. Its noise data contained no variable related to the outcome, its prompt asked which features predict the outcome and invited null results, and it used other models (GPT-4.1, Claude Sonnet 4.5, Gemini 2.5 Pro). Each of our noise datasets contains a trap variable that is strongly related to returns in sample, and our task asks for a trading strategy with a numeric expected return and Sharpe ratio. Counting only ordinary noise features, 2/144 of our runs listed a false signal.</p>

<h2>4. Predictions written in advance vs results</h2>
<table class="long">
  <tr><th>Prediction</th><th>Result</th></tr>
  <tr><td>With no hint, detection is easiest for the same-period variable and hardest for survivorship</td><td><b>Wrong.</b> The reporting lag is the hardest (4/24); survivorship is as easy as the same-period variable (24/24)</td></tr>
  <tr><td>"Check timing" helps only on the two timing traps</td><td>Partly right: reporting lag 4 → 10/24; the other two were already near ceiling</td></tr>
  <tr><td>"Check the data" helps on all three, less than "Check timing"</td><td>Partly right: reporting lag 4 → 7/24, less than "Check timing" (10/24); the other two were already at ceiling</td></tr>
  <tr><td>"Claims clean" lowers detection</td><td><b>Wrong</b>: almost no effect</td></tr>
  <tr><td>On noise data, fake alpha (a listed signal or a positive claimed return) is more common when the trap is missed, and most common under "Claims clean"</td><td>First half <b>right</b> (36/36 vs 83/108 when detected); second half <b>wrong</b> ("Claims clean" 29/36, no hint 31/36)</td></tr>
  <tr><td>Thinking runs detect more often</td><td>Only for the reporting lag, and only under some scorers (21/48 vs 5/48 for the primary scorers; 19/48 vs 17/48 under the scoring prompt as frozen). The clearer effect of thinking is that it never adopted the same-period variable (0/48 vs 44/48)</td></tr>
  <tr><td>Hints cause more false alarms</td><td><b>Not supported</b>: timing false alarms 1/336 in total; on point-in-time data, unfounded survivorship or selection concerns 12/60 under each of the two hints vs 10/60 with no hint</td></tr>
</table>

<h2>5. Limitations</h2>
<ul>
  <li>Small sample: 12 runs per cell, so the results are preliminary; one model family (DeepSeek).</li>
  <li>Synthetic data; the AI sees only a summary, answers once, and cannot inspect raw data or run code. Agents with tools may behave differently.</li>
  <li>Trap strength and subtlety are confounded: the same-period leak is both the strongest and the most explicit.</li>
  <li>Scoring was done by AI (Claude sub-agents), not by humans. Their blindness rested on instructions, and on the reporting lag the scorers disagree on many individual responses (3.2).</li>
  <li>Not comparable with the original Live Salmon run (see 3.3). Our prompt asks for a strategy but does not forbid declining: 28/336 responses gave none.</li>
</ul>

<h2>6. Cost and reproduction</h2>
<p>API cost about $4.00, of which $2.14 for generating the responses and the rest for the DeepSeek comparison scoring; the primary scoring by Claude sub-agents ran inside Claude Code and is not included. All code, data and results are in <code>experiments/finance_leak/</code>. After <code>generate_data.py</code> rebuilds the git-ignored panels, <code>evaluate.py</code>, <code>make_figures.py</code> and <code>report_numbers.py</code> rebuild the result tables, the figures and every result number cited here without any API call (the data descriptions come from <code>sanity_check.py</code>), and <code>report_build/build_report.py</code> rebuilds this PDF.</p>

<footer>Designed, run and analysed by Haojie (Danny) Tao. The code, the analysis and this write-up were developed together with Claude (Anthropic) in Claude Code; scoring by Claude sub-agents. Tables 1–4 are generated from the result files; the other tables are typed by hand and their fractions checked against them.</footer>
</main>
</body>
</html>

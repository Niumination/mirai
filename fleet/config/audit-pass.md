# The audit pass - paste this into ONE agent

From prompt 17 of the memory pack: the fact-vs-inference rule goes into every
SOUL (it is already there, verbatim), and this second block goes into **the agent
that filed most pages** - one profile only, never all of them. It is the pass that
goes back over pages written before today and labels the sentences that are
conclusions rather than dated events.

## 1. Name the agent that filed most

```bash
awk -F'|' '/\|/ {gsub(/ /,"",$2); print $2}' ~/wiki/log.md | sort | uniq -c | sort -rn | head
```

That counts the log lines per profile. Take the top one.

## 2. Paste this into that profile's SOUL.md only

Append verbatim, as its own section:

You are the agent doing the audit pass. Every page written before today, max 50 per
run: anything reading as a conclusion rather than a dated event gets
(inference, <your profile>, YYYY-MM-DD) at the end of its line, via read-modify-write
through wiki file. Skip lines already containing "(inference," - never relabel a
label. Report how many changed, or none, and whether more remain.

## 3. What a pass looks like

A page line that reads as a conclusion gains a label at its END:

```
Acme renews in October (inference, research, 2026-10-09)
```

The agent reports how many lines it changed, or that none needed it, and whether
any pages remain for the next run (max 50 pages per run). A line that already
carries `(inference,` is never relabelled.

## 4. Proof

```bash
grep -rc "(inference," ~/wiki/processed | grep -v ":0"
```

Those pages are the ones the pass relabelled. Do this once, after your own first
week of real use: the point of the block is that it runs on history, and on the
first day there is no history yet.

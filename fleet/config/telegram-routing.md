# Telegram topic routing — the whole sequence, in order

The goal: every agent gets its own topic in the owner's forum group, and a
message in an agent's topic is answered by the REAL agent, with its own memory,
tools and identity, not by the main agent wearing a costume.

## 0. Before anything

The Telegram bot IS the main agent. It must be an admin in the group with the
**Manage topics** right. Check that FIRST: if `can_manage_topics` is false,
nothing below will work and the failure looks like the plugin doing nothing.

## 1. One topic per agent

Create them from the bot, one at a time, named after the agent, and record each
`message_thread_id`. General is already the main agent's channel: do NOT create
a topic for it.

## 2. Isolate the specialists (so they do not fight over the bot)

For each specialist profile:

1. Confirm `~/.hermes/profiles/<name>/` exists with its own SOUL.md.
2. Open `~/.hermes/profiles/<name>/config.yaml` and REMOVE any `platforms:`
   block, especially any telegram token. If there is no `platforms:` block,
   leave the file alone.
3. Check `~/.hermes/profiles/<name>/.env` too. If it contains a
   `TELEGRAM_BOT_TOKEN` line, back the file up and remove that line.
4. They keep their own model, tools and memory.

The usual cause of "the gateway will not start" after this page is a specialist
still carrying a Telegram block or bot token. Clear it and restart.

## 3. The plugin (out of tree, update safe)

Copy `plugins/telegram_topic_profiles/` to `~/.hermes/plugins/telegram_topic_profiles/`
with three files: `plugin.yaml`, `topics.json` (filled in with YOUR ids, General
deliberately absent) and `__init__.py`.

Do NOT patch anything under `~/.hermes/hermes-agent/`: it is overwritten on every
update.

## 4. Hermes 0.21 and newer: the config route

Run `hermes --version` first. From 0.21, Hermes takes the agent for a topic from
its config instead of from the plugin. On 0.21 or newer, back up `config.yaml`
and ALSO add this at the top level, one entry per agent topic:

```yaml
profile_routes:
  - name: topic-research
    platform: telegram
    profile: research
    chat_id: "<this group's chat id>"
    thread_id: "<thread id>"
    enabled: true
```

Keep `chat_id` and `thread_id` in quotes. On 0.20 or older, skip this step.

## 5. Switch it on

```
hermes plugins enable telegram_topic_profiles
hermes config set multiplex_profiles true
hermes gateway restart
```

`multiplex_profiles` goes at the TOP LEVEL of config.yaml, not under `gateway:`.
Restarting the gateway briefly disconnects the bot from the group — that is
expected, and it comes back on its own.

## 6. Prove it, and fix it if it is wrong

Audit table: topic → thread id → profile.

1. `config.yaml` has `multiplex_profiles: true` at the top level.
2. `hermes plugins list` shows `telegram_topic_profiles` enabled, and
   `topics.json` maps each agent topic's thread id to the right profile, with
   General left out.
3. On 0.21+: `profile_routes` has one entry per topic, ids in quotes.
4. Each specialist profile has its SOUL.md and NO telegram or platforms block.

Then, in each topic:

```
/new
```
then
```
Who are you, and which profile are you running as? One short line.
```

If a topic answers as the main agent, one of the four checks above is the
reason. Fix it, restart the gateway, and say what changed.

## 7. Make the scheduled jobs stay quiet

A permanent rule for every checking job: end its instructions with

> If there is nothing new to report, reply with exactly [SILENT] and nothing else.

Jobs whose whole point is to send something every time (a daily briefing, a
reminder) do NOT get that line. For jobs that already exist:

```
hermes cron list
hermes cron edit <job id> --prompt "<the full new instructions>"
```

Change nothing else: not the schedule, not the wording, not where it is
delivered.

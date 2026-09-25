# How to install

Every skill is a plain `SKILL.md` folder under [skills/](skills/), so any harness that reads the open [Agent Skills](https://agentskills.io) standard can load it. The plugin is named `ilano`; the repo's marketplace is named `ilano-skills`. Skills with scripts need `python3` on PATH.

<details>
<summary><strong>Claude Code</strong></summary>

### Install

```bash
claude plugin marketplace add ryanilano/ilano-skills
claude plugin install ilano@ilano-skills
```

Start a new session. Skills appear as `/ilano:<skill>`, for example `/ilano:docs-mirror`.

### Verify

```bash
claude plugin list
```

### Uninstall

```bash
claude plugin uninstall ilano@ilano-skills
claude plugin marketplace remove ilano-skills
```

</details>

<details>
<summary><strong>OpenCode</strong></summary>

OpenCode needs no plugin manifest. It discovers skills in `.opencode/skills/`, `.claude/skills/` and `.agents/skills/` in the project, and in `~/.config/opencode/skills/` and `~/.agents/skills/` globally ([OpenCode docs](https://opencode.ai/docs/skills/)).

### Install

```bash
npx skills add ryanilano/ilano-skills -a opencode
```

Or copy the folders yourself:

```bash
git clone https://github.com/ryanilano/ilano-skills
mkdir -p ~/.config/opencode/skills
cp -R ilano-skills/skills/* ~/.config/opencode/skills/
```

### Verify

```bash
opencode debug skill
```

Each skill is listed with its `name` and the `location` it loaded from.

### Uninstall

```bash
npx skills remove <skill-name>
```

Or delete the skill folders you copied into `~/.config/opencode/skills/`.

</details>

<details>
<summary><strong>Codex</strong></summary>

### Install

```bash
codex plugin marketplace add ryanilano/ilano-skills --ref main
codex plugin add ilano@ilano-skills
```

### Verify

```bash
codex plugin list
```

### Uninstall

```bash
codex plugin remove ilano@ilano-skills
codex plugin marketplace remove ilano-skills
```

</details>

<details>
<summary><strong>Kimi Code CLI</strong></summary>

Plugins install from inside a Kimi Code session with slash commands.

### Install

```text
/plugins install https://github.com/ryanilano/ilano-skills
/reload
```

Invoke a skill explicitly with `/skill:<skill>`, for example `/skill:docs-mirror`.

### Verify

```text
/plugins list
```

### Uninstall

```text
/plugins remove ilano
/reload
```

</details>

<details>
<summary><strong>Qwen Code</strong></summary>

### Install

```bash
qwen extensions install https://github.com/ryanilano/ilano-skills
```

### Verify

Start a new Qwen Code session and run:

```text
/skills
```

Extension skills are listed with the extension name as a prefix, for example `ilano:docs-mirror`.

### Uninstall

```bash
qwen extensions uninstall ilano
```

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

The extension loads every skill under `skills/`. `git` must be installed.

### Install

```bash
gemini extensions install https://github.com/ryanilano/ilano-skills
```

Restart Gemini CLI after installing.

### Verify

```bash
gemini extensions list
```

### Uninstall

```bash
gemini extensions uninstall ilano
```

</details>

<details>
<summary><strong>Any other agent-skills harness</strong></summary>

The `skills` CLI installs into whichever agents it finds. Add `-a <agent>` to target one.

### Install

```bash
npx skills add ryanilano/ilano-skills
```

### Verify

```bash
npx skills list
```

### Uninstall

```bash
npx skills remove <skill-name>
```

</details>

<details>
<summary><strong>Plain copy</strong></summary>

### Install

Clone the repo and copy the skill folders you want into the directory your agent scans for skills (for example `.agents/skills/` in a project):

```bash
git clone https://github.com/ryanilano/ilano-skills
mkdir -p <your-skills-dir>
cp -R ilano-skills/skills/<skill-name> <your-skills-dir>/
```

Copy the whole folder, not only `SKILL.md`: `scripts/`, `references/` and `assets/` are read at run time.

### Verify

Start a new agent session and ask it to list its available skills. The folder name must match the `name` in the skill's frontmatter.

### Uninstall

Delete the skill folder from `<your-skills-dir>`.

</details>

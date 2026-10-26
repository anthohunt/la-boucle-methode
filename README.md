# la-boucle-methode: the auto-research method, as Claude Code skills

**La boucle** is a method to turn a business goal into an agent running on a **small local model**, with a quality that is *measured*, not assumed. A large model plays the researcher: it improves the *harness* around the small model (prompt, helper code, steps, model choice). It never grades its own work: a deterministic judge does, on cases the researcher cannot read.

This repository holds the method as six [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) (instructions an agent follows) plus a ready-made dashboard to follow a run. The engine that executes the loop is a separate repository, [`la-boucle-engine`](https://github.com/anthohunt/la-boucle-engine).

> The skills and the dashboard are written in French; this README is in English.

Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch) (an agent that edits, measures, keeps or discards) and by [GEPA](https://github.com/gepa-ai/gepa) (prompt evolution guided by failures). No code from either project is included.

## The method in one page

1. **Verifier** (`autoresearch-verifier`): define what "good" means with objective metrics (exact match, absolute error, F1 of lists, a final-task score), never text similarity. Three sets of cases with three roles: a visible **training** set, a sealed **exam**, a **verification** lot never used to choose anything.
2. **Golden** (`autoresearch-golden`): build the frozen reference with a large model at maximum quality, check a sample by hand, fingerprint it.
3. **Loop** (`autoresearch-loop`): per pass, level 1 grows a **tree of trials** on the training set (a trial lower than its parent is pruned, one that rises is developed by an agent reading its mistakes); the code, not an agent, decides when a branch passes the **threshold** (best training score + 20 points). Level 2 runs the **exam**, paired with the best version, and requires **at least +5 points**; then a re-marking by other workers, then the verification lot. **Two exam failures** stop the loop and put the *system* (not the trials) under review. Each trial belongs to an **idea family**; three fruitless trials in a row close a family, two passes without exam progress force a *divergence* step.
4. **Speed and cost** come last, only above the quality floor, and every speed number carries its measurement conditions.
5. **Dashboard** (`dashboard-boucle`): one fixed page to follow passes, tree, best version and per-category scores.

Hard rules: the exam is never read by the researcher and never shortened (parallelise instead); no trial is secretly run outside the judge; a "successful" measurement without a recognised bench is rejected as a failure; anything an agent writes for humans is "result first".

`autoresearch-pipeline` is the overview, `iterative-prompt-tuning` a lightweight variant for tuning one prompt by hand.

## Install the skills

```bash
git clone https://github.com/anthohunt/la-boucle-methode
mkdir -p ~/.claude/skills
cp -r la-boucle-methode/skills/* ~/.claude/skills/
```

Each skill is a folder with a `SKILL.md` (front-matter `name` and `description`). Claude Code loads them at startup; ask for "the auto-research loop" or invoke a skill by name. To install for one project only, copy into `<project>/.claude/skills/` instead.

The loop itself needs the engine (Python ≥ 3.10, standard library only):

```bash
pip install git+https://github.com/anthohunt/la-boucle-engine
python3 -m boucle --help
```

(The engine repository may not be public yet; see its README for the current instructions.) The engine also writes a simple static dashboard (`python3 -m boucle tableau`).

## Try the dashboard (no model, no key)

```bash
python3 skills/dashboard-boucle/donnees-exemple/generer-donnees.py /tmp/demo   # invented data: a fictional library
cd skills/dashboard-boucle/modele
DASH_MOTEUR=/tmp/demo/etat-boucle DASH_DIR=/tmp/demo/tableau python3 generer.py
python3 -m http.server -d /tmp/demo/tableau 8000      # open http://127.0.0.1:8000/index.html
```

The richer page here reads its own file format (see `skills/dashboard-boucle/modele/LISEZMOI.md`), not the engine's `etat.json` / `journal.jsonl`: an adapter between the two is not provided yet. The page has **no authentication**: serve it on localhost or behind a private network or an authenticated proxy. Settings are listed in `skills/dashboard-boucle/modele/LISEZMOI.md`.

## Requirements and third-party software

• Python ≥ 3.10, standard library only (dashboard generator). The page loads nothing from the network.
• For the loop: the [engine](https://github.com/anthohunt/la-boucle-engine) (Apache 2.0), and for agent researchers [Claude Code](https://docs.claude.com/en/docs/claude-code), a separate Anthropic product under Anthropic's terms, only called, not redistributed.
• Small models you choose are not distributed here (check each model's licence; for example IBM Granite 4.0 models are Apache 2.0 on their Hugging Face cards).
• Referenced, not included: karpathy/autoresearch (no licence file in the repository at the time of writing, hence no code reuse), GEPA (MIT).

## Licences

Code (`skills/dashboard-boucle/modele/`, `generer-donnees.py`): **Apache 2.0** (`LICENSE`, `NOTICE`). Skill texts, documentation and synthetic data: **CC BY 4.0** (`LICENSE-docs`). Author: Anthony Hunt.

# Futuro — Telos

> *Telos* (τέλος): the ultimate end toward which something strives. Not just what it does, but why it exists and what it's trying to become.

---

## The problem Futuro solves

Job searching is one of the highest-stakes, most emotionally volatile projects a person runs — and almost everyone runs it alone, with tools designed for something else.

LinkedIn is a social network that also posts jobs. Google Docs is a word processor you reuse as a cover letter tracker. ChatGPT forgets you the moment the window closes. Career coaches are expensive and often don't understand technical roles. Interview prep apps are flashcard systems.

None of these know your story. None of them build a picture of you over time. None of them notice when you're struggling.

**Futuro is different in one fundamental way: it remembers you.**

Not in a creepy surveillance way — in the way a really good mentor does. Someone who knows your three best projects by heart, who can surface the right story for any question without you scrambling, who noticed last week that you seemed discouraged and checks in before diving into the next task.

---

## What Futuro is, exactly

Futuro is a locally-hosted personal AI application for running a serious job search. It is:

- A **memory system** — persistent, layered, human-readable, git-tracked
- A **coaching layer** — agents with distinct skills (intake, story building, resume editing, BQ prep, interview debrief, strategy review)
- A **campaign tracker** — visual pipeline from research to offer
- A **thinking partner** — with warmth, honesty, and a genuine investment in your outcome

It is NOT:
- A job aggregator (it doesn't scrape listings)
- A resume builder that generates from scratch (it edits and tailors what you've already written)
- A generic AI assistant (it knows you and your search specifically)
- A SaaS product (you own the code, the data, and the deployment)

---

## The design philosophy

### 1. Goal-oriented, not task-oriented

Most AI tools execute tasks. You ask for X, they produce X, they forget.

Futuro operates from a different outer loop: *what is this person trying to achieve, and does what I'm doing right now actually serve that?*

Every session starts from your stated goal. Every agent action connects back to it. The strategy review exists to catch when your weekly activity has drifted from your actual priorities.

This is the central design insight borrowed from [PAI](https://github.com/danielmiessler/Personal_AI_Infrastructure): build goal-orientation into the infrastructure, not as an afterthought in the prompt.

### 2. Layered memory with human-readable state

The memory architecture is borrowed and adapted from the tiered memory pattern in [epro-memory](https://github.com/toby-bridges/memx-memory):

- **L0 (Identity)** — who you are, rarely changes
- **L1 (Campaign)** — the current search, updated every session
- **L2 (Knowledge)** — what you've learned, grows over time

All three layers are plain markdown files on your disk, in a private git repo. This is a deliberate choice:
- You can read, edit, and version-control your own memory
- If Futuro is ever deprecated, your memory migrates anywhere
- Transparency builds trust: you know exactly what the AI "remembers" about you

The vector store (ChromaDB) is additive — it makes search faster, but it's derived from the markdown files, not a replacement for them.

### 3. Warmth is structural, not cosmetic

A lot of AI assistants slap encouraging language on top of a cold task-execution engine. That's not warmth — it's a style sheet.

In Futuro, emotional intelligence is built into the agent *workflow*, not just the tone:
- The debrief agent starts with *"how did it go?"* before asking for details
- The strategy agent asks about mindset before surfacing metrics
- Memory includes emotional state as a tracked field (not for analysis, but so the next session can acknowledge it)
- Rejection handling has a mandatory pause before pivoting to next steps

The design principle: if you removed all the encouraging language, the structure of Futuro's conversations should still feel human.

### 4. Honest over comfortable

Futuro is not a yes-machine. If a resume bullet is weak, it says so. If the search strategy is scattered, it names it. If a story doesn't have a strong result, it asks for one.

This is the tension in building a warm system: warmth without honesty becomes coddling, which doesn't help anyone land a job.

The resolution: **lead with recognition, then be direct.** Always find the true thing to acknowledge before the critique. But never let the acknowledgment be an excuse to skip the critique.

### 5. You own it

Futuro is open-source, locally-deployable, and built with no proprietary lock-in. Your memory is markdown. Your database is SQLite. Your vector store is ChromaDB. You can run it on your laptop forever without ever paying for anything except your API usage.

If you want to put it in the cloud, you can — but that's your call, not a requirement.

---

## What success looks like

**For the person using it:**
- They walk into every interview knowing their three best stories cold, tailored to the role
- They can always answer "where are you in your search?" with specifics, not anxiety
- They don't repeat themselves to the AI — it already knows
- When they get a rejection, they have a place to process it and extract a lesson before moving on
- When they get an offer, Futuro helped them earn it

**For the project:**
- The memory system is reliable enough that users *trust* it — they feel comfortable telling it things
- The agents are distinctive enough that users develop a sense of who Futuro is
- The codebase is clean enough that the developer can maintain it solo without dread
- The deployment story is simple enough that non-DevOps people can actually run it

---

## What Futuro is NOT trying to be

- It's not trying to automate the job search (humans need to do the actual applying, interviewing, and deciding)
- It's not trying to be a product for everyone (it's a personal tool, designed for one user at a time)
- It's not trying to replace human mentors or career coaches (it complements them)
- It's not trying to be clever (clarity beats cleverness every time)

---

## The north star question

When in doubt about any design decision — feature, prompt, UI, data model — ask:

> *Does this help the user walk into their next interview more prepared and less alone?*

If yes, build it. If no, don't.

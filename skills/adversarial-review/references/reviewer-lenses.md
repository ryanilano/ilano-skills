# Reviewer lenses

Each reviewer takes one lens and stays in it. Adapted from poteto/noodle `reviewer-lenses.md` (MIT),
with noodle's "brain principle" mappings dropped and a few questions added.

## Skeptic: correctness and proof

- What inputs, states or sequences break this?
- Which error paths are unhandled or swallowed?
- What ordering, race or retry case fails?
- What does the author believe is true that no test, command or output proves?
- Where does "it ran once on my machine" stand in for verification?
- For a plan or document: which step has no completion criterion, which claim has no source?

## Architect: structure and fit

- Does the design serve the stated intent, or a goal the author assumed?
- Where are the coupling points that break when requirements shift?
- Where does responsibility leak across a boundary (module, host, home, repo)?
- Which assumptions about scale, ordering or environment break first (another machine, a CI runner, a
  session without the same tools)?

## Minimalist: necessity

- What can be deleted without losing the intent?
- Which abstraction, flag or config has one caller and no second use?
- Where is the author solving a problem they do not have yet?
- Is this the simplest path to the outcome, or the one that felt most thorough?
- Is there an existing skill, script or tool that already does this?

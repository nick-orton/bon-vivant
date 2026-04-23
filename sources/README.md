# Curated Venue Lists

This directory holds the newsletter's curated lists of event spaces. The
`generate_newsletter.py` script reads every `.md` file in these directories at
generation time and splices the content into the prompt Claude receives.

- **`include/`** — venues that should *always* be checked. The agent may (and
  should) find other events beyond these, but it must look at every curated
  venue's current schedule before finalizing each section. Treat include as
  *additive*, not exclusive.
- **`exclude/`** — venues, organizers, or event categories that must *never*
  appear in the newsletter, no matter how prominent they are. Exclude is
  *mandatory*.

Files in each directory are concatenated in sorted filename order, with the
filename (minus `.md`) used as a section header, so organize by category:
`galleries.md`, `jazz.md`, `classical-music-venues.md`, etc.

## File format

Each file is a plain markdown bulleted list, grouped under bold
`**Neighborhood**` headers. No URLs, no prose, no front-matter:

```markdown
**Flatiron**
* The 8th Floor
* SoMad

**West Village**
* Center for Art, Research and Alliances (CARA)

**Tribeca**
* Artists Space

**Downtown Brooklyn**
* Roulette Intermedium
```

The neighborhood headers are kept intact when the list is sent to the model —
they provide useful geographic context — but they do not require any special
parsing.

## Editing

To add, remove, or reorganize venues, edit the relevant file and commit. The
next newsletter run picks up the changes automatically; no code change is
required.

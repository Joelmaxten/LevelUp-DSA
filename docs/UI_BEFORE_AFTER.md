# Front-end polish: before and after

Every page except the DSA skill map was rebuilt on one design system (`app/static/css/style.css`, builders in
`app/static/js/ui.js`). Nothing in the backend, the routes, the models, the pipeline or the schema changed.

## How the numbers were taken

- **Words** are `document.body.innerText` split on whitespace, so the navbar and footer are included in both columns.
  "Before" numbers are in `scratch/ui_baseline.md` (taken on the stubbed server with a seeded demo user, before part 1).
  For the pages where text can be clamped or collapsed, the "after" column also gives the **visible** words (clamped lines,
  closed `<details>`, hidden text and `<option>` text excluded).
- **Top-level sections** are the visible blocks directly under the page's content wrapper, looking inside the dynamic boxes.
  Before: the `.row` blocks (header row included). After: the wrapper's children (page header, cards and disclosures all count).
  The two methods are not identical, so read the section column as a rough size, not a score.
- States: a demo user with a quiz result, goals, a saved resume (9 recognised skills) and four roadmaps (one flat, from an old shape).
  Every external call (LLM, YouTube, Adzuna) was stubbed.

## Per page

| Page (state) | Words before | Words after | Sections before | Sections after |
|---|---:|---:|---:|---:|
| Landing (logged out) | 381 | 104 | 2 | 3 |
| Landing (logged in, saved work) | 362 | 91 | 2 | 3 |
| Sign up | 68 | 39 | 1 | 1 |
| Log in | 51 | 31 | 1 | 1 |
| Quiz, a question | 127 | 83 | 2 | 3 |
| Quiz, results | 143 | 38 | 3 | 5 |
| Goals, a question | 111 | 68 | 2 | 3 |
| Goals, last (notes) step | 102 | 38 | 2 | 3 |
| Career profile (after goals) | 206 | 41 | 4 | 6 |
| Path picker | 130 | 46 | 2 | 2 |
| Roadmap, idle | 109 | 37 | 2 | 3 |
| Roadmap, generating | 72 | 50 | 2 | 2 |
| Roadmap, phased (22 steps, first phase open) | 1241 | 925 (693 visible) | 28 | 4 |
| Roadmap, flat old shape (32 steps) | 1047 | 1074 (906 visible) | 37 | 5 |
| Resume, fit form | 157 | 66 | 2 | 3 |
| Resume, discover form | 169 | 66 | 2 | 3 |
| Resume, fit results (saved) | 507 | 132 | 9 | 8 |
| Resume, discover results (9 skills) | 655 | 267 | 14 | 13 |
| Dashboard (phased newest roadmap) | 649 | 89 | 16 | 6 |

Notes on the numbers that go the wrong way or barely move:

- The flat 32-step roadmap is about the same size as before. An old flat roadmap has no phases to collapse, so all 32 steps are on
  screen; each is now a compact card (two-line description) instead of a row, which is why "visible" is lower than the raw count.
  The raw count also includes the roadmap dropdown's options (four demo roadmaps) and one screen-reader label per checkbox.
- The roadmap raw count (925) is mostly clamped descriptions and the dropdown; the words actually on screen are 693.
- Sections go up on small pages because the page header and the "How this works" disclosure now count as sections.
- Discover results stay long on purpose: ten path cards, each with its skills and a button.

## What was removed or collapsed, per page

**Layout**: Google Fonts requests (system font stack instead). Navbar label "Your goals" is now "Goals"; the footer is one line.
The red margin rule and the margin/main two-column "sheet" are gone from every page but the DSA map (kept for it).

**Landing**: the four-line hero ("Which tech career...?") and the long lead paragraph; three "phase" columns with status labels
and paragraphs are now three cards with one line each; the "Available now" labels; the sample specimen is a card with a ring and chips.
Collapsed into "How this works": that every tool works on its own, the login-first note, that coding, XP and streaks come later in the
skill map, and that the sample uses example numbers.

**Sign up / Log in**: the margin note about saved results; the paragraph under the password field (now five live rule chips, the
full rule sentence still shows as the error after leaving the field); "Already have an account?" and "New here?" are one short line.

**Quiz**: the three-sentence intro and the "Every question needs an answer" notes (now under "How this works", with the
question count). Letters A-D on the answers are now numbers 1-4 (the keys that select them); the "Choose one answer" hint is a
keyboard hint. Results: the "Every path, ranked" list is collapsed under "See all N paths"; the sentences under the top match are
a ring plus a "Tied: you pick one next" chip.

**Goals**: the two-sentence intro, the margin notes, the sentence-long placeholder and hint (shortened to one example), and the
"You chose: ..." recap line on the notes step. The answers recap on the profile is collapsed under "Your answers (N)".

**Path picker**: the margin notes and the explanation paragraph; the single line "This choice applies to this one request" now
sits in "How this works". The 15-path dropdown is collapsed under "Choose another path" when quiz matches exist.

**Roadmap**: the intro paragraph; the "Built for / Generated" margin notes; the overall progress bar (now a ring in the header);
the "Videos for this step" and "Projects" labels; the `Start here` text mark (now a chip). Collapsed: projects, docs and courses,
and "also covered" topics stay closed per step. The "Based on a reviewed ... roadmap" line moved into "How this works", which also
says when the reviewed base may be out of date and what a "search result" video is. The "Your roadmaps" list became a dropdown.
Error texts are one line each (the daily-limit and AI-busy messages are shorter).

**Resume**: the lead paragraph under the title and the margin notes; the "What happens next" list moved into "How this works".
Results: the "Everything below is compared with..." line, the per-section margin notes, the long salary notes, and the written
caveats about ATS, salary sources and AI feedback are one "How this works" list. The ATS reasons are under "Why this score".
The skills gauge (one segment per skill) is replaced by a bar plus chips. Feedback paragraphs became bullet lists.
Mode 1: the "Compared with all 15 paths" paragraph, the long limits note (now four short lines in "How this works"), and
the repeated "of the top match in this list" sentence on every card.

**Dashboard**: the margin note, the "standing" sentence, the status line, and the inline copies of the full resume analysis, the
full roadmap summary (or flat roadmap) and the skill-map gauge. The career ranking and answers are still there, collapsed under
"Career results". The full resume analysis is one click away on the Resume page (it shows your latest analysis).

## What a user might miss

- The dashboard no longer shows the full resume analysis or the DSA gauge; it shows ATS score, skills matched and date, and links on.
- The "Level" tile on the resume scorecard is the ATS band (Strong 80+, Fair 60+, Low), because the data has no experience-level field.
- Flat (old) roadmaps cannot be collapsed: they have no phases.

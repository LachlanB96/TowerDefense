# Character invariants — mage000

**What this file is.** Things that must stay true about *who he is*, as opposed to what
makes a good picture. A designer optimising for a striking image will trade these away
without noticing, because trading them away usually does make a better image.

**How they are used.** Each invariant is a **chip**, never a gate. The candidate is
built, rendered and judged normally; a violated invariant attaches a mark that blocks
*automatic* promotion and nothing else. Hard gates were tried and rejected — the user's
own words: *"the rules are quite weak and good design might get left behind because the
audit failed it on some legacy rule. I dont think we should have those binary rules and
just see what the model can produce."*

That is not a technicality. A hard gate would have killed d26 before it rendered, and
d26 is how we learned the narrower skirt was worth having.

**Rules for writing one.**
- Positively stated. "He carries his own weight", not "don't make him lean".
- **Measured, never asserted.** An `assert` crashes the build, which makes "violated an
  invariant" indistinguishable from "the build is broken".
- Scale-free and camera-free. If substituting a different size or viewing angle changes
  whether the invariant holds, it is not an invariant — it is a rendering preference.
- Carries a `broken-by` plate where one exists. A counter-example is worth more than
  another sentence of prose.
- Capped at ~25 lines total. Growth is how the last ledger reached 95 KB.

---

    INV-1  He carries his own weight.
      check      apex-over-base offset, MEASURED AS A CHANGE FROM THE INCUMBENT,
                 within 0.04 of figure height  (_tools/chips.py)
      broken-by  d26 (panel 204/300, reverted by the user 2026-08-02)
      why        "We dont want to give the character this weak stature, and the
                 physics of the lean is wrong."  Two independent designers reached
                 for a lean because it is an excellent silhouette move. It is a
                 character violation regardless.

    INV-2  The staff is a straight line and so is he.
      check      silhouette axis, AS A CHANGE FROM THE INCUMBENT, within 3 degrees
      broken-by  d17 (superseded by d26; same failure, earlier)

    INV-3  The gem is the brightest thing on him.
      check      no connected bright region outside the gem exceeds the gem's
                 peak luminance
      why        The user's own framing: "the most complexly beautiful item in all
                 the realms". Everything else on the model competes with it.
      note       This is the per-asset form of what used to be a hardcoded rule in
                 a shared tool. It belongs to this character, not to the harness.

    INV-4  Parts are connected; nothing floats — unless deliberate.
      check      one connected component in the silhouette from every judged cell,
                 excluding anything explicitly declared as an intended detached part
      why        User, 2026-07-31: "Ensure models parts are all connected and none
                 are levitating unrealistically, UNLESS OTHERWISE STATED."
      note       The escape clause is his and was previously dropped. Auras, glows
                 and deliberately floating elements are allowed and must be declared.

    INV-5  He reads as hat, robe and staff from every bearing.
      check      silhouette from each orbit cell has a distinguishable crown mass,
                 body mass and vertical line
      note       Deliberately stated as structure rather than as a size test. There
                 is no "reads at N pixels" rule here and there must not be one — his
                 rendered size is unknown and may change drastically.

---

## Known limit of the current checks — found by running them, 2026-08-10

**INV-1 and INV-2 are measured relative to the incumbent, not absolutely, and that is
a workaround rather than the right answer.**

Measured absolutely from a silhouette they fired on the *accepted champion*: 21° of
lean and 0.385 of figure height in the `orb3` cell. The model is not leaning. The
silhouette includes the **staff, held out to one side**, so from a high bearing the
topmost region of the outline is the gem rather than his head — and "apex offset from
the feet" then reports a held prop as a lean.

Taking the delta against the incumbent cancels the prop, because the prop is in both
images, and it matches how every other decision here is made. But it means these two
invariants can only catch a change, never an inherited violation: if a lean ever landed,
subsequent candidates would measure clean against it.

**The real fix is a 3D measurement out of the build** — the spine axis and the mass
distribution are properties of the geometry, not of a picture, and the asset script
could emit them as a small JSON beside the render. Recorded here rather than faked in
the checker.

## Open — the user has not ruled on these

- **Height.** `height_question_closed` in the old log was closed by a judge, not by
  the user. Reopened 2026-08-10; no invariant asserted until he says.
- **Bevel radius.** "Rounded armour, never visible cubes" is the user's, via
  `CLAUDE.md`. The specific threshold `>= 0.03` has no traceable origin and is
  recorded as `untuned` rather than enforced.

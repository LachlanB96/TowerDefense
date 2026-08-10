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
      check      torso apex within 40 mm of hip centre in the ground plane
      broken-by  d26 (panel 204/300, reverted by the user 2026-08-02)
      why        "We dont want to give the character this weak stature, and the
                 physics of the lean is wrong."  Two independent designers reached
                 for a lean because it is an excellent silhouette move. It is a
                 character violation regardless.

    INV-2  The staff is a straight line and so is he.
      check      spine axis within 3 degrees of the up axis
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

## Open — the user has not ruled on these

- **Height.** `height_question_closed` in the old log was closed by a judge, not by
  the user. Reopened 2026-08-10; no invariant asserted until he says.
- **Bevel radius.** "Rounded armour, never visible cubes" is the user's, via
  `CLAUDE.md`. The specific threshold `>= 0.03` has no traceable origin and is
  recorded as `untuned` rather than enforced.

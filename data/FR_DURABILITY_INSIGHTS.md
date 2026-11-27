# What 1,968 French durability indexes tell us

**Data:** all 205 manufacturer datasets titled "Indice de durabilité" on data.gouv.fr (downloaded 27 Nov 2026),
merged to **1,968 unique models**: 1,041 washing machines, 927 TVs. Scores are **self-declared by the manufacturer**
under the decree of 5 April 2024 and subject to DGCCRF checks. Script: see the analysis cell in the session; consolidated
table: `fr_durabilite_consolidated.csv`.

## Findings
1. **The formula is recoverable from the data: overall = 0.5 × repairability + 0.5 × reliability.**
   Least squares without intercept gives 0.501/0.499 (washing machines, R² = 0.998) and 0.526/0.474 (TVs, R² = 0.943).
   Only 3 of 1,968 filings deviate by more than 0.5 points from this formula, so the published overall scores are
   internally consistent.
2. **Repairable is not the same as reliable.** Spearman ρ between the two sub-scores is only 0.32 (washing machines)
   and 0.35 (TVs). A buyer who reads only a repairability score learns little about reliability. This is why
   *Hält das?* keeps both axes, plus field failure reports.
3. **Washing machines hit a ceiling; TVs discriminate.** Washing machines: median 8.4, IQR 8.1–8.8, repairability median
   9.0, and the repairability sub-criteria barely vary (ρ with the overall ≈ 0). The differences come from reliability.
   TVs spread from 2.3 to 9.1 (median 7.6), and two sub-criteria drive the ranking (ρ 0.74 for B_c2, 0.70 for A_c4).
4. **Brand spread on TVs is large:** median 8.4 (Metz, n = 10), 7.8 (LG, n = 226), 7.7 (Samsung, n = 288),
   6.3 (Panasonic, n = 57), 5.5 (Toshiba, n = 21), 4.7 (Strong, n = 18). For washing machines it is narrow:
   9.0 (Bosch, Siemens) to 7.4 (Continental Edison).
5. **Self-declared fields at the legal minimum carry no information.** Every listed spare part is "available" for
   exactly 15 years (washing machines) or 7 years (TVs), with no spread at all (p10 = p90). Spare-part delivery times
   are empty. A field that every filer sets to the same value cannot tell products apart.

## Caveats
- Self-declared, not measured. Consistency (finding 1) says nothing about whether the inputs are true.
- Sub-criterion codes (A_c1 … B_c3) follow the decree's grid; their labels were not verified in this session.
- Coverage is two product types only; durability indexes for other categories are not yet mandatory.

## How *Hält das?* uses it
For a TV or washing machine whose model code matches a filing, the official index appears as **tier-A evidence**
(overall, repairability, reliability, filer, link to the scoring sheet) and enters the live verdict.

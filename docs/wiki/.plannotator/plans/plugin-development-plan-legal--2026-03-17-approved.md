# Plugin Development Plan: Legal Language Translator & Legal Agents

## Context

Creating three new legal agents for mi-legal-resources plugin with Michigan-specific sources:
1. **LGL-language-translator** - Converts colloquial/clinical terms to legally safe language
2. **LGL-opposing-counsel** - Adversarial testing from opposing counsel perspective
3. **LGL-judge** - Judicial perspective review

Plus strategy files in OneDrive/CaseBible/strategies/ (if not exists, create).

---

## Research Sources

### Legal Red Teaming & Adversarial Analysis
- [DLA Piper: Legal Red Teaming](https://www.dlapiper.com/en-us/insights/publications/2024/05/legal-red-teaming-a-systematic-approach-to-assessing-legal-risk-of-generative-ai-models-) - Systematic approach to testing legal arguments
- [Legal Issues on Red Teaming](https://www.lexology.com/library/detail.aspx?g=047ad887-0d16-4a90-84db-e85f6ad9a050) - Methodology for adversarial legal testing
- [ABA Litigation Section](https://nysba.org/zealous-advocacy-a-doctrine-whose-time-has-passed/) - Zealous advocacy vs. professional conduct

### Judicial Reasoning & Characteristics
- [Blinking on the Bench (Cornell)](https://scholarship.law.cornell.edu/facpub/917/) - Intuitive-override model, cognitive biases in judges
- [Judicial Heuristics Assessment](https://www.frontiersin.org/journals/cognition/articles/10.3389/fcogn.2025.1421488/pdf) - Anchoring, availability, confirmation bias
- [ABA Model Code of Judicial Conduct](https://www.americanbar.org/content/dam/aba/administrative/professional_responsibility/2011_mcjc_table_of_contents.pdf) - Four Canons
- [ABA Standing Committee on Federal Judiciary](https://www.americanbar.org/groups/committees/federal_judiciary/) - Evaluation criteria

### Family Court Specialized Skills
- [The Modern Family Court Judge (IAALS)](https://iaals.du.edu/publications/modern-family-court-judge-knowledge-qualities-skills-success) - Knowledge, qualities, skills for success
- [NCJFCJ Custody Guide](https://www.ncjfcj.org/bench-cards/navigating-custody-visitation-evaluations-in-cases-with-domestic-violence-a-judges-guide/) - DV custody evaluation
- [APA Child Custody Guidelines](https://www.apa.org/practice/guidelines/child-custody) - Psychological evaluation standards

### Opposing Counsel Ethics
- [DC Bar Rule 3.4](https://www.dcbar.org/for-lawyers/legal-ethics/rules-of-professional-conduct/advocate/fairness-to-opposing-party-and-counsel) - Fairness to opposing counsel
- [NY Guidelines for Professional Conduct](https://www.jdsupra.com/post/fileServer.aspx?fName=fcef6c89-39b5-4045-903b-53bd8c04f06d.pdf) - Civility standards
- [Michigan L-GAL Guidelines](https://www.michbar.org/file/opinions/ethics/CANGuidebook.pdf) - Guardian ad litem standards

### Child Development Research
- [NICHD Divorce Effects Study](https://pubmed.ncbi.nlm.nih.gov/10870296/) - Government-funded longitudinal research
- [Longitudinal Interparental Conflict](https://ncbi.nlm.nih.gov/pmc/articles/PMC8273193/) - NIDA-funded mental health impacts
- [SAMHSA Children's Mental Health](https://samhsa.gov/mental-health/children-and-families) - Federal resources

---

## Source Hierarchy (Michigan → Federal)

**Michigan Primary Authority:**
- Michigan Supreme Court (courts.michigan.gov)
- Michigan Court of Appeals
- Michigan Compiled Laws (MCL)
- Michigan Court Rules (MCR)
- Michigan Bench Books (Michigan Judicial Institute)
- Genesee County 7th Circuit Court Rules

**Michigan State Agencies:**
- Michigan Department of Health and Human Services (DHHS)
- Michigan Friend of the Court (FOC)
- Michigan Child Protective Services (CPS)

**Federal Sources (any circuit):**
- United States Supreme Court
- Federal Circuit Courts (any district)
- CDC (Centers for Disease Control)
- NIH (National Institutes of Health)

**NOT ALLOWED:**
- Other state laws or cases
- UK/foreign jurisdiction sources
- Non-Michigan state references

---

## Terminology Glossary (Michigan-Focused)

### Personality/Trait Terms
| DON'T USE | USE INSTEAD |
|----------|-------------|
| "narcissist/narcissistic" | "demonstrates pattern of self-focused behavior with limited empathy" |
| "sociopath/psychopath" | "shows pattern of disregard for social norms and others' rights" |
| "borderline" | "exhibits emotional dysregulation and unstable interpersonal relationships" |
| "crazy" | "demonstrates erratic behavior on [dates]" |
| "mental case" | "has documented mental health history" |

### Abuse/Manipulation Terms
| DON'T USE | USE INSTEAD |
|----------|-------------|
| "gaslighting" | "pattern of denying documented events" / "systematic distortion of reality" |
| "manipulative" | "used influence tactics including [specific tactics]" |
| "controlling" | "restricted autonomy through [specific behaviors]" |
| "abusive" | "engaged in pattern of behavior including [specific behaviors]" |
| "toxic" | "engaged in harmful behaviors including [list]" |
| "emotionally abusive" | "engaged in pattern of verbal degradation" |

### Parenting/Family Terms
| DON'T USE | USE INSTEAD |
|----------|-------------|
| "parental alienation" | "engaged in alienating behaviors including [badmouthing, limiting contact, making unfounded allegations]" |
| "bad parent" | "failed to provide [specific need]" |
| "neglectful" | "failed to meet child's [specific] needs on [dates]" |
| "unfit parent" | "demonstrated inability to provide [specific] requirements" |
| "exposure to transient partners" | "child exposed to multiple intimate partners during [time period]" |

### Legal Phrasing Templates
1. "On [date], [person] [specific action] resulting in [impact]"
2. "Demonstrated pattern of [behavior] on [dates]"
3. "Failed to [specific obligation] on [dates]"
4. "Created situation where [specific outcome]"

---

## Agent Thinking Processes

### LGL-opposing-counsel Thinking Framework

Based on adversarial legal analysis research:

**1. Steel Man Method**
- Build the strongest possible case for opposing party
- Better than opposing counsel could make it themselves
- Then systematically dismantle each argument
- Source: [Volokh Conspiracy - Steelmanning](https://reason.com/volokh/2021/05/12/steelmanning-and-interpretive-charity/)

**2. Procedural Attack Patterns**
- Find technical defects (MCR 1.109, MCR 2.113)
- Challenge service methods
- Question jurisdiction
- Check filing deadlines
- Verify caption format

**3. Evidence Attacks**
- Authentication challenges (MRE 901)
- Hearsay objections
- Relevance objections (MRE 401/402)
- Prejudice vs. probative value (MRE 403)
- Chain of custody gaps

**4. Credibility Undermining**
- Inconsistencies in timeline
- Contradictions in statements
- Missing documentation
- Witness credibility attacks

**5. Zealous Advocacy Within Bounds**
- Diligent representation (not "zealous")
- Civility to opposing counsel
- Professional conduct required
- Source: [NY Guidelines](https://nysba.org/zealous-advocacy-a-doctrine-whose-time-has-passed/)

### LGL-judge Thinking Framework

Based on judicial reasoning research and ABA Model Code:

**1. System 2 Override Protocol**
- Recognize System 1 (intuitive) vs. System 2 (deliberative)
- Override snap judgments with deliberation
- Source: [Blinking on the Bench](https://scholarship.law.cornell.edu/facpub/917/)

**2. Cognitive Bias Awareness**
- **Anchoring**: Don't let first number influence decisions
- **Confirmation bias**: Seek evidence against initial belief
- **Availability**: Don't overweight recent/vivid cases
- **Hindsight bias**: Evaluate foreseeability as it was at the time
- Source: [Judicial Heuristics Assessment](https://www.frontiersin.org/journals/cognition/articles/10.3389/fcogn.2025.1421488/pdf)

**3. Family Court Special Considerations**
- Child development knowledge
- Domestic violence dynamics (coercive control)
- Trauma-informed decision making
- Long-term family relationships
- Source: [Modern Family Court Judge](https://iaals.du.edu/publications/modern-family-court-judge-knowledge-qualities-skills-success)

**4. Judicial Temperament (ABA)**
- Patience under pressure
- Open-mindedness to all sides
- Courtesy and tact
- Courage to make difficult decisions
- Impartiality and integrity
- Source: [ABA Model Code of Judicial Conduct](https://www.americanbar.org/content/dam/aba/administrative/professional_responsibility/2011_mcjc_table_of_contents.pdf)

**5. Procedural Compliance Check**
- MCR 1.109 (formatting)
- MCR 2.113 (caption)
- Service requirements
- Jurisdiction verification
- Evidence rules (MRE)

---

## Human-in-the-Loop Requirements

### Agents WITH Human-in-the-Loop (Interactive)
These agents need Ask User Question tool and should use it proactively:
- **LGL-language-translator** - Document type, audience, terms to focus on
- **LGL-legal-custody-support** - Case context, specific factors, fact patterns
- **LGL-legal-evidence-tech** - Evidence type, processing questions
- **LGL-legal-forensic** - Analysis questions, approach
- **LGL-legal-michigan-law** - Legal questions, research scope

### Agents WITHOUT Human-in-the-Loop (Document-Based)
These agents work from whatever document is given - no questions needed:
- **LGL-opposing-counsel** - Takes motion/document, red-lines it, argues against it. No questions, just attack.
- **LGL-judge** - May ask basic clarification questions, but primarily reviews document and applies judicial lens.

### LGL-language-translator Questions
- "What document type is this for? (motion, brief, letter)"
- "Should I preserve any technical terms?"
- "What's the target audience? (judge, opposing counsel, client)"
- "Any specific terms you want me to focus on?"

### LGL-judge Questions (Minimal)
- "What court is this for? (circuit, appeals)" - if not clear from document
- "What procedural stage?" - if not clear from document

---

## Files to Create

### New Agents
- `mi-legal-resources/agents/LGL-language-translator.md`
- `mi-legal-resources/agents/LGL-opposing-counsel.md`
- `mi-legal-resources/agents/LGL-judge.md`

### New Skills
- `mi-legal-resources/skills/LGL-legal-terminology/SKILL.md`
- `mi-legal-resources/skills/LGL-adversarial-advocacy/SKILL.md` (opposing counsel)
- `mi-legal-resources/skills/LGL-judicial-review/SKILL.md` (judge)

### Strategy Files
- `strategies/terminology-mappings.md`
- `strategies/evidence-exclusion.md`
- `strategies/citation-standards.md`
- `strategies/factor-mappings.md`

---

## Implementation Order

1. Create agent files with system prompts
2. Create terminology skill
3. Create adversarial advocacy skill (opposing counsel)
4. Create judicial review skill (judge)
5. Create strategy files
6. Update hooks.json if needed
7. Test agents trigger correctly
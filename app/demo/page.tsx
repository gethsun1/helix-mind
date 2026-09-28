import Link from 'next/link';

import { Brand } from '../components/Brand';

export default function DemoPage() {
  return <main className="demo-page"><header className="landing-nav"><Brand /><Link href="/login" className="button button-small">Open research workspace</Link></header><div className="demo-wrap"><p className="eyebrow">RESEARCH &amp; INNOVATION / CANONICAL WORKFLOW</p><h1>An auditable research project from question to reproducible artifact.</h1><p className="demo-lede">Use this bounded question in the authenticated workspace to demonstrate HelixMind’s institutional AI infrastructure. The project uses your existing profile research context; it does not create an institutional account or shared workspace.</p><div className="demo-question"><span>CANONICAL RESEARCH QUESTION</span><h2>What clinical evidence supports CRISPR-Cas9 therapies for sickle cell disease, and what safety outcomes have been reported?</h2><p>Suggested project title: <b>Evidence review — CRISPR-Cas9 and sickle cell disease</b></p></div><div className="demo-steps">{[
    ['Research project and context', 'An Investigation is the research project. The owner’s organization profile appears as context when one is set.'],
    ['Bounded planning agent', 'OmegaClaw returns an inspectable research plan with provider, model, latency and fallback attribution. A deterministic fallback is labeled separately.'],
    ['Literature and evidence', 'PubMed and Europe PMC provide the retrieved papers. Evidence stays linked to its source paper and location.'],
    ['Knowledge and reasoning', 'HelixMind builds propositions and hypotheses, then aggregates evidence deterministically with uncertainty and contradictions visible.'],
    ['Human research decision', 'A researcher explicitly saves a structured decision as persistent research memory and can deactivate it later.'],
    ['Memory-influenced rerun', 'The next run records which active memories it loaded and how their bounded policy changed retrieval or ranking.'],
    ['Reproducibility and artifact', 'Run lineage, snapshot manifest digest and generated artifact digest remain available for inspection and verification.'],
  ].map(([step, detail], index) => <div key={step}><span>{String(index + 1).padStart(2, '0')}</span><h3>{step}</h3><p>{detail}</p></div>)}</div><p className="disclaimer demo-disclaimer">This public page is a workflow guide, not a live investigation. It contains no fabricated papers, citations, experimental results, or scientific conclusions. Live project evidence is retrieved from the named literature sources after you create the project.</p><Link href="/login" className="button">Open the authenticated research workspace ↗</Link></div></main>;
}

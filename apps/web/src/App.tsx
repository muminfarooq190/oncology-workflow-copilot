type ReadinessItem = {
  label: string
  detail: string
  state: 'ready' | 'planned'
}

const readiness: ReadinessItem[] = [
  { label: 'Product boundary', detail: 'Adult synthetic NSCLC only', state: 'ready' },
  { label: 'FHIR intake', detail: 'Synthetic Bundle envelope', state: 'ready' },
  { label: 'Clinical extraction', detail: 'Week 6 implementation', state: 'planned' },
  { label: 'Evidence retrieval', detail: 'Frozen nsclc-v1 corpus', state: 'planned' },
  { label: 'Clinician review', detail: 'Correction and approval workflow', state: 'planned' },
]

function StatusBadge({ state }: Pick<ReadinessItem, 'state'>) {
  return <span className={`badge badge--${state}`}>{state === 'ready' ? 'Foundation ready' : 'Planned'}</span>
}

function App() {
  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#overview" aria-label="Oncology Workflow Copilot home">
          <span className="brand__mark" aria-hidden="true">OW</span>
          <span>Oncology Workflow Copilot</span>
        </a>
        <span className="environment">Synthetic data environment</span>
      </header>

      <section className="hero" id="overview">
        <div className="hero__copy">
          <p className="eyebrow">Evaluation-first clinical workflow</p>
          <h1>Tumor-board preparation with evidence, provenance, and clinician control.</h1>
          <p className="lede">
            Convert synthetic FHIR records into a structured NSCLC case packet, surface what is
            missing, and require a clinician to review every material claim.
          </p>
          <div className="notice" role="note">
            <strong>Portfolio safety boundary</strong>
            <span>No real patient data. No diagnosis or autonomous treatment decisions.</span>
          </div>
        </div>

        <aside className="case-card" aria-label="Example case readiness">
          <div className="case-card__header">
            <div>
              <p className="overline">Development case</p>
              <h2>NSCLC-001</h2>
            </div>
            <span className="case-card__state">Foundation</span>
          </div>
          <dl>
            <div><dt>Histology</dt><dd>Lung adenocarcinoma</dd></div>
            <div><dt>Stage</dt><dd>cT2a cN2 cM1c · IVB</dd></div>
            <div><dt>Key biomarker</dt><dd>EGFR exon 21 L858R</dd></div>
            <div><dt>Performance</dt><dd>ECOG 1</dd></div>
          </dl>
          <p className="case-card__footnote">Synthetic fixture awaiting clinician adjudication.</p>
        </aside>
      </section>

      <section className="readiness" aria-labelledby="readiness-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Week 5</p>
            <h2 id="readiness-title">Foundation readiness</h2>
          </div>
          <p>Visible status is deliberately honest: planned functionality is not presented as complete.</p>
        </div>

        <div className="readiness-grid">
          {readiness.map((item) => (
            <article className="readiness-item" key={item.label}>
              <StatusBadge state={item.state} />
              <h3>{item.label}</h3>
              <p>{item.detail}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  )
}

export default App


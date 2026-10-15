import { Reveal } from './Reveal';

const STAGES = ['Clone', 'Analyze', 'Plan', 'Build', 'Health check', 'Live URL'];

export function Hero() {
  return (
    <section className="bg-ink pt-[72px] relative overflow-hidden" aria-labelledby="hero-heading">
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(ellipse at 30% 20%, rgba(255,103,36,.18), transparent 55%), linear-gradient(180deg, rgba(255,255,255,.04), transparent)',
        }}
      />
      <div className="relative max-w-6xl mx-auto px-6 py-16 md:py-24 grid gap-12 md:grid-cols-[1.2fr_1fr] items-center">
        <div>
          <Reveal>
            <p className="inline-flex items-center gap-2 bg-ember/15 border border-ember/40 px-4 py-2 mb-8">
              <span className="pulse-dot inline-block w-2 h-2 rounded-full bg-ember" aria-hidden="true" />
              <span className="font-display text-xs font-bold tracking-[2px] uppercase text-ember">
                GitHub URL → Live app
              </span>
            </p>
          </Reveal>
          <Reveal delay={80}>
            <h1
              id="hero-heading"
              className="font-display font-extrabold uppercase text-white leading-[0.95] tracking-tight text-5xl md:text-7xl mb-6"
            >
              Turn any repo into a <span className="text-ember">running app.</span>
            </h1>
          </Reveal>
          <Reveal delay={160}>
            <p className="text-lg leading-relaxed text-white/70 max-w-xl mb-10">
              Paste a GitHub URL and Repo2Web analyzes the codebase, builds an execution
              plan, and deploys it inside a sandboxed container — no README archaeology,
              no port guessing.
            </p>
          </Reveal>
          <Reveal delay={240}>
            <div className="flex flex-wrap gap-4">
              <a
                href="#deploy"
                className="btn-lift font-display text-[15px] font-bold tracking-[1.5px] uppercase bg-ember text-white px-8 py-4 hover:bg-emberdark"
              >
                ▼ Deploy a repo
              </a>
              <a
                href="#how"
                className="btn-lift font-display text-[15px] font-bold tracking-[1.5px] uppercase bg-transparent text-white border-2 border-white px-8 py-4 hover:bg-white hover:text-ink"
              >
                How it works
              </a>
            </div>
          </Reveal>
        </div>
        <Reveal delay={160} className="w-full">
          <div className="border border-white/15 bg-white/[0.04] p-6" role="img" aria-label="Deployment pipeline: clone, analyze, plan, build, health check, live URL">
            <p className="font-display text-xs font-bold tracking-[2px] uppercase text-ember mb-4">
              The pipeline
            </p>
            <ol className="flex flex-col gap-0">
              {STAGES.map((stage, i) => (
                <li key={stage} className="flex items-center gap-4 py-3 border-b border-white/10 last:border-0 group">
                  <span className="font-display font-extrabold text-2xl text-white/15 group-hover:text-ember transition-colors" aria-hidden="true">
                    {i + 1}
                  </span>
                  <span className="font-display text-lg font-bold uppercase tracking-wide text-white/80">
                    {stage}
                  </span>
                  {i === STAGES.length - 1 && (
                    <span className="ml-auto text-xs font-semibold text-white/50">~ minutes</span>
                  )}
                </li>
              ))}
            </ol>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

import { Reveal } from './Reveal';

export function SiteFooter() {
  return (
    <>
      <section className="bg-[#353031] py-20 text-center" aria-labelledby="cta-heading">
        <div className="max-w-6xl mx-auto px-6">
          <Reveal>
            <p className="font-display text-lg font-bold uppercase text-ember mb-2">
              Ready when your repo is
            </p>
            <h2
              id="cta-heading"
              className="font-display font-extrabold uppercase text-white leading-[0.92] tracking-tight text-5xl md:text-7xl mb-6"
            >
              Ship it live <span className="text-ember">today.</span>
            </h2>
            <p className="text-white/60 max-w-xl mx-auto mb-10 leading-relaxed">
              Paste the URL above and watch analysis, build, and health check do
              the work — with logs at every stage.
            </p>
            <a
              href="#deploy"
              className="btn-lift inline-block font-display text-[15px] font-bold tracking-[1.5px] uppercase bg-ember text-white px-8 py-4 hover:bg-emberdark"
            >
              → Deploy a repo
            </a>
          </Reveal>
        </div>
      </section>
      <footer className="bg-ink border-t-[3px] border-ember text-white/55">
        <div className="max-w-6xl mx-auto px-6 py-14 grid gap-10 md:grid-cols-[1.3fr_1fr_1fr]">
          <div>
            <p className="font-display font-bold text-xl tracking-wide text-white uppercase mb-3">
              Repo<span className="text-ember">2</span>Web
            </p>
            <p className="text-sm leading-relaxed max-w-sm">
              GitHub repositories into running apps — static analysis to
              ExecutionPlan, controlled Docker build and runtime, async
              deployment dashboard.
            </p>
          </div>
          <nav aria-label="Footer">
            <p className="font-display text-xs font-bold tracking-[2px] uppercase text-ember mb-4">
              Product
            </p>
            <ul className="flex flex-col gap-2 text-sm">
              <li><a href="#deploy" className="hover:text-white transition-colors">Deploy</a></li>
              <li><a href="#how" className="hover:text-white transition-colors">How it works</a></li>
              <li><a href="#guarantees" className="hover:text-white transition-colors">Guarantees</a></li>
              <li><a href="#faq" className="hover:text-white transition-colors">FAQ</a></li>
            </ul>
          </nav>
          <div>
            <p className="font-display text-xs font-bold tracking-[2px] uppercase text-ember mb-4">
              API
            </p>
            <ul className="flex flex-col gap-2 text-sm font-mono">
              <li>POST /api/v1/deployments</li>
              <li>GET /api/v1/deployments/{'{id}'}</li>
              <li>GET /api/v1/deployments/{'{id}'}/logs</li>
            </ul>
          </div>
        </div>
        <div className="border-t border-white/10">
          <div className="max-w-6xl mx-auto px-6 py-6 flex flex-wrap gap-3 justify-between text-xs">
            <span>© 2026 Repo2Web · MIT</span>
            <span>Every repository is untrusted code — sandboxed, SHA-pinned, observable.</span>
          </div>
        </div>
      </footer>
    </>
  );
}

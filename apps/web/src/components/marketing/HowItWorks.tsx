import { Reveal } from './Reveal';

const PAINS = [
  'Cloning a repo that has no working setup instructions',
  'Guessing the entrypoint, port, and environment variables',
  'Dependency installs that break on a different machine',
  '“Works on my machine” demos before a review',
];

const STEPS = [
  {
    n: '1',
    label: 'Step one',
    title: 'Paste',
    text: 'Drop in any public GitHub URL. The form validates it and pins the immutable commit SHA — never a moving branch ref.',
  },
  {
    n: '2',
    label: 'Step two',
    title: 'Analyze',
    text: 'Thirteen analyzer modules inventory files, detect the framework, entrypoint, port, env, and dependencies — then build a validated ExecutionPlan.',
  },
  {
    n: '3',
    label: 'Step three',
    title: 'Go live',
    text: 'The plan builds inside a controlled Docker environment, passes a health check, and you get a live URL with streaming logs.',
  },
];

export function HowItWorks() {
  return (
    <>
      <section className="bg-[#353031] py-16 md:py-24" aria-labelledby="pain-heading">
        <div className="max-w-6xl mx-auto px-6 grid gap-12 md:grid-cols-2 items-center">
          <Reveal>
            <p className="font-display text-lg font-bold uppercase text-ember mb-2">
              Repos that never run
            </p>
            <h2 id="pain-heading" className="font-display font-extrabold uppercase text-white leading-[0.95] text-4xl md:text-6xl mb-6">
              Dead code doesn&apos;t demo itself
            </h2>
            <p className="text-white/65 leading-relaxed">
              You&apos;ve met a repository with no runnable story before — and you
              probably gave up on it. Every repo is untrusted code until it proves
              otherwise, inside a sandbox.
            </p>
          </Reveal>
          <Reveal delay={120}>
            <ul>
              {PAINS.map((pain) => (
                <li
                  key={pain}
                  className="py-4 border-b border-white/10 first:border-t text-white/75 flex gap-3"
                >
                  <span className="text-ember" aria-hidden="true">✕</span>
                  {pain}
                </li>
              ))}
            </ul>
            <p className="mt-8 font-display text-xl font-bold text-white/40">
              This is where Repo2Web comes in ↓
            </p>
          </Reveal>
        </div>
      </section>

      <section id="how" className="bg-ink py-16 md:py-24 scroll-mt-[72px]" aria-labelledby="how-heading">
        <div className="max-w-6xl mx-auto px-6">
          <Reveal>
            <p className="font-display text-lg font-bold uppercase text-ember mb-2">Our process</p>
            <h2 id="how-heading" className="font-display font-extrabold uppercase text-white leading-[0.95] text-4xl md:text-6xl mb-4">
              Three steps to live
            </h2>
            <p className="text-white/55 max-w-xl mb-12">
              The same pipeline runs for every repository — analysis first, execution
              only inside controlled containers.
            </p>
          </Reveal>
          <div className="grid gap-px md:grid-cols-3 bg-white/10 border border-white/10">
            {STEPS.map((step, i) => (
              <Reveal key={step.n} delay={i * 80} className="h-full">
                <article className="relative h-full bg-ink p-8 hover:bg-white/[0.06] transition-colors">
                  <span
                    className="absolute top-5 right-5 font-display font-extrabold text-7xl leading-none text-white/[0.07] hover:text-ember transition-colors"
                    aria-hidden="true"
                  >
                    {step.n}
                  </span>
                  <p className="font-display text-[11px] font-bold tracking-[3px] uppercase text-ember mb-3">
                    {step.label}
                  </p>
                  <h3 className="font-display text-4xl font-extrabold uppercase text-white mb-4">
                    {step.title}
                  </h3>
                  <p className="text-[15px] leading-relaxed text-white/55">{step.text}</p>
                </article>
              </Reveal>
            ))}
          </div>
          <Reveal delay={120}>
            <pre className="mt-8 overflow-x-auto text-sm leading-relaxed bg-black/40 border border-white/10 text-white/70 p-6">
              <code>{`GitHub URL → Clone → Analyze → ExecutionPlan → Docker Build → Health Check → Live URL`}</code>
            </pre>
          </Reveal>
        </div>
      </section>
    </>
  );
}

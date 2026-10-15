'use client';

import { useEffect, useRef, useState } from 'react';
import { Reveal } from './Reveal';

function useCountUp(target: number, active: boolean, duration = 1200) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!active) return;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      setValue(Math.round(target * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [active, target, duration]);
  return value;
}

function Stat({ target, decimals = 0, suffix, label }: { target: number; decimals?: number; suffix: string; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(false);
  const raw = useCountUp(target, active);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setActive(true);
          io.disconnect();
        }
      },
      { threshold: 0.4 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const display = decimals > 0 ? (raw / 10).toFixed(decimals) : String(raw);
  return (
    <div ref={ref} className="px-6 py-8 text-center border-r border-gray-200 last:border-r-0">
      <strong className="block font-display text-4xl font-extrabold text-ember">
        {display}
        {suffix}
      </strong>
      <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">{label}</span>
    </div>
  );
}

const GUARANTEES = [
  { title: 'Sandboxed builds', text: 'No Docker socket exposure, dropped capabilities, non-root execution, enforced CPU / memory / PID limits.' },
  { title: 'SHA-pinned deploys', text: 'Every deployment locks an immutable commit SHA. Rebuilds are reproducible, never moving refs.' },
  { title: 'SSRF & secret guards', text: 'Repository fetching and secrets pass validation, audit logging, and network policy before anything runs.' },
  { title: 'Observable by default', text: 'Deployment detail pages poll status, stream logs, and show results — no black-box waiting.' },
];

export function TrustSignals() {
  return (
    <section id="guarantees" className="bg-white py-16 md:py-24 scroll-mt-[72px]" aria-labelledby="guarantees-heading">
      <div className="max-w-6xl mx-auto px-6">
        <Reveal>
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-10">
            <div>
              <p className="font-display text-lg font-bold uppercase text-ember mb-2">
                Measured, not promised
              </p>
              <h2 id="guarantees-heading" className="font-display font-extrabold uppercase text-gray-900 leading-[0.95] text-4xl md:text-6xl">
                Built like infrastructure
              </h2>
            </div>
          </div>
        </Reveal>
        <Reveal>
          <div className="grid grid-cols-1 sm:grid-cols-3 border border-gray-200 bg-gray-50 mb-12">
            <Stat target={941} decimals={1} suffix="%" label="Analysis success · 17 real repos" />
            <Stat target={13} suffix="" label="Analyzer modules" />
            <Stat target={544} suffix="" label="Backend tests passing" />
          </div>
        </Reveal>
        <div className="grid gap-6 sm:grid-cols-2">
          {GUARANTEES.map((g, i) => (
            <Reveal key={g.title} delay={i * 80}>
              <article className="group relative h-full bg-gray-50 border border-gray-200 border-t-4 border-t-gray-200 hover:border-t-ember transition-colors p-8">
                <h3 className="font-display text-xl font-extrabold uppercase text-gray-900 mb-3">
                  {g.title}
                </h3>
                <p className="text-[15px] leading-relaxed text-gray-600">{g.text}</p>
                <span
                  className="absolute bottom-0 left-0 right-0 h-[3px] bg-ember scale-x-0 origin-left group-hover:scale-x-100 transition-transform duration-300"
                  aria-hidden="true"
                />
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

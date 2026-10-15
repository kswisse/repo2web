'use client';

import { useRef, useState } from 'react';
import { Reveal } from './Reveal';

const ITEMS = [
  {
    q: 'Which stacks are supported?',
    a: 'React, Vue, Angular, Next.js, plain Node.js, and Python (Flask, Django, FastAPI). The framework detector picks the entrypoint, port, and install commands automatically.',
  },
  {
    q: 'How are deployments versioned?',
    a: 'Every deployment pins an immutable commit SHA — never a mutable branch ref. The same SHA always rebuilds the same way, and snapshots are kept for audit.',
  },
  {
    q: 'Is it safe to deploy an arbitrary repo?',
    a: 'Yes, by design. All repository code is treated as untrusted: it only runs inside sandboxed containers with dropped capabilities, non-root execution, resource limits, and no host networking.',
  },
  {
    q: 'How do I follow a deployment?',
    a: 'After submitting, you land on a deployment detail page that polls status every 2 seconds and streams build and runtime logs until the health check passes.',
  },
  {
    q: 'Why did my build fail?',
    a: 'The usual causes: Docker Desktop is not running, the build needs a command outside the executor allowlist (for example pnpm or yarn build), or the base image has not been pulled yet. The logs on the deployment page show exactly which stage failed.',
  },
  {
    q: 'Are there resource limits?',
    a: 'Yes. Deployed containers are capped at 1 CPU core, 512 MB of memory, and 100 PIDs, with filesystem and network isolation from the host.',
  },
];

function FaqItem({ q, a, defaultOpen = false }: { q: string; a: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyRef = useRef<HTMLDivElement>(null);
  return (
    <div className="border-b border-gray-200">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-4 py-6 text-left"
      >
        <span className="font-display text-lg font-bold text-gray-900">{q}</span>
        <span
          aria-hidden="true"
          className={`flex items-center justify-center w-8 h-8 shrink-0 text-sm transition-all duration-300 ${
            open ? 'bg-ember text-white rotate-45' : 'bg-gray-100 text-gray-900'
          }`}
        >
          +
        </span>
      </button>
      <div
        ref={bodyRef}
        className="overflow-hidden transition-[max-height] duration-300 ease-in-out"
        style={{
          maxHeight: open ? bodyRef.current?.scrollHeight ?? 500 : 0,
          visibility: open ? 'visible' : 'hidden',
        }}
        aria-hidden={!open}
      >
        <p className="pb-6 text-[15px] leading-relaxed text-gray-600">{a}</p>
      </div>
    </div>
  );
}

export function Faq() {
  return (
    <section id="faq" className="bg-gray-50 py-16 md:py-24 scroll-mt-[72px]" aria-labelledby="faq-heading">
      <div className="max-w-6xl mx-auto px-6 grid gap-12 md:grid-cols-[1fr_2fr]">
        <Reveal>
          <p className="font-display text-lg font-bold uppercase text-ember mb-2">But what about…</p>
          <h2 id="faq-heading" className="font-display font-extrabold uppercase text-gray-900 leading-[0.95] text-4xl md:text-5xl mb-4">
            FAQ
          </h2>
          <p className="text-gray-500 leading-relaxed">
            Honest answers, including the current limitations. Still stuck? The
            deployment logs show exactly which stage failed.
          </p>
        </Reveal>
        <Reveal delay={120}>
          <div className="border-t border-gray-200">
            {ITEMS.map((item, i) => (
              <FaqItem key={item.q} q={item.q} a={item.a} defaultOpen={i === 0} />
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

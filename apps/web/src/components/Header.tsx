'use client';

import { useState } from 'react';

const LINKS = [
  { href: '#deploy', label: 'Deploy' },
  { href: '#how', label: 'How it works' },
  { href: '#guarantees', label: 'Guarantees' },
  { href: '#faq', label: 'FAQ' },
];

export function Header() {
  const [open, setOpen] = useState(false);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-ink border-b-[3px] border-ember">
      <div className="max-w-6xl mx-auto px-6 h-[72px] flex items-center justify-between">
        <a href="#top" className="flex items-center gap-2" aria-label="Repo2Web home">
          <span className="w-8 h-8 bg-ember flex items-center justify-center" aria-hidden="true">
            <span className="text-white font-bold text-sm">R2</span>
          </span>
          <span className="font-display font-bold text-xl tracking-wide text-white uppercase">
            Repo<span className="text-ember">2</span>Web
          </span>
        </a>
        <nav className="hidden md:flex items-center gap-8" aria-label="Primary">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="font-display text-sm font-semibold tracking-[1.5px] uppercase text-white/75 hover:text-ember transition-colors"
            >
              {l.label}
            </a>
          ))}
          <a
            href="#deploy"
            className="btn-lift font-display text-[13px] font-bold tracking-[1.5px] uppercase bg-ember text-white px-6 py-2.5 hover:bg-emberdark"
          >
            Deploy now
          </a>
        </nav>
        <button
          type="button"
          className="md:hidden text-white text-2xl px-2 py-1 border border-white/30"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? 'Close menu' : 'Open menu'}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? '✕' : '☰'}
        </button>
      </div>
      <div
        id="mobile-menu"
        className="md:hidden overflow-hidden bg-ink border-t border-white/10 transition-[max-height] duration-300 ease-in-out"
        style={{ maxHeight: open ? 400 : 0 }}
      >
        {LINKS.map((l) => (
          <a
            key={l.href}
            href={l.href}
            onClick={() => setOpen(false)}
            className="block font-display text-sm font-semibold tracking-[1.5px] uppercase text-white/80 px-6 py-4 border-b border-white/10"
          >
            {l.label}
          </a>
        ))}
        <a
          href="#deploy"
          onClick={() => setOpen(false)}
          className="block font-display text-sm font-bold tracking-[1.5px] uppercase text-ember px-6 py-4"
        >
          Deploy now →
        </a>
      </div>
    </header>
  );
}

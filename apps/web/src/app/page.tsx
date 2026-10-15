import { Header } from '@/components/Header';
import { Hero } from '@/components/marketing/Hero';
import { HowItWorks } from '@/components/marketing/HowItWorks';
import { TrustSignals } from '@/components/marketing/TrustSignals';
import { Faq } from '@/components/marketing/Faq';
import { SiteFooter } from '@/components/marketing/SiteFooter';
import { Reveal } from '@/components/marketing/Reveal';
import { DeployPanel } from '@/components/DeployPanel';

export default function HomePage() {
  return (
    <div id="top" className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        <Hero />
        <section id="deploy" className="bg-ink border-t border-white/10 scroll-mt-[72px]" aria-labelledby="deploy-heading">
          <div className="max-w-6xl mx-auto px-6 pb-16 md:pb-20">
            <Reveal>
              <div className="max-w-4xl mx-auto">
                <h2 id="deploy-heading" className="sr-only">
                  Deploy a repository
                </h2>
                <DeployPanel />
                <p className="mt-6 text-center text-sm text-white/40">
                  Supported: React, Vue, Angular, Next.js, Node.js, Python (Flask, Django, FastAPI)
                </p>
              </div>
            </Reveal>
          </div>
        </section>
        <HowItWorks />
        <TrustSignals />
        <Faq />
      </main>
      <SiteFooter />
    </div>
  );
}

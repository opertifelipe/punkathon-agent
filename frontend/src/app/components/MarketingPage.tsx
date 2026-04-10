import { Button } from './ui/button';

interface MarketingPageProps {
  onOpenSignin: () => void;
  onOpenSignup: () => void;
}

export function MarketingPage({ onOpenSignin, onOpenSignup }: MarketingPageProps) {
  return (
    <div className="flex min-h-screen flex-col bg-white text-slate-950">
      {/* Header */}
      <header className="fixed left-0 right-0 top-0 z-20 flex items-center justify-between border-b border-slate-100 bg-white/90 px-6 py-4 backdrop-blur">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="PunkAgent" className="h-8 w-8 object-contain" />
          <span
            className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-950"
            style={{ fontFamily: '"Space Grotesk", "Avenir Next", sans-serif' }}
          >
            PunkAgent
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            className="rounded-full px-4 text-slate-700 hover:bg-slate-100"
            onClick={onOpenSignin}
          >
            Sign in
          </Button>
          <Button
            className="rounded-full bg-slate-950 px-5 text-white hover:bg-slate-800"
            onClick={onOpenSignup}
          >
            Sign up
          </Button>
        </div>
      </header>

      {/* Hero */}
      <main className="flex flex-1 flex-col items-center justify-center px-6 pb-24 pt-24 text-center">
        <img
          src="/logo.png"
          alt="PunkAgent logo"
          className="mb-8 h-40 w-40 object-contain"
        />

        <h1
          className="text-5xl font-semibold tracking-[-0.06em] text-slate-950 sm:text-6xl lg:text-7xl"
          style={{ fontFamily: '"Space Grotesk", "Avenir Next", sans-serif' }}
        >
          PunkAgent
        </h1>

        <p className="mt-6 max-w-xl text-lg leading-8 text-slate-500 sm:text-xl">
          Leggi i tuoi movimenti bancari, capisci dove vanno i soldi e ricevi
          consigli pratici — senza fogli Excel, senza linguaggio da consulente.
        </p>

        <div className="mt-16 flex items-center gap-6 text-sm text-slate-400">
          <span>Creato da</span>
          <a
            href="https://linkedin.com/in/stefanni-matos-080411163"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-600 underline-offset-4 hover:underline"
          >
            Stefanni Matos da Oliveira
          </a>
          <span>&amp;</span>
          <a
            href="https://linkedin.com/in/felipeoperti"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-600 underline-offset-4 hover:underline"
          >
            Felipe Operti
          </a>
        </div>
      </main>
    </div>
  );
}

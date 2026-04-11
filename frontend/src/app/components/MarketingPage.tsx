import { ArrowRight, BrainCircuit, PiggyBank, Target, Wallet } from 'lucide-react';

import { Button } from './ui/button';

interface MarketingPageProps {
  onOpenSignin: () => void;
  onOpenSignup: () => void;
}

export function MarketingPage({ onOpenSignin, onOpenSignup }: MarketingPageProps) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#fff5ec_0%,#fffaf6_24%,#f6f8ff_62%,#eef6ff_100%)] text-slate-950">
      <header className="fixed left-0 right-0 top-0 z-20 flex items-center justify-between border-b border-white/70 bg-white/75 px-6 py-4 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="Aurora" className="h-10 object-contain sm:h-12" />
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            className="rounded-full px-4 text-slate-700 hover:bg-slate-100"
            onClick={onOpenSignin}
          >
            Accedi
          </Button>
          <Button
            className="rounded-full bg-slate-950 px-5 text-white hover:bg-slate-800"
            onClick={onOpenSignup}
          >
            Crea account
          </Button>
        </div>
      </header>

      <main className="flex min-h-screen w-full flex-col px-6 pb-20 pt-28 lg:px-10">
        <section className="mx-auto flex w-full max-w-[88rem] flex-1 flex-col items-center gap-12 py-10 lg:py-16">
          <div className="flex w-full max-w-5xl flex-col items-center text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-orange-200 bg-white/80 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-orange-600 shadow-sm backdrop-blur">
              <BrainCircuit className="h-4 w-4" />
              AI + comportamento
            </div>

            <div className="mt-8 flex justify-center">
              <div className="flex h-24 w-56 items-center justify-center overflow-hidden sm:h-28 sm:w-72 lg:h-52 lg:w-[44rem] xl:h-60 xl:w-[52rem] 2xl:h-64 2xl:w-[58rem]">
                <img src="/logo.png" alt="Aurora logo" className="h-full w-full scale-[2.15] object-contain object-center" />
              </div>
            </div>

            <p className="mt-8 max-w-4xl text-lg leading-8 text-slate-600 sm:text-xl">
              Una delle grandi opportunita' dell'intelligenza artificiale oggi e' aiutarci ad analizzare informazioni in modo semplice e interattivo.
              Ma nella finanza personale il vero problema non sono i numeri: sono le abitudini.
              Aurora nasce proprio qui: unisce analisi dei dati e comportamento.
            </p>

            <p className="mt-5 max-w-4xl text-base leading-8 text-slate-500 sm:text-lg">
              Non e' solo un'app per gestire il denaro. E' uno strumento per costruire consapevolezza e abitudini nel tempo,
              con un linguaggio semplice e diretto e con la logica 70/20/10 come bussola quotidiana.
            </p>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Button className="rounded-full bg-slate-950 px-6 text-white hover:bg-slate-800" onClick={onOpenSignup}>
                Inizia con Aurora
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <Button variant="ghost" className="rounded-full border border-slate-200 bg-white/80 px-5 text-slate-700 hover:bg-white" onClick={onOpenSignin}>
                Ho gia' un account
              </Button>
            </div>

          </div>

          <div className="grid w-full gap-4 text-left sm:grid-cols-3">
            <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)] backdrop-blur">
              <Wallet className="h-5 w-5 text-orange-500" />
              <p className="mt-3 text-sm font-semibold text-slate-900">Legge il quotidiano</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">Ti aiuta a vedere dove vanno davvero i soldi giorno dopo giorno.</p>
            </div>
            <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)] backdrop-blur">
              <Target className="h-5 w-5 text-orange-500" />
              <p className="mt-3 text-sm font-semibold text-slate-900">Dai direzione</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">Collega spese, obiettivi pianificati e priorita' usando il 70/20/10.</p>
            </div>
            <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)] backdrop-blur">
              <PiggyBank className="h-5 w-5 text-orange-500" />
              <p className="mt-3 text-sm font-semibold text-slate-900">Costruisce routine</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">Piccoli comportamenti costanti oggi, piu' sicurezza e margine domani.</p>
            </div>
          </div>

          <div className="grid w-full gap-5 text-left xl:grid-cols-3">
            <div className="h-full rounded-[2rem] border border-slate-200/80 bg-slate-950 p-6 text-white shadow-[0_28px_90px_rgba(15,23,42,0.18)]">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-orange-300">Immagina questo scenario</p>
              <p className="mt-4 text-lg leading-8 text-slate-100">
                Carichi il tuo estratto conto o inserisci una spesa.
                Aurora analizza automaticamente i movimenti e ti dice:
              </p>
              <div className="mt-5 rounded-[1.4rem] border border-white/10 bg-white/5 p-5 text-left">
                <p className="text-base leading-7 text-orange-100">
                  “Stai spendendo piu' del previsto nel quotidiano e non stai ancora costruendo risparmio.”
                </p>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  E ti propone subito una direzione pratica, senza farti annegare nei numeri.
                </p>
              </div>
            </div>

            <div className="h-full rounded-[2rem] border border-white/80 bg-white/88 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.1)] backdrop-blur">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-orange-600">La logica centrale</p>
              <div className="mt-5 space-y-4">
                <div className="rounded-[1.25rem] bg-orange-50 px-4 py-4">
                  <p className="text-sm font-semibold text-orange-900">70% per le spese quotidiane</p>
                  <p className="mt-1 text-sm leading-6 text-orange-800">Affitto, cibo, salute, trasporti, bollette e anche il tempo libero non pianificato.</p>
                </div>
                <div className="rounded-[1.25rem] bg-sky-50 px-4 py-4">
                  <p className="text-sm font-semibold text-sky-900">20% per obiettivi pianificati</p>
                  <p className="mt-1 text-sm leading-6 text-sky-800">Vacanza, auto, corso, telefono nuovo o qualsiasi traguardo di breve e medio periodo.</p>
                </div>
                <div className="rounded-[1.25rem] bg-emerald-50 px-4 py-4">
                  <p className="text-sm font-semibold text-emerald-900">10% per la riserva di emergenza</p>
                  <p className="mt-1 text-sm leading-6 text-emerald-800">Prima costruisci 3-6 mesi di sicurezza, poi quella quota puo' spostarsi sugli obiettivi di lungo termine.</p>
                </div>
              </div>
            </div>

            <div className="h-full rounded-[2rem] border border-dashed border-slate-300 bg-white/70 p-6 backdrop-blur">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Learning by doing</p>
              <p className="mt-4 text-sm leading-7 text-slate-600">
                Aurora non si limita ad analizzare: ti accompagna nel quotidiano, calcola quanto puoi spendere ogni settimana
                e ti aiuta a capire, giorno dopo giorno, dove stanno andando i tuoi soldi. Il punto non e' solo sapere i numeri,
                ma costruire consapevolezza e abitudini che reggono nel tempo.
              </p>
            </div>
          </div>
        </section>

        <div className="mx-auto flex w-full max-w-[88rem] flex-wrap items-center justify-center gap-3 border-t border-white/80 py-8 text-sm text-slate-500">
          <span>Creato da</span>
          <a
            href="https://linkedin.com/in/stefanni-matos-080411163"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-700 underline-offset-4 hover:underline"
          >
            Stefanni Matos da Oliveira
          </a>
          <span>&amp;</span>
          <a
            href="https://linkedin.com/in/felipeoperti"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-700 underline-offset-4 hover:underline"
          >
            Felipe Operti
          </a>
        </div>
      </main>
    </div>
  );
}

import { useEffect, useState } from 'react';

import { AuthSession, signin, signup } from '../api/client';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';

export type AuthMode = 'signin' | 'signup';

interface AuthDialogProps {
  mode: AuthMode;
  onAuthenticated: (session: AuthSession) => void;
  onModeChange: (mode: AuthMode) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
}

const EMPTY_SIGNUP = {
  email: '',
  nome: '',
  cognome: '',
  eta: '18',
  password: '',
};

const EMPTY_SIGNIN = {
  email: '',
  password: '',
};

export function AuthDialog({
  mode,
  onAuthenticated,
  onModeChange,
  onOpenChange,
  open,
}: AuthDialogProps) {
  const [signupForm, setSignupForm] = useState(EMPTY_SIGNUP);
  const [signinForm, setSigninForm] = useState(EMPTY_SIGNIN);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setError(null);
      setIsSubmitting(false);
    }
  }, [open]);

  const isSignup = mode === 'signup';

  const handleSubmit = async () => {
    setError(null);

    if (isSignup) {
      if (!signupForm.email.includes('@')) return setError('Inserisci un\'email valida.');
      if (!signupForm.nome.trim()) return setError('Nome obbligatorio.');
      if (!signupForm.cognome.trim()) return setError('Cognome obbligatorio.');
      const eta = Number(signupForm.eta);
      if (!Number.isInteger(eta) || eta < 13 || eta > 120) return setError('Età non valida (13–120).');
      if (signupForm.password.length < 8) return setError('La password deve contenere almeno 8 caratteri.');
    } else {
      if (!signinForm.email.includes('@')) return setError('Inserisci un\'email valida.');
      if (!signinForm.password) return setError('Password obbligatoria.');
    }

    setIsSubmitting(true);

    try {
      const session = isSignup
        ? await signup({
            email: signupForm.email,
            nome: signupForm.nome,
            cognome: signupForm.cognome,
            eta: Number(signupForm.eta),
            password: signupForm.password,
          })
        : await signin(signinForm);
      onAuthenticated(session);
      setSignupForm(EMPTY_SIGNUP);
      setSigninForm(EMPTY_SIGNIN);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Operazione non riuscita.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm border-slate-200 bg-white p-8 shadow-xl">
        <DialogHeader className="text-left">
          <DialogTitle className="text-xl">{isSignup ? 'Sign up' : 'Sign in'}</DialogTitle>
        </DialogHeader>

        <div className="mt-4 flex rounded-full border border-slate-200 bg-slate-100 p-1">
          <button
            className={`flex-1 rounded-full px-4 py-2 text-sm transition ${isSignup ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500'}`}
            onClick={() => onModeChange('signup')}
            type="button"
          >
            Sign up
          </button>
          <button
            className={`flex-1 rounded-full px-4 py-2 text-sm transition ${!isSignup ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500'}`}
            onClick={() => onModeChange('signin')}
            type="button"
          >
            Sign in
          </button>
        </div>

        <div className="mt-6 space-y-4">
          {isSignup ? (
            <>
              <Input
                placeholder="Email"
                type="email"
                value={signupForm.email}
                onChange={(event) => setSignupForm((prev) => ({ ...prev, email: event.target.value }))}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  placeholder="Nome"
                  value={signupForm.nome}
                  onChange={(event) => setSignupForm((prev) => ({ ...prev, nome: event.target.value }))}
                />
                <Input
                  placeholder="Cognome"
                  value={signupForm.cognome}
                  onChange={(event) => setSignupForm((prev) => ({ ...prev, cognome: event.target.value }))}
                />
              </div>
              <Input
                placeholder="Età"
                type="number"
                min={13}
                max={120}
                value={signupForm.eta}
                onChange={(event) => setSignupForm((prev) => ({ ...prev, eta: event.target.value }))}
              />
              <Input
                placeholder="Password (min. 8 caratteri)"
                type="password"
                value={signupForm.password}
                onChange={(event) => setSignupForm((prev) => ({ ...prev, password: event.target.value }))}
              />
            </>
          ) : (
            <>
              <Input
                placeholder="Email"
                type="email"
                value={signinForm.email}
                onChange={(event) => setSigninForm((prev) => ({ ...prev, email: event.target.value }))}
              />
              <Input
                placeholder="Password"
                type="password"
                value={signinForm.password}
                onChange={(event) => setSigninForm((prev) => ({ ...prev, password: event.target.value }))}
              />
            </>
          )}
        </div>

        {error ? (
          <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <div className="mt-6 flex gap-3">
          <Button
            className="flex-1 rounded-full bg-slate-950 text-white hover:bg-slate-800"
            disabled={isSubmitting}
            onClick={handleSubmit}
          >
            {isSubmitting ? 'Invio...' : isSignup ? 'Crea account' : 'Accedi'}
          </Button>
          <Button
            className="rounded-full"
            disabled={isSubmitting}
            onClick={() => onOpenChange(false)}
            variant="outline"
          >
            Chiudi
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

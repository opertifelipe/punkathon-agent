import { useState, useRef } from 'react';
import { Send, Paperclip } from 'lucide-react';

interface InputAreaProps {
  onSendMessage: (message: string, attachedFiles: File[]) => void;
  disabled?: boolean;
}

export function InputArea({ onSendMessage, disabled = false }: InputAreaProps) {
  const [input, setInput] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = () => {
    if (disabled) return;
    if (input.trim() || attachedFiles.length > 0) {
      onSendMessage(input, attachedFiles);
      setInput('');
      setAttachedFiles([]);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileAttach = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setAttachedFiles([...attachedFiles, ...Array.from(e.target.files)]);
    }
  };

  return (
    <>
      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-lg dark:border-slate-800 dark:bg-slate-900 dark:shadow-none">
        <div className="flex items-center gap-3 p-4">
          <button 
            onClick={handleFileAttach}
            className="text-gray-400 transition-colors hover:text-gray-600 dark:text-slate-500 dark:hover:text-slate-200"
            aria-label="Allega file"
          >
            <Paperclip className="w-5 h-5" />
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Aggiungi una spesa, scatta una foto di una ricevuta o fai una domanda..."
            className="flex-1 bg-transparent text-gray-700 outline-none placeholder:text-gray-400 dark:text-slate-100 dark:placeholder:text-slate-500"
          />
          <button
            onClick={handleSubmit}
            disabled={disabled || (!input.trim() && attachedFiles.length === 0)}
            className="rounded-lg bg-gray-700 p-2 text-white transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-emerald-500/80 dark:hover:bg-emerald-500"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
        
        {/* Show attached files */}
        {attachedFiles.length > 0 && (
          <div className="px-4 pb-3 flex gap-2 flex-wrap">
            {attachedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center gap-1 rounded-lg bg-gray-100 px-2 py-1 text-xs text-gray-600 dark:bg-slate-950 dark:text-slate-300"
              >
                <span>{file.name}</span>
                <button
                  onClick={() => setAttachedFiles(attachedFiles.filter((_, i) => i !== index))}
                  className="text-gray-400 hover:text-gray-600 dark:text-slate-500 dark:hover:text-slate-200"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        onChange={handleFileChange}
        className="hidden"
        multiple
        accept="image/*,.pdf"
      />
    </>
  );
}
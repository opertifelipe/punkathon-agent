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
      <div className="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden">
        <div className="flex items-center gap-3 p-4">
          <button 
            onClick={handleFileAttach}
            className="text-gray-400 hover:text-gray-600 transition-colors"
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
            className="flex-1 outline-none text-gray-700 placeholder:text-gray-400"
          />
          <button
            onClick={handleSubmit}
            disabled={disabled || (!input.trim() && attachedFiles.length === 0)}
            className="bg-gray-700 hover:bg-gray-800 text-white rounded-lg p-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
                className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-lg flex items-center gap-1"
              >
                <span>{file.name}</span>
                <button
                  onClick={() => setAttachedFiles(attachedFiles.filter((_, i) => i !== index))}
                  className="text-gray-400 hover:text-gray-600"
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
        accept="image/*,.pdf,.doc,.docx"
      />
    </>
  );
}
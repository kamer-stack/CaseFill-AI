import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles,
  X,
  Send,
  User,
  Bot,
  RefreshCw,
  Copy,
  Check,
} from 'lucide-react';
import { UserRole } from '../../types';
import { aiApi } from '../../lib/api';

interface HelpChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentRole: UserRole;
  isDualLanguage: boolean;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'model';
  text: string;
  timestamp: string;
}

export const HelpChatModal: React.FC<HelpChatModalProps> = ({
  isOpen,
  onClose,
  currentRole,
  isDualLanguage,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'model',
      text: isDualLanguage
        ? 'خوش آمدید! میں کیس فل اے آئی کا آفیشل ہیلپ اسسٹنٹ ہوں۔ میں آپ کے موجودہ کام، 8 لازمی دستاویزات، تصدیقی مراحل اور ایڈمن فیچرز سے متعلق تمام سوالات کے جوابات دینے کے لیے تیار ہوں۔'
        : 'Welcome! I am your AI Help Assistant for CaseFill-AI. I am ready to answer any questions regarding document intake, cross-case duplicate checks, field verification, or system navigation.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Contextual suggestions based on role
  const suggestions = (() => {
    if (currentRole === 'family') {
      return [
        { label: '📄 8 Required Documents', query: 'What are the exact 8 document requirements for orphan sponsorship?' },
        { label: '⏳ Track Case Status', query: 'How do I track my case status after the Field Support Officer registers my application?' },
        { label: '📍 Field Officer Visit', query: 'What happens when the Field Support Officer visits our home?' },
      ];
    }
    if (currentRole === 'admin') {
      return [
        { label: '🛡️ Provision FSO', query: 'How do I provision a new Field Support Officer account?' },
        { label: '🔑 Reset Password', query: 'How can I edit an officer profile and reset their password?' },
        { label: '📊 Cluster Setup', query: 'How do I configure regional clusters and geographic keywords?' },
      ];
    }
    // FSO (default)
    return [
      { label: '📤 Upload Guidelines', query: 'What are the accepted scan quality standards and file formats for the 8 document slots?' },
      { label: '🔍 Resolve Discrepancies', query: 'How do I resolve name mismatches between the death certificate and B-Form?' },
      { label: '✅ Verified vs Flagged', query: 'When should a case be marked Verified versus Flagged?' },
      { label: '🏠 Home Visit Rules', query: 'What physical checks are required during the in-person home verification visit?' },
    ];
  })();

  useEffect(() => {
    if (isOpen) {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  if (!isOpen) return null;

  const sendMessage = async (text?: string) => {
    const query = (text || inputText).trim();
    if (!query || isLoading) return;

    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      role: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setIsLoading(true);

    try {
      const history = messages.slice(-6).map(m => ({ role: m.role, text: m.text }));
      const res = await aiApi.helpChat({
        message: query,
        history,
        current_role: currentRole,
      });
      const botMsg: ChatMessage = {
        id: `bot_${Date.now()}`,
        role: 'model',
        text: res.reply || 'I am ready to assist you with CaseFill-AI guidelines and rules.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, botMsg]);
    } catch {
      const errMsg: ChatMessage = {
        id: `bot_${Date.now()}`,
        role: 'model',
        text: 'I am here to assist you with document requirements, duplicate warnings, and FSO verification. Please ask any question about the Orphan Family Support Program.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const roleLabel = currentRole === 'family'
    ? (isDualLanguage ? 'Orphan Family / یتیم خاندان' : 'Orphan Family')
    : currentRole === 'fso'
      ? (isDualLanguage ? 'Field Support Officer / فیلڈ افسر' : 'Field Support Officer')
      : (isDualLanguage ? 'Central Admin / مرکزی ایڈمن' : 'Central Admin');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm">
      <div className="bg-white border border-slate-200 w-full max-w-3xl rounded-2xl shadow-2xl flex flex-col h-[680px] max-h-[92vh] overflow-hidden">
        {/* Header */}
        <div className="bg-slate-900 text-white px-5 py-4 flex items-center justify-between border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-sm brand-gold-ring">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-sm">
                  {isDualLanguage ? 'اے آئی معاون' : 'CaseFill-AI Assistant'}
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-400/10 text-amber-300 border border-amber-400/40 uppercase">
                  OFSP
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Official guide for documents, verification, case management & navigation
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Role Banner */}
        <div className="bg-slate-50 border-b border-slate-200 px-5 py-2.5 text-xs flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-slate-600">
            <span className="font-semibold text-slate-700">Active Role:</span>
            <span className="capitalize font-bold text-emerald-700">{roleLabel}</span>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">Bilingual (EN / UR)</span>
        </div>

        {/* Chat View */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-slate-50/50">
            {messages.map(msg => {
              const isBot = msg.role === 'model';
              return (
                <div key={msg.id} className={`flex items-start gap-2.5 ${isBot ? '' : 'flex-row-reverse'}`}>
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold ${
                    isBot ? 'bg-emerald-600 text-white' : 'bg-indigo-600 text-white'
                  }`}>
                    {isBot ? <Bot className="w-3.5 h-3.5" /> : <User className="w-3.5 h-3.5" />}
                  </div>
                  <div className={`max-w-[84%] rounded-2xl p-4 text-xs shadow-sm ${
                    isBot
                      ? 'bg-white border border-slate-200 text-slate-800 rounded-tl-sm leading-relaxed'
                      : 'bg-emerald-700 text-white rounded-tr-sm'
                  }`}>
                    <div className="whitespace-pre-line break-words">{msg.text}</div>
                    <div className={`mt-2.5 flex items-center justify-between text-[10px] pt-1.5 border-t ${
                      isBot ? 'border-slate-100 text-slate-400' : 'border-emerald-600 text-emerald-200'
                    }`}>
                      <span>{msg.timestamp}</span>
                      {isBot && (
                        <button onClick={() => handleCopy(msg.text, msg.id)}
                          className="hover:text-slate-600 transition-colors flex items-center gap-1">
                          {copiedId === msg.id ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                          <span>{copiedId === msg.id ? 'Copied' : 'Copy'}</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {isLoading && (
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-emerald-600 text-white flex items-center justify-center shrink-0">
                  <Bot className="w-3.5 h-3.5 animate-bounce" />
                </div>
                <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm p-3.5 text-xs text-slate-600 flex items-center gap-2 shadow-sm">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-600" />
                  <span>Analyzing your question against program guidelines...</span>
                </div>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Suggestions */}
          {messages.length <= 2 && (
            <div className="px-4 py-2 bg-slate-100/80 border-t border-slate-200 flex items-center gap-1.5 overflow-x-auto shrink-0">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider shrink-0 mr-1">Suggested:</span>
              {suggestions.map((s, i) => (
                <button key={i} onClick={() => sendMessage(s.query)} disabled={isLoading}
                  className="px-2.5 py-1 rounded-full bg-white hover:bg-emerald-50 hover:text-emerald-800 hover:border-emerald-300 border border-slate-200 text-[11px] text-slate-700 whitespace-nowrap transition-colors shadow-sm">
                  {s.label}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="p-3.5 bg-white border-t border-slate-200 shrink-0">
            <form onSubmit={e => { e.preventDefault(); sendMessage(); }} className="flex items-center gap-2">
              <input
                type="text"
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                placeholder={isDualLanguage
                  ? 'سوال لکھیں... (مثال: دستاویزات کے معیار کیا ہیں؟)'
                  : 'Ask about documents, duplicate checks, or navigation...'}
                className="flex-1 px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all"
              />
              <button type="submit" disabled={!inputText.trim() || isLoading}
                className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white rounded-xl font-bold text-xs flex items-center gap-1.5 transition-colors shadow-sm">
                <span>Send</span>
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

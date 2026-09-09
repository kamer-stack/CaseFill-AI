import React, { useState } from 'react';
import { ChevronDown, HelpCircle, FileStack, MessageCircle } from 'lucide-react';

interface LandingFaqSectionProps {
  isDualLanguage: boolean;
  sectionRef?: React.RefObject<HTMLElement | null>;
}

interface FaqItem {
  question: string;
  answer: string;
}

const FAQ_ITEMS: FaqItem[] = [
  {
    question: 'What is CaseFill-AI?',
    answer:
      'CaseFill-AI is Alkhidmat\'s AI-assisted document intake tool built for Field Support Officers. It scans and extracts key fields from the 8 required orphan sponsorship documents, then presents everything in a structured review screen for you to confirm before submission.',
  },
  {
    question: 'Which documents does it support?',
    answer:
      'All 8 OFSP intake slots: the child\'s picture, school result card, B-Form, father\'s death certificate, mother\'s CNIC, father\'s CNIC (optional), residential address, and mother\'s education level. Scanned documents are OCR\'d via AI; address and education fields are entered directly by the FSO.',
  },
  {
    question: 'Does the AI finalize cases on its own?',
    answer:
      'No. AI extraction is always a draft. Every field must be reviewed and confirmed by an authorized FSO before a case is marked Verified or Flagged. The AI never has final say — your judgment and sign-off are required, with a full audit trail recorded.',
  },
  {
    question: 'What happens when extraction confidence is low?',
    answer:
      'Low-confidence fields are highlighted during review alongside cross-document discrepancies (such as name mismatches between the death certificate and B-Form). You can edit any value manually — nothing is locked to the AI output, and flagged items stay in your queue until resolved.',
  },
  {
    question: 'How is applicant data kept private?',
    answer:
      'Cases are accessible only to authenticated users: provisioned FSOs, Central Admin, and family accounts registered by their assigned officer. Document uploads are processed securely within the platform — there is no public access or self-registration.',
  },
  {
    question: 'Who can sign in to the portal?',
    answer:
      'FSO accounts are provisioned internally by Central Admin using verified CNIC credentials. Family portal accounts are created by the assigned FSO during in-person registration. If you are a new officer, contact your cluster admin to request access.',
  },
];

const DOCUMENTS_FAQ_INDEX = 1;

export const LandingFaqSection: React.FC<LandingFaqSectionProps> = ({
  isDualLanguage,
  sectionRef,
}) => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const toggle = (index: number) => {
    setOpenIndex((prev) => (prev === index ? null : index));
  };

  const scrollToFaq = () => {
    sectionRef?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const viewRequiredDocuments = () => {
    setOpenIndex(DOCUMENTS_FAQ_INDEX);
    scrollToFaq();
  };

  return (
    <>
      <section
        ref={sectionRef}
        id="faq"
        className="py-14 md:py-20 bg-white border-b border-slate-200 scroll-mt-20"
      >
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="text-center space-y-3">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
              <HelpCircle className="w-3.5 h-3.5 text-emerald-600" />
              {/* Compact label: English always shown, Urdu added inline — never a full replace */}
              <span>Frequently Asked Questions{isDualLanguage ? ' / عمومی سوالات' : ''}</span>
            </div>

            <div className="space-y-1">
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
                About CaseFill-AI
              </h2>
              {isDualLanguage && (
                <h2
                  className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight font-urdu"
                  dir="rtl"
                >
                 کے بارے میں CaseFill-AI
                </h2>
              )}
            </div>

            <div className="space-y-1 max-w-lg mx-auto">
              <p className="text-sm text-slate-600 leading-relaxed">
                Common questions about AI-assisted intake, FSO verification, and data handling for Field Support Officers.
              </p>
              {isDualLanguage && (
                <p className="text-sm text-slate-600 leading-relaxed font-urdu" dir="rtl">
                  فیلڈ سپورٹ آفیسرز (FSO) کے لیے اے آئی (AI) کی مدد سے اندراج (intake)، ایف ایس او (FSO) کی تصدیق، اور ڈیٹا ہینڈلنگ سے متعلق عام سوالات
                </p>
              )}
            </div>
          </div>

          <div className="space-y-3">
            {FAQ_ITEMS.map((item, index) => {
              const isOpen = openIndex === index;
              return (
                <div
                  key={item.question}
                  className={`rounded-2xl border transition-colors ${
                    isOpen
                      ? 'bg-emerald-50/50 border-emerald-300 shadow-sm'
                      : 'bg-slate-50 border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => toggle(index)}
                    aria-expanded={isOpen}
                    className="w-full flex items-center justify-between gap-4 px-5 py-4 sm:px-6 sm:py-5 text-left cursor-pointer"
                  >
                    <span className="text-sm sm:text-base font-semibold text-slate-900 pr-2">
                      {item.question}
                    </span>
                    <ChevronDown
                      className={`w-5 h-5 shrink-0 text-emerald-600 transition-transform duration-200 ${
                        isOpen ? 'rotate-180' : ''
                      }`}
                    />
                  </button>
                  <div
                    className={`grid transition-[grid-template-rows] duration-200 ease-out ${
                      isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
                    }`}
                  >
                    <div className="overflow-hidden">
                      <p className="px-5 pb-5 sm:px-6 sm:pb-6 text-sm text-slate-600 leading-relaxed border-t border-slate-200 pt-4">
                        {item.answer}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Need Help CTA bar */}
      <section className="py-10 md:py-12 bg-slate-100 border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="rounded-2xl bg-white border border-emerald-200 shadow-sm p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-6">
            <div className="flex items-start sm:items-center gap-4 text-center sm:text-left">
              <div className="hidden sm:flex w-12 h-12 rounded-2xl bg-emerald-50 border border-emerald-200 items-center justify-center shrink-0">
                <MessageCircle className="w-6 h-6 text-emerald-600" />
              </div>
              <div className="space-y-1">
                <div className="space-y-0.5">
                  <h3 className="text-lg sm:text-xl font-bold text-slate-900">Need Help?</h3>
                  {isDualLanguage && (
                    <h3 className="text-lg sm:text-xl font-bold text-slate-900 font-urdu" dir="rtl">
                      مدد چاہیے؟
                    </h3>
                  )}
                </div>
                <div className="space-y-0.5">
                  <p className="text-sm text-slate-600 max-w-md leading-relaxed">
                    Questions about your FSO account, document requirements, or the intake workflow? Reach out to support or review the required document list.
                  </p>
                  {isDualLanguage && (
                    <p className="text-sm text-slate-600 max-w-md leading-relaxed font-urdu" dir="rtl">
                کیا آپ کے ایف ایس ا و ا کاؤنٹ، مطلوبہ دستاویزات، یا شمولیت کے طریقہ کار کے بارے میں سوالات ہیں؟ سپورٹ سے رابطہ کریں یا ضروری دستاویزات کی فہرست دیکھیں۔
                    </p>
                  )}
                </div>
              </div>
            </div>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full sm:w-auto shrink-0">
              <a
                href="mailto:fso-support@alkhidmat.org"
                className="px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm flex items-center justify-center space-x-2 transition-colors"
              >
                <MessageCircle className="w-4 h-4" />
                {/* Compact combined label, matching the Header's Sign In button convention */}
                <span>Contact Support{isDualLanguage ? ' (سپورٹ سے رابطہ)' : ''}</span>
              </a>
              <button
                type="button"
                onClick={viewRequiredDocuments}
                className="px-6 py-3 rounded-xl bg-white hover:bg-slate-50 text-slate-900 font-bold text-sm border border-slate-300 hover:border-emerald-400 flex items-center justify-center space-x-2 transition-colors cursor-pointer"
              >
                <FileStack className="w-4 h-4 text-emerald-600" />
                <span>View Required Documents{isDualLanguage ? ' (مطلوبہ دستاویزات)' : ''}</span>
              </button>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

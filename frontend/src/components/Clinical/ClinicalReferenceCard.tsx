import React from 'react';
import { BookOpen, FileText, CheckCircle2, Bookmark } from 'lucide-react';

interface ClinicalReferenceCardProps {
  referenceText?: string | null;
  sourceDoc?: string;
  referenceType?: string;
}

export const ClinicalReferenceCard: React.FC<ClinicalReferenceCardProps> = ({
  referenceText = 'Length of stay (LOS) is defined as the duration of a single episode of hospitalization, calculated from admission timestamp to formal discharge.',
  sourceDoc = 'clinical_reference.txt',
  referenceType = 'Clinical Reference (SNOMED-CT)',
}) => {
  return (
    <div className="bg-white border border-gray-200/90 rounded-xl p-3.5 shadow-sm flex flex-col justify-between h-full">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-gray-100">
          <div className="flex items-center space-x-1.5">
            <BookOpen className="w-3.5 h-3.5 text-indigo-600" />
            <h3 className="text-xs font-bold text-gray-900">Clinical Reference</h3>
          </div>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-100">
            &lt;&gt; Ontology Verified
          </span>
        </div>

        {/* Clinical Definition quote box matching Screenshot 1 & 3 */}
        <div className="pt-1">
          <div className="bg-blue-50/30 border-l-2 border-blue-500 rounded-r-lg p-2.5 text-[11px] text-gray-700 italic leading-relaxed">
            "{referenceText}"
          </div>
        </div>
      </div>

      {/* Structured Source & Type Footer matching Screenshot 1 & 3 */}
      <div className="mt-3 pt-2 border-t border-gray-100 flex items-center justify-between text-[10px] font-mono text-gray-400 uppercase tracking-wider">
        <span>{sourceDoc.toUpperCase()}</span>
        <span>{referenceType.toUpperCase()}</span>
      </div>
    </div>
  );
};

export default ClinicalReferenceCard;

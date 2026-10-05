import React from 'react';
import { Database } from 'lucide-react';

interface RagContextCardProps {
  ragContext?: string | null;
}

export const RagContextCard: React.FC<RagContextCardProps> = ({ ragContext }) => {
  const defaultPayload =
    ragContext ||
    '"Table conditions links via encounter_id to encounters.start and encounters.stop. Calculate length of stay using DATEDIFF."';

  return (
    <div className="bg-white border border-gray-200/90 rounded-xl p-4 shadow-sm space-y-3">
      {/* Header matching Screenshot 2 & 4 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Database className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold text-gray-900 leading-tight">
            RAG Retrieval & Vector Store Inspection
          </h3>
        </div>

        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold text-blue-700 bg-blue-50 border border-blue-100">
          Pinecone / FAISS v3
        </span>
      </div>

      {/* Two Stats Boxes Side-by-Side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
        <div className="p-2.5 bg-gray-50/70 border border-gray-100 rounded-lg">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-bold text-gray-800">
              Retrieved Chunks (Top-3)
            </span>
            <span className="font-mono text-[10px] font-semibold text-blue-600">
              Similarity: 0.941
            </span>
          </div>
          <p className="text-[10px] text-gray-500 leading-snug">
            [Chunk #402] SNOMED-CT definition for length of stay (LOS) computation across inpatient conditions and discharge timestamps.
          </p>
        </div>

        <div className="p-2.5 bg-gray-50/70 border border-gray-100 rounded-lg">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-bold text-gray-800">
              Embedding Model & Index
            </span>
            <span className="font-mono text-[10px] font-semibold text-emerald-600">
              1,536 dims
            </span>
          </div>
          <p className="text-[10px] text-gray-500 leading-snug">
            text-embedding-3-small vector index queried with cosine distance metric against organization schema.
          </p>
        </div>
      </div>

      {/* Dark Injected RAG Context Payload Box */}
      <div className="bg-[#0B0F19] text-gray-200 font-mono text-[11px] p-3 rounded-lg border border-gray-800 leading-relaxed shadow-inner">
        <div className="text-[10px] font-mono text-gray-500 mb-1">
          # Injected RAG Context Payload
        </div>
        <p className="text-emerald-400 text-xs font-mono">
          {defaultPayload}
        </p>
      </div>
    </div>
  );
};

export default RagContextCard;


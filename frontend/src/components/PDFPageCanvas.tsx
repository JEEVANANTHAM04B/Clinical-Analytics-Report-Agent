import React, { useEffect, useRef, useState } from 'react';
import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist';

interface PDFPageCanvasProps {
  pageNumber: number;
  pdf: PDFDocumentProxy;
  scale: number;
  onVisible?: (pageNumber: number) => void;
}

export const PDFPageCanvas: React.FC<PDFPageCanvasProps> = ({
  pageNumber,
  pdf,
  scale,
  onVisible,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);
  const [isRendered, setIsRendered] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    const renderPage = async () => {
      try {
        const page = await pdf.getPage(pageNumber);
        if (isCancelled) return;

        // Cancel previous render task if active
        if (renderTaskRef.current) {
          try {
            renderTaskRef.current.cancel();
          } catch {
            // Cancel errors are expected when re-rendering
          }
          renderTaskRef.current = null;
        }

        const viewport = page.getViewport({ scale });
        setDimensions({ width: viewport.width, height: viewport.height });

        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d', { alpha: false });
        if (!ctx) return;

        const outputScale = window.devicePixelRatio || 1;
        canvas.width = Math.floor(viewport.width * outputScale);
        canvas.height = Math.floor(viewport.height * outputScale);
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;

        const renderContext = {
          canvasContext: ctx,
          viewport: viewport,
          transform: transform ?? undefined,
        };

        const task = page.render(renderContext);
        renderTaskRef.current = task;

        await task.promise;
        if (!isCancelled) {
          setIsRendered(true);
        }
      } catch (err: any) {
        if (err?.name !== 'RenderingCancelledException') {
          console.error(`PDF.js Page ${pageNumber} render error:`, err);
        }
      }
    };

    renderPage();

    return () => {
      isCancelled = true;
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch {
          // ignore
        }
        renderTaskRef.current = null;
      }
    };
  }, [pdf, pageNumber, scale]);

  // Track page visibility for Page X of Y indicator
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !onVisible) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && entry.intersectionRatio >= 0.35) {
            onVisible(pageNumber);
          }
        });
      },
      { threshold: [0.1, 0.35, 0.6] }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [pageNumber, onVisible]);

  return (
    <div
      id={`pdf-page-${pageNumber}`}
      ref={containerRef}
      className="relative mb-6 bg-white rounded-lg shadow-lg ring-1 ring-[#CBD5E1] overflow-hidden transition-all duration-200"
      style={{
        width: dimensions ? `${Math.floor(dimensions.width)}px` : 'auto',
        minHeight: dimensions ? `${Math.floor(dimensions.height)}px` : '500px',
      }}
    >
      {/* Individual Page Badge */}
      <div className="absolute top-3 right-3 z-10 select-none pointer-events-none opacity-70 hover:opacity-100 transition-opacity">
        <span className="px-2.5 py-1 text-[11px] font-semibold bg-[#EEF2FF] text-[#4F46E5] rounded-full shadow-xs">
          Page {pageNumber} of {pdf.numPages}
        </span>
      </div>

      {/* Rendered PDF Page Canvas */}
      <canvas ref={canvasRef} className="block w-full h-auto bg-white" />

      {/* Loading state before first render */}
      {!isRendered && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-50/90 backdrop-blur-xs">
          <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-2" />
          <span className="text-xs text-gray-500 font-medium">Loading Page {pageNumber}...</span>
        </div>
      )}
    </div>
  );
};

export default PDFPageCanvas;

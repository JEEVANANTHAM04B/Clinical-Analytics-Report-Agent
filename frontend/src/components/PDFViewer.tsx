import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker?url';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  Maximize2, 
  Minimize2, 
  ChevronUp, 
  ChevronDown, 
  Maximize, 
  FileText,
  AlertCircle
} from 'lucide-react';
import PDFPageCanvas from './PDFPageCanvas';

// Configure the PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;

interface PDFViewerProps {
  pdfBlob?: Blob | null;
  pdfUrl?: string | null;
  className?: string;
}

export const PDFViewer: React.FC<PDFViewerProps> = ({
  pdfBlob,
  pdfUrl,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Zoom management
  const [zoomMode, setZoomMode] = useState<'fit-width' | 'fit-page' | 'custom'>('fit-width');
  const [zoomPercent, setZoomPercent] = useState<number>(100);
  const [containerDimensions, setContainerDimensions] = useState<{ width: number; height: number }>({
    width: 800,
    height: 700,
  });
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  // Measure container dimensions for responsive scaling
  useEffect(() => {
    const el = scrollAreaRef.current;
    if (!el) return;

    const updateDimensions = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0) {
        setContainerDimensions({ width: rect.width, height: rect.height });
      }
    };

    updateDimensions();

    const resizeObserver = new ResizeObserver(() => {
      updateDimensions();
    });

    resizeObserver.observe(el);
    return () => resizeObserver.disconnect();
  }, []);

  // Load PDF Document from blob or URL
  useEffect(() => {
    let isCancelled = false;

    const loadPdf = async () => {
      setIsLoading(true);
      setErrorMessage(null);
      setPdfDoc(null);

      try {
        let loadingTask;

        if (pdfBlob) {
          const arrayBuffer = await pdfBlob.arrayBuffer();
          if (isCancelled) return;
          loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        } else if (pdfUrl) {
          loadingTask = pdfjsLib.getDocument(pdfUrl);
        } else {
          setIsLoading(false);
          return;
        }

        const loadedDoc = await loadingTask.promise;
        if (isCancelled) return;

        setPdfDoc(loadedDoc);
        setNumPages(loadedDoc.numPages);
        setCurrentPage(1);
        setIsLoading(false);
      } catch (err: any) {
        if (!isCancelled) {
          console.error('Failed to load PDF document:', err);
          setErrorMessage(err?.message || 'Failed to load PDF document');
          setIsLoading(false);
        }
      }
    };

    loadPdf();

    return () => {
      isCancelled = true;
    };
  }, [pdfBlob, pdfUrl]);

  // Compute effective scale
  // Standard A4 dimensions in points: width 595.28, height 841.89
  const A4_WIDTH = 595.28;
  const A4_HEIGHT = 841.89;

  const calculateEffectiveScale = useCallback((): number => {
    const availableWidth = Math.max(containerDimensions.width - 48, 320);
    const availableHeight = Math.max(containerDimensions.height - 48, 400);

    if (zoomMode === 'fit-width') {
      // Scale so page fits comfortably within available width with max cap for ultra-wide screens
      const targetWidth = Math.min(availableWidth, 920);
      return targetWidth / A4_WIDTH;
    } else if (zoomMode === 'fit-page') {
      const scaleX = availableWidth / A4_WIDTH;
      const scaleY = availableHeight / A4_HEIGHT;
      return Math.min(scaleX, scaleY);
    } else {
      // Custom zoom: baseline 100% corresponds to ~800px width (scale = 1.34)
      const baseScale = 1.34;
      return baseScale * (zoomPercent / 100);
    }
  }, [containerDimensions, zoomMode, zoomPercent]);

  const effectiveScale = calculateEffectiveScale();

  // Scroll to a specific page
  const scrollToPage = useCallback((pageNum: number) => {
    if (pageNum < 1 || pageNum > numPages) return;
    const pageEl = document.getElementById(`pdf-page-${pageNum}`);
    if (pageEl) {
      pageEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setCurrentPage(pageNum);
    }
  }, [numPages]);

  // Fullscreen toggle
  const toggleFullscreen = () => {
    const target = containerRef.current;
    if (!target) return;

    if (!document.fullscreenElement) {
      target.requestFullscreen().then(() => {
        setIsFullscreen(true);
      }).catch((err) => {
        console.warn('Fullscreen request failed:', err);
      });
    } else {
      document.exitFullscreen().then(() => {
        setIsFullscreen(false);
      }).catch(() => {});
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Zoom handlers
  const handleZoomIn = () => {
    setZoomMode('custom');
    setZoomPercent((prev) => Math.min(prev + 15, 200));
  };

  const handleZoomOut = () => {
    setZoomMode('custom');
    setZoomPercent((prev) => Math.max(prev - 15, 50));
  };

  const handleResetZoom = () => {
    setZoomMode('custom');
    setZoomPercent(100);
  };

  const handleFitWidth = () => {
    setZoomMode('fit-width');
  };

  const handleFitPage = () => {
    setZoomMode('fit-page');
  };

  return (
    <div
      ref={containerRef}
      className={`flex flex-col h-full w-full bg-slate-900 select-none overflow-hidden ${className}`}
    >
      {/* PDF Controls Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 bg-slate-800 border-b border-slate-700/80 text-slate-200 text-xs shadow-md z-20">
        {/* Left: Page Navigation */}
        <div className="flex items-center space-x-1.5">
          <button
            onClick={() => scrollToPage(currentPage - 1)}
            disabled={currentPage <= 1 || isLoading}
            title="Previous Page"
            className="p-1 rounded-md hover:bg-slate-700 disabled:opacity-40 disabled:hover:bg-transparent transition-colors cursor-pointer text-slate-300"
          >
            <ChevronUp className="w-4 h-4" />
          </button>

          <div className="flex items-center space-x-1 px-1.5 py-0.5 bg-slate-900/60 rounded border border-slate-700 font-mono text-[11px]">
            <span className="font-semibold text-white">{currentPage}</span>
            <span className="text-slate-400">/</span>
            <span className="text-slate-300">{numPages || '–'}</span>
          </div>

          <button
            onClick={() => scrollToPage(currentPage + 1)}
            disabled={currentPage >= numPages || isLoading}
            title="Next Page"
            className="p-1 rounded-md hover:bg-slate-700 disabled:opacity-40 disabled:hover:bg-transparent transition-colors cursor-pointer text-slate-300"
          >
            <ChevronDown className="w-4 h-4" />
          </button>

          {/* Quick Page Jump Dropdown */}
          {numPages > 1 && (
            <select
              value={currentPage}
              onChange={(e) => scrollToPage(Number(e.target.value))}
              className="ml-1 bg-slate-900 text-slate-300 border border-slate-700 rounded px-1.5 py-0.5 text-[11px] focus:outline-hidden focus:ring-1 focus:ring-indigo-500 cursor-pointer"
            >
              {Array.from({ length: numPages }, (_, i) => i + 1).map((p) => (
                <option key={p} value={p}>
                  Page {p}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Center: Zoom Controls */}
        <div className="flex items-center space-x-1 sm:space-x-2">
          <button
            onClick={handleZoomOut}
            disabled={isLoading}
            title="Zoom Out"
            className="p-1 rounded-md hover:bg-slate-700 transition-colors cursor-pointer text-slate-300 disabled:opacity-40"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={handleResetZoom}
            disabled={isLoading}
            title="Reset to 100%"
            className="px-2 py-0.5 rounded-md hover:bg-slate-700 font-mono text-[11px] text-slate-200 transition-colors cursor-pointer disabled:opacity-40"
          >
            {zoomMode === 'custom' ? `${zoomPercent}%` : '100%'}
          </button>

          <button
            onClick={handleZoomIn}
            disabled={isLoading}
            title="Zoom In"
            className="p-1 rounded-md hover:bg-slate-700 transition-colors cursor-pointer text-slate-300 disabled:opacity-40"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>

          <div className="h-3.5 w-px bg-slate-700 mx-1 hidden sm:block" />

          {/* Fit Width */}
          <button
            onClick={handleFitWidth}
            disabled={isLoading}
            title="Fit Width"
            className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors cursor-pointer ${
              zoomMode === 'fit-width'
                ? 'bg-indigo-600 text-white font-semibold shadow-xs'
                : 'hover:bg-slate-700 text-slate-300'
            }`}
          >
            Fit Width
          </button>

          {/* Fit Page */}
          <button
            onClick={handleFitPage}
            disabled={isLoading}
            title="Fit Entire Page"
            className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors cursor-pointer hidden md:inline-block ${
              zoomMode === 'fit-page'
                ? 'bg-indigo-600 text-white font-semibold shadow-xs'
                : 'hover:bg-slate-700 text-slate-300'
            }`}
          >
            Fit Page
          </button>
        </div>

        {/* Right: Fullscreen and Document Info */}
        <div className="flex items-center space-x-2">
          <div className="hidden lg:flex items-center space-x-1.5 text-slate-400 text-[11px]">
            <FileText className="w-3.5 h-3.5 text-indigo-400" />
            <span>Official Clinical Audit PDF</span>
          </div>

          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Fullscreen' : 'Open Fullscreen'}
            className="p-1 rounded-md hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer flex items-center space-x-1"
          >
            {isFullscreen ? (
              <>
                <Minimize2 className="w-3.5 h-3.5" />
                <span className="hidden sm:inline text-[11px]">Exit Fullscreen</span>
              </>
            ) : (
              <>
                <Maximize2 className="w-3.5 h-3.5" />
                <span className="hidden sm:inline text-[11px]">Fullscreen</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Scrollable Document Viewing Area */}
      <div
        ref={scrollAreaRef}
        className="flex-1 overflow-y-auto overflow-x-auto p-4 sm:p-6 bg-slate-950 flex flex-col items-center justify-start min-h-0"
      >
        {/* Loading Spinner */}
        {isLoading && (
          <div className="my-auto py-16 flex flex-col items-center justify-center text-center">
            <div className="w-10 h-10 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-sm font-semibold text-slate-200">
              Loading Certified 5-Page Clinical Analytics Document...
            </p>
            <p className="text-xs text-slate-400 mt-1 max-w-sm">
              Rendering vector report pages with verified EHR database query outcomes.
            </p>
          </div>
        )}

        {/* Error State */}
        {errorMessage && !isLoading && (
          <div className="my-auto py-12 px-6 max-w-md bg-rose-950/40 border border-rose-800/80 rounded-xl text-center">
            <AlertCircle className="w-8 h-8 text-rose-400 mx-auto mb-2" />
            <h3 className="text-sm font-bold text-rose-200">Failed to render PDF preview</h3>
            <p className="text-xs text-rose-300/80 mt-1">{errorMessage}</p>
          </div>
        )}

        {/* PDF Pages Stack */}
        {!isLoading && pdfDoc && numPages > 0 && (
          <div className="flex flex-col items-center w-full">
            {Array.from({ length: numPages }, (_, index) => {
              const pageNumber = index + 1;
              return (
                <PDFPageCanvas
                  key={`page-${pageNumber}`}
                  pageNumber={pageNumber}
                  pdf={pdfDoc}
                  scale={effectiveScale}
                  onVisible={(visiblePage) => setCurrentPage(visiblePage)}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default PDFViewer;

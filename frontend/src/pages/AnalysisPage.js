import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

import 'katex/dist/katex.min.css';
import 'github-markdown-css/github-markdown-light.css';

import { API_BASE_URL } from '../App';

// --- Sub-components for the new UI ---

const Lightbox = ({ src, onClose }) => (
    <div className="lightbox-overlay" onClick={onClose}>
        <div className="lightbox-content">
            <button className="lightbox-close-button" onClick={onClose}>&times;</button>
            <img src={src} alt="Lightbox content" />
        </div>
    </div>
);

// New CollapsibleFiguresGallery Component
const CollapsibleFiguresGallery = ({ images }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [lightboxSrc, setLightboxSrc] = useState(null);

    if (!images || images.length === 0) {
        return null;
    }

    return (
        <div className="mt-4 p-3 border rounded shadow-sm">
            <h4 className="mb-3" style={{ cursor: 'pointer' }} onClick={() => setIsOpen(!isOpen)}>
                <i className={`bi ${isOpen ? 'bi-caret-down-fill' : 'bi-caret-right-fill'} me-2`}></i>
                论文图集 ({images.length} 张)
            </h4>
            {isOpen && (
                <div className="thumbnail-gallery d-flex flex-wrap justify-content-center">
                    {images.map((image, index) => (
                        <div key={index} className="thumbnail-item m-2" onClick={() => setLightboxSrc(image.src)} style={{ cursor: 'pointer', width: '150px', height: '150px', overflow: 'hidden', border: '1px solid #ddd', borderRadius: '5px' }}>
                            <img src={image.src} alt={image.alt} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                        </div>
                    ))}
                </div>
            )}
            {lightboxSrc && <Lightbox src={lightboxSrc} onClose={() => setLightboxSrc(null)} />}
        </div>
    );
};

// --- Main Analysis Page Component ---

function AnalysisPage() {
    const { paperId } = useParams();
    const [paper, setPaper] = useState(null);
    const [status, setStatus] = useState('running');
    const [content, setContent] = useState('');
    const [error, setError] = useState('');
    const [lightboxSrc, setLightboxSrc] = useState(null);
    const [galleryImages, setGalleryImages] = useState([]); // New state for gallery images

    const intervalRef = useRef(null);

    useEffect(() => {
        const storedPaper = localStorage.getItem(`paper_for_analysis_${paperId}`);
        if (storedPaper) {
            setPaper(JSON.parse(storedPaper));
        } else {
            setStatus('error');
            setError('Paper data not found in local storage.');
        }
    }, [paperId]);

    const checkStatus = React.useCallback(async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/api/analysis-status/${paperId}`);
            if (response.data.status === 'success') {
                setStatus('success');
                let fullContent = response.data.content;

                // Extract FIGURES_GALLERY_DATA from HTML comment
                const galleryDataRegex = /<!-- FIGURES_GALLERY_DATA: (.*?) -->/s;
                const match = fullContent.match(galleryDataRegex);
                if (match && match[1]) {
                    try {
                        const parsedData = JSON.parse(match[1]);
                        setGalleryImages(parsedData);
                        // Remove the comment from the content before setting it
                        fullContent = fullContent.replace(match[0], '');
                    } catch (jsonError) {
                        console.error("Failed to parse gallery JSON:", jsonError);
                    }
                }
                
                setContent(fullContent);
                if (intervalRef.current) clearInterval(intervalRef.current);
            } else if (response.data.status === 'error') {
                setStatus('error');
                setError(response.data.message);
                if (intervalRef.current) clearInterval(intervalRef.current);
            }
        } catch (err) {
            setStatus('error');
            setError('Failed to fetch analysis status.');
            if (intervalRef.current) clearInterval(intervalRef.current);
        }
    }, [paperId]);

    useEffect(() => {
        if (paper) {
            axios.post(`${API_BASE_URL}/api/analyze-paper`, { paper });
            intervalRef.current = setInterval(checkStatus, 3000);
        }
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [paper, checkStatus]);

    if (!paper && status !== 'running') {
        return <div className="alert alert-danger">Error: Paper data could not be loaded.</div>;
    }

    const containerStyle = {
        maxWidth: '900px',
        margin: '0 auto'
    };

    return (
        <div className="container mt-4" style={containerStyle}>
            <div className="d-flex justify-content-between align-items-center mb-3">
                <h2 className="mb-0">Analysis Result</h2>
                <Link to="/" className="btn btn-secondary">Back to Home</Link>
            </div>

            {status === 'running' && (
                <div className="d-flex align-items-center alert alert-info">...Loading Analysis...</div>
            )}
            {status === 'error' && (
                <div className="alert alert-danger"><h4>An Error Occurred</h4><p>{error}</p></div>
            )}

            {status === 'success' && (
                <>
                    <div className="card shadow-sm">
                        <div className="card-body markdown-body">
                            <ReactMarkdown 
                                remarkPlugins={[remarkGfm, remarkMath]} 
                                rehypePlugins={[rehypeKatex]}
                            >
                                {content}
                            </ReactMarkdown>
                        </div>
                    </div>

                    {/* Render the new collapsible figures gallery */}
                    <CollapsibleFiguresGallery images={galleryImages} />
                </>
            )}
        </div>
    );
}

export default AnalysisPage;

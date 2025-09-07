import React, { useState, useEffect, useRef } from 'react';
import { useParams, useLocation, Link } from 'react-router-dom';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css'; // Import KaTeX CSS
import { API_BASE_URL } from '../App';

function AnalysisPage() {
    const { paperId } = useParams();
    const location = useLocation();

    // Retrieve paper data: first from location state, then fallback to sessionStorage.
    let paper = location.state?.paper;
    if (!paper) {
        const storedPaper = sessionStorage.getItem(`paper_for_analysis_${paperId}`);
        if (storedPaper) {
            paper = JSON.parse(storedPaper);
        }
    }

    const [status, setStatus] = useState('running');
    const [content, setContent] = useState('');
    const [error, setError] = useState('');
    const [recipientEmail, setRecipientEmail] = useState('');
    const [emailStatus, setEmailStatus] = useState('idle'); // idle, sending, success, error

    const intervalRef = useRef(null);

    const checkStatus = React.useCallback(async () => {
        try {
            const encodedPaperId = encodeURIComponent(paperId);
            const response = await axios.get(`${API_BASE_URL}/api/analysis-status/${encodedPaperId}`);
            
            if (response.data.status === 'success') {
                setStatus('success');
                setContent(response.data.content);
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

    const handleSendEmail = async () => {
        if (!recipientEmail) {
            alert('Please enter a recipient email address.');
            return;
        }
        setEmailStatus('sending');
        try {
            await axios.post(`${API_BASE_URL}/api/email-result`, { paper, email: recipientEmail });
            setEmailStatus('success');
        } catch (err) {
            setEmailStatus('error');
        }
    };

    if (!paper) {
        return (
            <div className="alert alert-danger">Error: Paper data not found. Please go back to the results page and try again.</div>
        );
    }

    return (
        <div className="container mt-4">
            <div className="d-flex justify-content-between align-items-center mb-3">
                <h2 className="mb-0">Analysis Result</h2>
                <Link to="/results" className="btn btn-secondary">Back to Results</Link>
            </div>

            {status === 'running' && (
                <div className="d-flex align-items-center alert alert-info">
                    <div className="spinner-border me-3" role="status"></div>
                    <strong>Analyzing paper... This may take a few minutes. The page will update automatically.</strong>
                </div>
            )}

            {status === 'error' && (
                <div className="alert alert-danger">
                    <h4>An Error Occurred</h4>
                    <p>{error}</p>
                </div>
            )}

            {status === 'success' && (
                <div className="card shadow-sm">
                    <div className="card-header">
                        <div className="input-group">
                            <input 
                                type="email"
                                className="form-control"
                                placeholder="Enter email to send results..."
                                value={recipientEmail}
                                onChange={(e) => setRecipientEmail(e.target.value)}
                                disabled={emailStatus === 'sending'}
                            />
                            <button 
                                className="btn btn-primary" 
                                onClick={handleSendEmail}
                                disabled={emailStatus === 'sending'}
                            >
                                {emailStatus === 'sending' ? 'Sending...' : 'Send to Email'}
                            </button>
                        </div>
                        {emailStatus === 'success' && <div className="text-success mt-2">Email sent successfully!</div>}
                        {emailStatus === 'error' && <div className="text-danger mt-2">Failed to send email.</div>}
                    </div>
                    <div className="card-body">
                        <ReactMarkdown 
                            remarkPlugins={[remarkGfm, remarkMath]} 
                            rehypePlugins={[rehypeKatex]}
                        >
                            {content}
                        </ReactMarkdown>
                    </div>
                </div>
            )}
        </div>
    );
}

export default AnalysisPage;
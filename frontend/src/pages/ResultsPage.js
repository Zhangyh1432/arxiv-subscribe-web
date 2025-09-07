import React, { useState, useMemo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../App';

const PaperCard = ({ paper, isSelected, onSelect, onTranslate, onAnalyze, translation }) => {
    const { translated_title, translated_abstract, status: translationStatus } = translation || {};
    const isCardProcessing = translationStatus === 'translating';

    return (
        <div className={`card mb-3 shadow-sm ${isCardProcessing ? 'opacity-50' : ''}`}>
            <div className="card-header d-flex justify-content-start align-items-center">
                <input 
                    type="checkbox" 
                    className="form-check-input me-3" 
                    style={{transform: 'scale(1.5)'}}
                    checked={isSelected}
                    onChange={() => onSelect(paper.entry_id)}
                />
                <div>
                    <h5 className="mb-0">{paper.title}</h5>
                    {translated_title && <h6 className="text-dark fw-bold mb-0 mt-1 fs-5">{translated_title.replace(/^标题[:：]?\s*/, '')}</h6>}
                </div>
            </div>
            <div className="card-body">
                <p><strong>Authors:</strong> {paper.authors.join(', ')}</p>
                <p><strong>Published:</strong> {new Date(paper.published).toLocaleDateString()}</p>
                <p><strong>Categories:</strong> {paper.categories.join(', ')}</p>
                <p><strong>Summary:</strong> {paper.summary}</p>
                {translated_abstract && <p className="mt-1 fs-6" style={{ fontFamily: 'KaiTi, "楷体", serif' }}>{translated_abstract}</p>}
                
                <a href={paper.pdf_url} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-info me-2">View PDF</a>
                
                <button 
                    className="btn btn-sm btn-secondary me-2"
                    onClick={() => onTranslate(paper)}
                    disabled={isCardProcessing}
                >
                    {translationStatus === 'translating' ? 'Translating...' : (translationStatus === 'translated' ? 'Re-translate' : 'Translate')}
                </button>

                <button 
                    className="btn btn-sm btn-success"
                    onClick={() => onAnalyze(paper)}
                    disabled={isCardProcessing}
                >
                    Analyze
                </button>
                {translationStatus === 'error' && <p className='text-danger mt-2'>Translation failed.</p>}
            </div>
        </div>
    );
};

function ResultsPage({ startPolling }) {
    const [selectedPapers, setSelectedPapers] = useState({});
    const [email, setEmail] = useState('');
    const [translations, setTranslations] = useState({});
    const location = useLocation();

    const uniquePapers = useMemo(() => {
        let papers = [];
        const queryParams = new URLSearchParams(location.search);
        const storageKey = queryParams.get('sessionKey');

        if (storageKey) {
            const storedPapers = localStorage.getItem(storageKey);
            if (storedPapers) {
                papers = JSON.parse(storedPapers);
                localStorage.removeItem(storageKey);
            }
        } else if (location.state?.papers) {
            papers = location.state.papers;
        }
        return papers;
    }, [location]);

    const handleSelectPaper = (paperId) => {
        setSelectedPapers(prev => ({ ...prev, [paperId]: !prev[paperId] }));
    };

    const handleSelectAll = (e) => {
        const isSelected = e.target.checked;
        const allIds = {};
        if (isSelected) {
            uniquePapers.forEach(p => allIds[p.entry_id] = true);
        }
        setSelectedPapers(allIds);
    };

    const handleAnalyzeAndEmail = async () => {
        const papersToProcess = uniquePapers.filter(p => selectedPapers[p.entry_id]);
        if (papersToProcess.length === 0) {
            alert("Please select at least one paper to analyze.");
            return;
        }
        const payload = { papers: papersToProcess, email: email };
        alert("Starting bulk analysis. You will be notified via the status banner on the main page.");
        try {
            await axios.post(`${API_BASE_URL}/api/analyze-and-email`, payload);
            if(startPolling) startPolling();
        } catch (error) {
            alert(`Failed to start bulk analysis: ${error.response?.data?.message || 'Unknown error'}`);
        }
    };

    const handleTranslate = async (paper) => {
        setTranslations(prev => ({ ...prev, [paper.entry_id]: { status: 'translating' } }));
        try {
            const response = await axios.post(`${API_BASE_URL}/api/translate`, { 
                title: paper.title, 
                abstract: paper.summary 
            });
            setTranslations(prev => ({ 
                ...prev, 
                [paper.entry_id]: { ...response.data, status: 'translated' } 
            }));
        } catch (error) {
            setTranslations(prev => ({ ...prev, [paper.entry_id]: { status: 'error' } }));
        }
    };

    const handleAnalyze = (paper) => {
        const shortId = paper.entry_id.split('/').pop();
        localStorage.setItem(`paper_for_analysis_${shortId}`, JSON.stringify(paper));
        window.open(`/analysis/${shortId}`, '_blank');
    };

    const selectedCount = Object.keys(selectedPapers).filter(id => selectedPapers[id]).length;

    return (
        <div className="card shadow-lg">
            <div className="card-header text-center bg-dark text-white">
                <h2>Review and Analyze Papers ({uniquePapers.length} Found)</h2>
            </div>
            <div className="card-body">
                <div className="mb-3">
                    <Link to="/" className="btn btn-secondary mb-3"> &larr; Back to Query Page</Link>
                </div>
                
                <div className="card p-3 mb-3 sticky-top bg-light shadow-sm">
                    <div className="d-flex justify-content-between align-items-center mb-3">
                        <div className="form-check">
                            <input type="checkbox" className="form-check-input" id="selectAll" onChange={handleSelectAll} />
                            <label className="form-check-label" htmlFor="selectAll">
                                Select All ({selectedCount} / {uniquePapers.length} selected)
                            </label>
                        </div>
                        <button 
                            className="btn btn-primary" 
                            disabled={selectedCount === 0}
                            onClick={handleAnalyzeAndEmail}
                        >
                            {`Analyze & Email Selected (${selectedCount})`}
                        </button>
                    </div>
                    <div className="form-group">
                        <label htmlFor="emailInput">Recipient Email for Bulk Send (optional)</label>
                        <input 
                            type="email" 
                            className="form-control"
                            id="emailInput"
                            placeholder="Leave blank for default..."
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                        />
                    </div>
                </div>

                {uniquePapers.map(paper => (
                    <PaperCard 
                        key={paper.entry_id} 
                        paper={paper}
                        isSelected={!!selectedPapers[paper.entry_id]}
                        onSelect={handleSelectPaper}
                        onTranslate={handleTranslate}
                        onAnalyze={handleAnalyze}
                        translation={translations[paper.entry_id] || {}}
                    />
                ))}
            </div>
        </div>
    );
}

export default ResultsPage;
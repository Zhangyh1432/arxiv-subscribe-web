import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../App';
import presets from '../category-presets.json';

const AVAILABLE_CATEGORIES = [
    "cs.AI", "cs.CL", "cs.CC", "cs.CE", "cs.CG", "cs.GT", "cs.CV", "cs.CY", 
    "cs.CR", "cs.DS", "cs.DB", "cs.DL", "cs.DM", "cs.DC", "cs.ET", "cs.FL", 
    "cs.GL", "cs.GR", "cs.AR", "cs.HC", "cs.IR", "cs.IT", "cs.LO", "cs.LG", 
    "cs.MS", "cs.MA", "cs.MM", "cs.NI", "cs.NE", "cs.NA", "cs.OS", "cs.PF", 
    "cs.PL", "cs.RO", "cs.SI", "cs.SE", "cs.SD", "cs.SC", "cs.SY", "cs.HCI"
];

function QueryPage({ status, setStatus, setMessage, startPolling }) {
    const [dateRange, setDateRange] = useState('recent');
    const [selectedCategories, setSelectedCategories] = useState({});
    const [keywords, setKeywords] = useState('');
    const [categoryPresets, setCategoryPresets] = useState({});
    const [recentPapers, setRecentPapers] = useState([]);

    const fetchRecent = async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/api/recent-analyses?_=${new Date().getTime()}`);
            setRecentPapers(response.data);
        } catch (error) {
            console.error("Failed to fetch recent papers:", error);
        }
    };

    useEffect(() => {
        setCategoryPresets(presets);
        fetchRecent();
        const handleFocus = () => fetchRecent();
        window.addEventListener('focus', handleFocus);
        return () => window.removeEventListener('focus', handleFocus);
    }, []);

    const handleCategoryChange = (category) => {
        setSelectedCategories(prev => ({ ...prev, [category]: !prev[category] }));
    };

    const handlePresetClick = (presetName) => {
        const presetCategories = categoryPresets[presetName];
        const newSelected = {};
        AVAILABLE_CATEGORIES.forEach(cat => {
            newSelected[cat] = presetCategories.includes(cat);
        });
        setSelectedCategories(newSelected);
    };

    const handleClearSelection = () => {
        setSelectedCategories({});
    };

    const handleSelectAll = (e) => {
        const allSelected = {};
        if (e.target.checked) {
            AVAILABLE_CATEGORIES.forEach(cat => { allSelected[cat] = true; });
        }
        setSelectedCategories(allSelected);
    };

    const handleClearCache = async () => {
        const isConfirmed = window.confirm("Are you sure you want to clear all cache? This is irreversible.");
        if (isConfirmed) {
            try {
                setStatus('running');
                setMessage('Clearing cache...');
                const response = await axios.post(`${API_BASE_URL}/api/clear-cache`);
                setStatus('success');
                setMessage(response.data.message || 'Cache cleared successfully.');
                fetchRecent();
            } catch (error) {
                setStatus('error');
                setMessage(error.response?.data?.message || 'Failed to clear cache.');
            }
        }
    };

    const handleRunProcess = async () => {
        if (status === 'running') return;
        
        const finalKeywords = keywords.split(',').map(kw => kw.trim()).filter(kw => kw);
        if (finalKeywords.length === 0) {
            setMessage("Please enter at least one keyword.");
            return;
        }

        const finalCategories = Object.keys(selectedCategories).filter(cat => selectedCategories[cat]);

        const payload = {
            date_range: dateRange !== 'recent' ? dateRange : null,
            categories: finalCategories.length > 0 ? finalCategories : null,
            keywords: finalKeywords,
        };

        setStatus('running');
        setMessage('Fetching papers...');
        
        try {
            await axios.post(`${API_BASE_URL}/api/run-fetch`, payload);
            startPolling();
        } catch (error) {
            setMessage(error.response?.data?.message || 'Failed to start the process.');
            setStatus('error');
        }
    };
    
    const numSelected = Object.keys(selectedCategories).filter(cat => selectedCategories[cat]).length;
    const allSelected = numSelected === AVAILABLE_CATEGORIES.length;

    return (
        <>
            <div className="card shadow-sm mb-4">
                <div className="card-header text-center bg-dark text-white">
                    <h2>arXiv Advanced Subscription Service</h2>
                </div>
                <div className="card-body">
                    {/* Main query builder UI */}
                    <div className="row">
                        <div className="col-md-6 mb-3">
                            <h5>1. Select Date Range (Optional)</h5>
                            <select 
                                className="form-select" 
                                value={dateRange} 
                                onChange={(e) => setDateRange(e.target.value)}
                            >
                                <option value="recent">Recent (Default)</option>
                                <option value="last_month">Last Month</option>
                                <option value="last_3_months">Last 3 Months</option>
                                <option value="last_year">Last Year</option>
                                <option value="last_2_years">Last 2 Years</option>
                            </select>
                        </div>
                        <div className="col-md-6 mb-3">
                            <h5>2. Enter Keywords (Required)</h5>
                            <input 
                                type="text" 
                                className="form-control" 
                                value={keywords}
                                onChange={(e) => setKeywords(e.target.value)}
                                placeholder="e.g., transformer, diffusion"
                                required
                            />
                        </div>
                    </div>
                    <div className="mb-3">
                        <h5>3. Select Categories (Optional)</h5>
                        <div className="d-flex align-items-center mb-2 flex-wrap">
                            <strong className="me-3">Actions:</strong>
                            <div className="btn-group btn-group-sm me-3 mb-1" role="group">
                                {Object.keys(categoryPresets).map(name => (
                                    <button key={name} type="button" className="btn btn-outline-primary" onClick={() => handlePresetClick(name)}>
                                        {name}
                                    </button>
                                ))}
                            </div>
                            <div className="form-check me-3 mb-1">
                                <input className="form-check-input" type="checkbox" id="selectAllCheck" onChange={handleSelectAll} checked={allSelected} />
                                <label className="form-check-label" htmlFor="selectAllCheck">Select All</label>
                            </div>
                            <button className="btn btn-sm btn-outline-secondary mb-1" onClick={handleClearSelection}>Clear Selection</button>
                        </div>
                        <div className="card p-3" style={{ maxHeight: '200px', overflowY: 'auto' }}>
                            <div className="row">
                                {AVAILABLE_CATEGORIES.map(cat => (
                                    <div key={cat} className="col-md-3">
                                        <div className="form-check">
                                            <input type="checkbox" className="form-check-input" id={cat} checked={!!selectedCategories[cat]} onChange={() => handleCategoryChange(cat)} />
                                            <label className="form-check-label" htmlFor={cat}>{cat}</label>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="d-grid mt-4">
                        <button className="btn btn-primary btn-lg" onClick={handleRunProcess} disabled={status === 'running'}>
                            {status === 'running' ? 'Fetching Papers...' : 'Fetch Papers for Review'}
                        </button>
                    </div>
                    <hr />
                    <div>
                        <button className="btn btn-danger" onClick={handleClearCache}>清除缓存 (慎重)</button>
                    </div>
                </div>
            </div>

            {/* Recent Analyses Section */}
            <div className="card shadow-sm">
                <div className="card-header d-flex justify-content-between align-items-center">
                    <h4 className="mb-0">Recent Analyses</h4>
                    <Link to="/warehouse" className="btn btn-sm btn-info">View All in Warehouse &rarr;</Link>
                </div>
                <div className="list-group list-group-flush">
                    {recentPapers.length > 0 ? (
                        recentPapers.map(paper => (
                            <Link 
                                key={paper.entry_id} 
                                to={`/analysis/${paper.short_id}`} 
                                state={{ paper: paper }} 
                                className="list-group-item list-group-item-action"
                            >
                                <div className="d-flex w-100 justify-content-between">
                                    <strong className="mb-1">{paper.title}</strong>
                                    <small>{new Date(paper.published).toLocaleDateString()}</small>
                                </div>
                                <p className="mb-1 text-muted">{paper.authors.join(', ')}</p>
                            </Link>
                        ))
                    ) : (
                        <div className="list-group-item">No recent analyses found.</div>
                    )}
                </div>
            </div>
        </>
    );
}

export default QueryPage;

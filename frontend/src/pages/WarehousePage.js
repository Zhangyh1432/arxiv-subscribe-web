import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../App';

const PaperListItem = ({ paper }) => (
    <div className="list-group-item list-group-item-action">
        <div className="d-flex w-100 justify-content-between">
            <h5 className="mb-1">{paper.title}</h5>
            <small>{new Date(paper.published).toLocaleDateString()}</small>
        </div>
        <p className="mb-1"><strong>Authors:</strong> {paper.authors.join(', ')}</p>
        <p className="mb-1"><strong>ID:</strong> {paper.entry_id}</p>
        <Link to={`/analysis/${paper.short_id}`} state={{ paper: paper }} className="btn btn-sm btn-primary">
            View Analysis
        </Link>
    </div>
);

function WarehousePage() {
    const [papers, setPapers] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [loading, setLoading] = useState(true);

    const fetchPapers = useCallback(async (query) => {
        setLoading(true);
        try {
            const response = await axios.get(`${API_BASE_URL}/api/all-analyses?query=${query}`);
            setPapers(response.data);
        } catch (error) {
            console.error("Failed to fetch papers:", error);
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        fetchPapers(''); // Initial fetch for all papers
    }, [fetchPapers]);

    const handleSearch = (e) => {
        e.preventDefault();
        fetchPapers(searchTerm);
    };

    return (
        <div className="card shadow-lg">
            <div className="card-header text-center bg-dark text-white">
                <h2>Analysis Warehouse</h2>
            </div>
            <div className="card-body">
                <div className="mb-3">
                    <Link to="/" className="btn btn-secondary mb-3"> &larr; Back to Query Page</Link>
                </div>

                <form onSubmit={handleSearch} className="mb-4">
                    <div className="input-group">
                        <input 
                            type="text"
                            className="form-control"
                            placeholder="Search by title or paper ID..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                        <button className="btn btn-primary" type="submit">Search</button>
                    </div>
                </form>

                {loading ? (
                    <p>Loading history...</p>
                ) : (
                    <div className="list-group">
                        {papers.length > 0 ? (
                            papers.map(paper => <PaperListItem key={paper.entry_id} paper={paper} />)
                        ) : (
                            <p>No analyzed papers found.</p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

export default WarehousePage;
